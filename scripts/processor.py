#!/usr/bin/env python3
"""
Zero-Cost AI Research Pipeline — processor.py
Scrapes RSS feeds, deduplicates, and summarizes with Gemini 1.5 Flash.

Usage:
  python processor.py --mode daily     # Run daily digest
  python processor.py --mode weekly    # Run weekly digest (every Monday)
  python processor.py --mode monthly   # Run monthly report (5th of month)
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import feedparser
import google.generativeai as genai

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
DATA_DIR    = REPO_ROOT / "data"
SCRIPTS_DIR = Path(__file__).parent
SEEN_FILE   = DATA_DIR / "seen_hashes.json"
FEEDS_FILE  = SCRIPTS_DIR / "feeds.json"

# Gemini rate-limit guard — free tier is 15 RPM / 1M TPM
GEMINI_MODEL   = "gemini-1.5-flash"
MAX_CHARS_BATCH = 80_000   # ~20k tokens; safe per-request ceiling
RETRY_DELAY_S   = 65       # Wait 65s between batches to respect RPM

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_seen_hashes() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen_hashes(hashes: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(hashes), indent=2))


def article_hash(title: str, link: str) -> str:
    """Stable dedup key: sha256 of normalised title+url."""
    norm = re.sub(r"\W+", " ", (title + link).lower().strip())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def parse_date(entry) -> str:
    """Extract ISO date string from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return date(*t[:3]).isoformat()
    return date.today().isoformat()


def entry_text(entry) -> str:
    """Best-effort full text extraction from an RSS entry."""
    content = ""
    if hasattr(entry, "content"):
        content = entry.content[0].get("value", "")
    if not content and hasattr(entry, "summary"):
        content = entry.summary
    # Strip HTML tags
    content = re.sub(r"<[^>]+>", " ", content)
    content = re.sub(r"\s+", " ", content).strip()
    return content[:3000]  # cap per article


# ── Scraping ──────────────────────────────────────────────────────────────────

def scrape_feeds(feeds: list[dict], since_date: date) -> tuple[list[dict], set[str]]:
    """
    Scrape all feeds, filter articles published >= since_date, deduplicate.
    Returns (articles, new_hashes).

    IMPORTANT: hashes are NOT persisted here. The caller must call
    save_seen_hashes(new_hashes) only after a successful write, so a
    Gemini failure cannot permanently blacklist un-summarised articles.
    """
    existing_seen = load_seen_hashes()
    new_hashes: set[str] = set()
    articles: list[dict] = []

    for feed_meta in feeds:
        name = feed_meta["name"]
        url  = feed_meta["url"]
        log.info("Fetching feed: %s", name)

        try:
            parsed = feedparser.parse(url, request_headers={
                "User-Agent": "Mozilla/5.0 (compatible; AI-Research-Bot/1.0)"
            })
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", url, exc)
            continue

        if parsed.bozo:
            log.warning("Malformed feed %s: %s", name, parsed.bozo_exception)

        for entry in parsed.entries:
            title = getattr(entry, "title", "").strip()
            link  = getattr(entry, "link",  "").strip()
            if not title or not link:
                continue

            pub_date_str = parse_date(entry)
            try:
                pub_date = date.fromisoformat(pub_date_str)
            except ValueError:
                pub_date = date.today()

            if pub_date < since_date:
                continue

            h = article_hash(title, link)
            if h in existing_seen or h in new_hashes:
                log.debug("Skip duplicate: %s", title[:80])
                continue

            new_hashes.add(h)
            articles.append({
                "hash":      h,
                "title":     title,
                "link":      link,
                "source":    name,
                "tags":      feed_meta.get("tags", []),
                "date":      pub_date_str,
                "text":      entry_text(entry),
            })

    log.info("Scraped %d new articles since %s", len(articles), since_date)
    return articles, new_hashes


# ── Gemini Summarization ──────────────────────────────────────────────────────

def build_daily_prompt(articles: list[dict], target_date: str) -> str:
    lines = [
        f"You are a CTO-level AI research analyst. Today is {target_date}.",
        "Below are raw articles scraped from top AI/Tech newsletters.",
        "Your task: produce a DAILY BRIEFING in clean Markdown with these sections:\n",
        "## 🔑 Executive Summary  (3-5 bullets, each ≤ 25 words)\n",
        "## 🚀 Top Stories  (top 5–8 stories, each with: ### Title, 2-sentence summary, source, link)\n",
        "## 🧠 Key Trends & Signals  (bullet list of emerging patterns CTO should track)\n",
        "## ⚡ Action Items  (what an AI-focused team should do/consider this week)\n",
        "Rules: No fluff. No repeated information. Prioritise research breakthroughs, model releases, and business-critical AI news. Skip pure marketing puff.\n",
        "---\nARTICLES:\n",
    ]
    for art in articles:
        lines.append(
            f"\n### {art['title']}\nSource: {art['source']} | Date: {art['date']} | URL: {art['link']}\n{art['text']}\n"
        )
    return "\n".join(lines)


def build_weekly_prompt(daily_files: list[Path]) -> str:
    combined = []
    for f in daily_files:
        data = json.loads(f.read_text())
        combined.append(f"=== DATE: {data.get('date', 'unknown')} ===\n{data.get('summary', '')}")

    return (
        "You are a CTO-level AI research analyst. Synthesise the following 7 DAILY BRIEFINGS into a "
        "WEEKLY DIGEST in clean Markdown.\n\n"
        "Required sections:\n"
        "## 📅 Week in Review  (top headline: 1 sentence)\n"
        "## 🏆 Biggest Stories of the Week  (5–10, deduplicated)\n"
        "## 📈 Trend Analysis  (patterns that appeared multiple days — what's accelerating?)\n"
        "## 🔬 Research Highlights  (notable papers/releases worth deep-reading)\n"
        "## 💼 Business & Industry Moves  (funding, acquisitions, partnerships)\n"
        "## 🗓️ What to Watch Next Week\n\n"
        "Rules: No repetition across sections. Merge duplicate stories into single entries. Be concise and CTO-appropriate.\n\n"
        "---\nDAILY SUMMARIES:\n\n" + "\n\n".join(combined)
    )


def build_monthly_prompt(weekly_files: list[Path]) -> str:
    combined = []
    for f in weekly_files:
        data = json.loads(f.read_text())
        combined.append(f"=== WEEK: {data.get('week_label', 'unknown')} ===\n{data.get('summary', '')}")

    return (
        "You are a CTO-level AI research analyst. Synthesise the following WEEKLY DIGESTS into a "
        "MONTHLY EXECUTIVE REPORT in clean Markdown.\n\n"
        "Required sections:\n"
        "## 📊 Month at a Glance  (3–5 bullet TL;DR)\n"
        "## 🎯 Major Milestones  (top 10 most important events/releases of the month)\n"
        "## 📈 Macro Trends  (3–5 persistent trends; rate each: Accelerating / Stable / Slowing)\n"
        "## 🔬 Research Landscape  (notable papers, model releases, benchmark shifts)\n"
        "## 💰 Industry & Investment  (funding rounds, M&A, big-tech moves)\n"
        "## ⚠️ Risks & Watch List  (emerging risks, regulatory signals, controversial developments)\n"
        "## 📋 Strategic Recommendations  (what an AI-focused company should prioritise next month)\n\n"
        "Rules: Executive-level prose. No duplication. Cite sources where known. Be analytical, not journalistic.\n\n"
        "---\nWEEKLY DIGESTS:\n\n" + "\n\n".join(combined)
    )


def call_gemini(prompt: str, api_key: str) -> str:
    """Call Gemini 1.5 Flash with retry on 429."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    for attempt in range(1, 4):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
            )
            return response.text
        except Exception as exc:
            log.warning("Gemini attempt %d failed: %s", attempt, exc)
            if attempt < 3:
                wait = RETRY_DELAY_S * attempt
                log.info("Waiting %ds before retry…", wait)
                time.sleep(wait)
    raise RuntimeError("Gemini API failed after 3 attempts")


def batch_and_summarise(articles: list[dict], api_key: str, target_date: str) -> str:
    """Split articles into token-safe batches and concatenate summaries."""
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0

    for art in articles:
        chars = len(art["text"]) + len(art["title"]) + 200
        if current_chars + chars > MAX_CHARS_BATCH and current:
            batches.append(current)
            current, current_chars = [], 0
        current.append(art)
        current_chars += chars

    if current:
        batches.append(current)

    if not batches:
        return "No new articles found for this period."

    log.info("Processing %d batch(es) through Gemini…", len(batches))
    summaries: list[str] = []

    for i, batch in enumerate(batches, 1):
        log.info("Batch %d/%d (%d articles)…", i, len(batches), len(batch))
        prompt  = build_daily_prompt(batch, target_date)
        result  = call_gemini(prompt, api_key)
        summaries.append(result)

        if i < len(batches):
            log.info("Rate-limit pause %ds…", RETRY_DELAY_S)
            time.sleep(RETRY_DELAY_S)

    if len(summaries) == 1:
        return summaries[0]

    # Merge multi-batch summaries with a second Gemini call
    log.info("Merging %d partial summaries…", len(summaries))
    merge_prompt = (
        "You are a CTO-level AI research analyst. Merge and deduplicate the following partial daily briefings "
        "into ONE cohesive DAILY BRIEFING. Keep all sections (Executive Summary, Top Stories, Key Trends, "
        "Action Items). Remove any duplicate stories. Output clean Markdown only.\n\n"
        + "\n\n---PARTIAL---\n\n".join(summaries)
    )
    return call_gemini(merge_prompt, api_key)


# ── Output Writers ────────────────────────────────────────────────────────────

def write_daily(summary: str, articles: list[dict], target_date: str) -> None:
    out_dir = DATA_DIR / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{target_date}.json"

    payload = {
        "type":         "daily",
        "date":         target_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "article_count": len(articles),
        "sources":      sorted({a["source"] for a in articles}),
        "summary":      summary,
        "articles":     [{"title": a["title"], "link": a["link"],
                          "source": a["source"], "date": a["date"],
                          "tags": a["tags"]} for a in articles],
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info("Written: %s", out_file)


def write_weekly(summary: str, week_label: str, daily_dates: list[str]) -> None:
    out_dir = DATA_DIR / "weekly"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{week_label}.json"

    payload = {
        "type":         "weekly",
        "week_label":   week_label,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "daily_dates":  daily_dates,
        "summary":      summary,
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info("Written: %s", out_file)


def write_monthly(summary: str, month_label: str, weekly_labels: list[str]) -> None:
    out_dir = DATA_DIR / "monthly"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{month_label}.json"

    payload = {
        "type":          "monthly",
        "month_label":   month_label,
        "generated_at":  datetime.utcnow().isoformat() + "Z",
        "weekly_labels": weekly_labels,
        "summary":       summary,
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info("Written: %s", out_file)


def write_index() -> None:
    """Regenerate data/index.json for the frontend to discover available files."""
    index: dict[str, Any] = {"daily": [], "weekly": [], "monthly": []}

    for kind in ("daily", "weekly", "monthly"):
        d = DATA_DIR / kind
        if d.exists():
            files = sorted(d.glob("*.json"), reverse=True)
            for f in files:
                try:
                    meta = json.loads(f.read_text())
                    index[kind].append({
                        "file":  f"data/{kind}/{f.name}",
                        "label": meta.get("date") or meta.get("week_label") or meta.get("month_label", f.stem),
                        "date":  meta.get("date") or meta.get("generated_at", "")[:10],
                        "article_count": meta.get("article_count"),
                    })
                except Exception:
                    pass

    index["last_updated"] = datetime.utcnow().isoformat() + "Z"
    index_file = DATA_DIR / "index.json"
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    log.info("Index updated: %s", index_file)


# ── Modes ─────────────────────────────────────────────────────────────────────

def run_daily(api_key: str) -> None:
    today = date.today()
    target = today.isoformat()
    log.info("=== DAILY MODE: %s ===", target)

    feeds = json.loads(FEEDS_FILE.read_text())
    # Look back 3 days on Monday to catch Saturday+Sunday; 1 day otherwise.
    # Also gives a 1-day buffer if the cron was delayed.
    lookback = 3 if today.weekday() == 0 else 1
    since = today - timedelta(days=lookback)
    articles, new_hashes = scrape_feeds(feeds, since)

    if not articles:
        log.warning("No new articles found; writing empty placeholder.")
        summary = "No new articles found for this date."
        write_daily(summary, [], target)
    else:
        summary = batch_and_summarise(articles, api_key, target)
        write_daily(summary, articles, target)

    # Persist new hashes only after a successful write.
    # Moving this here (vs. inside scrape_feeds) means a Gemini failure
    # won't permanently blacklist articles that were never summarised.
    existing = load_seen_hashes()
    save_seen_hashes(existing | new_hashes)
    write_index()


def run_weekly(api_key: str) -> None:
    today = date.today()
    # The job runs on Monday — we want the PREVIOUS week (Mon–Sun).
    # today.weekday() == 0 on Monday, so subtracting 7 more days gives last Monday.
    last_monday = today - timedelta(days=today.weekday() + 7)
    week_label = f"{last_monday.isocalendar().year}-W{last_monday.isocalendar().week:02d}"
    log.info("=== WEEKLY MODE: %s ===", week_label)

    # Collect daily files for the 7 days of last week (Mon–Sun)
    daily_dates = [(last_monday + timedelta(days=i)).isoformat() for i in range(7)]
    daily_files = [DATA_DIR / "daily" / f"{d}.json" for d in daily_dates
                   if (DATA_DIR / "daily" / f"{d}.json").exists()]

    if not daily_files:
        # Fallback: scrape directly for the whole week
        log.info("No daily files found; scraping week directly…")
        feeds    = json.loads(FEEDS_FILE.read_text())
        articles, new_hashes = scrape_feeds(feeds, last_monday)
        summary  = batch_and_summarise(articles, api_key, week_label)
        existing = load_seen_hashes()
        save_seen_hashes(existing | new_hashes)
    else:
        prompt  = build_weekly_prompt(daily_files)
        summary = call_gemini(prompt, api_key)

    write_weekly(summary, week_label, daily_dates)
    write_index()


def run_monthly(api_key: str) -> None:
    today       = date.today()
    month_label = today.strftime("%Y-%m")
    log.info("=== MONTHLY MODE: %s ===", month_label)

    # Collect weekly files for the past 4–5 weeks
    weekly_files = sorted((DATA_DIR / "weekly").glob("*.json"), reverse=True)[:5]

    if not weekly_files:
        # Fallback: scrape entire month
        log.info("No weekly files found; scraping month directly…")
        feeds      = json.loads(FEEDS_FILE.read_text())
        month_start = date(today.year, today.month, 1)
        articles, new_hashes = scrape_feeds(feeds, month_start)
        summary    = batch_and_summarise(articles, api_key, month_label)
        existing = load_seen_hashes()
        save_seen_hashes(existing | new_hashes)
    else:
        prompt  = build_monthly_prompt(list(weekly_files))
        summary = call_gemini(prompt, api_key)

    write_monthly(summary, month_label, [f.stem for f in weekly_files])
    write_index()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Research Pipeline Processor")
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Run mode",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        log.error("GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    (DATA_DIR / "daily").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "weekly").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "monthly").mkdir(parents=True, exist_ok=True)

    if args.mode == "daily":
        run_daily(api_key)
    elif args.mode == "weekly":
        run_weekly(api_key)
    elif args.mode == "monthly":
        run_monthly(api_key)


if __name__ == "__main__":
    main()
