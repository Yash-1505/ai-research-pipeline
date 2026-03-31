#!/usr/bin/env python3
"""
Zero-Cost AI Research Pipeline â€” processor.py
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
from google import genai
from google.genai import types as genai_types

# â”€â”€ Logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
REPO_ROOT   = Path(__file__).parent.parent
DATA_DIR    = REPO_ROOT / "data"
SCRIPTS_DIR = Path(__file__).parent
SEEN_FILE   = DATA_DIR / "seen_hashes.json"
FEEDS_FILE  = SCRIPTS_DIR / "feeds.json"

# Gemini rate-limit guard â€” free tier is 15 RPM / 1M TPM
GEMINI_MODEL   = "gemini-2.0-flash"
MAX_CHARS_BATCH = 80_000   # ~20k tokens; safe per-request ceiling
RETRY_DELAY_S   = 65       # Wait 65s between batches to respect RPM

# Archival settings
ARCHIVE_BRANCH       = "data-archive"   # Orphan branch that receives old files
DAILY_RETENTION_DAYS = 90              # Daily files older than this are archived
HASH_RETENTION_DAYS  = 90             # Hashes older than this window are pruned

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def load_seen_hashes() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8-sig")))
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


# â”€â”€ Scraping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ Gemini Summarization â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_daily_prompt(articles: list[dict], target_date: str) -> str:
    lines = [
        f"You are a CTO-level AI research analyst. Today is {target_date}.",
        "Below are raw articles scraped from top AI/Tech newsletters.",
        "Your task: produce a DAILY BRIEFING in clean Markdown with these sections:\n",
        "## ðŸ”‘ Executive Summary  (3-5 bullets, each â‰¤ 25 words)\n",
        "## ðŸš€ Top Stories  (top 5â€“8 stories, each with: ### Title, 2-sentence summary, source, link)\n",
        "## ðŸ§  Key Trends & Signals  (bullet list of emerging patterns CTO should track)\n",
        "## âš¡ Action Items  (what an AI-focused team should do/consider this week)\n",
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
        "## ðŸ“… Week in Review  (top headline: 1 sentence)\n"
        "## ðŸ† Biggest Stories of the Week  (5â€“10, deduplicated)\n"
        "## ðŸ“ˆ Trend Analysis  (patterns that appeared multiple days â€” what's accelerating?)\n"
        "## ðŸ”¬ Research Highlights  (notable papers/releases worth deep-reading)\n"
        "## ðŸ’¼ Business & Industry Moves  (funding, acquisitions, partnerships)\n"
        "## ðŸ—“ï¸ What to Watch Next Week\n\n"
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
        "## ðŸ“Š Month at a Glance  (3â€“5 bullet TL;DR)\n"
        "## ðŸŽ¯ Major Milestones  (top 10 most important events/releases of the month)\n"
        "## ðŸ“ˆ Macro Trends  (3â€“5 persistent trends; rate each: Accelerating / Stable / Slowing)\n"
        "## ðŸ”¬ Research Landscape  (notable papers, model releases, benchmark shifts)\n"
        "## ðŸ’° Industry & Investment  (funding rounds, M&A, big-tech moves)\n"
        "## âš ï¸ Risks & Watch List  (emerging risks, regulatory signals, controversial developments)\n"
        "## ðŸ“‹ Strategic Recommendations  (what an AI-focused company should prioritise next month)\n\n"
        "Rules: Executive-level prose. No duplication. Cite sources where known. Be analytical, not journalistic.\n\n"
        "---\nWEEKLY DIGESTS:\n\n" + "\n\n".join(combined)
    )


def call_gemini(prompt: str, api_key: str) -> str:
    """Call Gemini 2.0 Flash, fall back to Sarvam AI if quota exceeded."""
    try:
        return _call_gemini_sdk(prompt, api_key)
    except RuntimeError as e:
        if "429" in str(e) or "quota" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
            log.warning("Gemini quota exceeded, falling back to Sarvam AI...")
            sarvam_key = os.environ.get("SARVAM_API_KEY", "").strip()
            if sarvam_key:
                return _call_sarvam(prompt, sarvam_key)
            log.error("SARVAM_API_KEY not set, cannot fallback.")
        raise


def _call_gemini_sdk(prompt: str, api_key: str) -> str:
    """Primary: Gemini 2.0 Flash via google-genai SDK."""
    client = genai.Client(api_key=api_key)
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                ),
            )
            return response.text
        except Exception as exc:
            log.warning("Gemini attempt %d failed: %s", attempt, exc)
            if attempt < 3:
                time.sleep(RETRY_DELAY_S * attempt)
    raise RuntimeError(f"429 Gemini API failed after 3 attempts")


def _call_sarvam(prompt: str, api_key: str) -> str:
    """Fallback: Sarvam AI sarvam-m via OpenAI-compatible API."""
    import requests as req
    url = "https://api.sarvam.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "sarvam-m",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 8192,
    }
    for attempt in range(1, 4):
        try:
            r = req.post(url, json=body, headers=headers, timeout=120)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log.warning("Sarvam attempt %d failed: %s", attempt, exc)
            if attempt < 3:
                time.sleep(30 * attempt)
    raise RuntimeError("Sarvam API also failed after 3 attempts")

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

    log.info("Processing %d batch(es) through Geminiâ€¦", len(batches))
    summaries: list[str] = []

    for i, batch in enumerate(batches, 1):
        log.info("Batch %d/%d (%d articles)â€¦", i, len(batches), len(batch))
        prompt  = build_daily_prompt(batch, target_date)
        result  = call_gemini(prompt, api_key)
        summaries.append(result)

        if i < len(batches):
            log.info("Rate-limit pause %dsâ€¦", RETRY_DELAY_S)
            time.sleep(RETRY_DELAY_S)

    if len(summaries) == 1:
        return summaries[0]

    # Merge multi-batch summaries with a second Gemini call
    log.info("Merging %d partial summariesâ€¦", len(summaries))
    merge_prompt = (
        "You are a CTO-level AI research analyst. Merge and deduplicate the following partial daily briefings "
        "into ONE cohesive DAILY BRIEFING. Keep all sections (Executive Summary, Top Stories, Key Trends, "
        "Action Items). Remove any duplicate stories. Output clean Markdown only.\n\n"
        + "\n\n---PARTIAL---\n\n".join(summaries)
    )
    return call_gemini(merge_prompt, api_key)


# â”€â”€ Output Writers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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


# â”€â”€ Modes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    # The job runs on Monday â€” we want the PREVIOUS week (Monâ€“Sun).
    # today.weekday() == 0 on Monday, so subtracting 7 more days gives last Monday.
    last_monday = today - timedelta(days=today.weekday() + 7)
    week_label = f"{last_monday.isocalendar().year}-W{last_monday.isocalendar().week:02d}"
    log.info("=== WEEKLY MODE: %s ===", week_label)

    # Collect daily files for the 7 days of last week (Monâ€“Sun)
    daily_dates = [(last_monday + timedelta(days=i)).isoformat() for i in range(7)]
    daily_files = [DATA_DIR / "daily" / f"{d}.json" for d in daily_dates
                   if (DATA_DIR / "daily" / f"{d}.json").exists()]

    if not daily_files:
        # Fallback: scrape directly for the whole week
        log.info("No daily files found; scraping week directlyâ€¦")
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

    # Collect weekly files for the past 4â€“5 weeks
    weekly_files = sorted((DATA_DIR / "weekly").glob("*.json"), reverse=True)[:5]

    if not weekly_files:
        # Fallback: scrape entire month
        log.info("No weekly files found; scraping month directlyâ€¦")
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


# â”€â”€ Archive & Maintenance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _git(cmd: str, cwd: Path = REPO_ROOT) -> str:
    """Run a git command, return stdout, raise on failure."""
    import subprocess
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {cmd!r}\n{result.stderr.strip()}")
    return result.stdout.strip()


def archive_old_daily_files() -> list[Path]:
    """
    Move daily JSON files older than DAILY_RETENTION_DAYS to the ARCHIVE_BRANCH
    orphan branch so main stays lean. Returns the list of files moved.

    Strategy:
      1. Identify stale daily files on main.
      2. Ensure the orphan archive branch exists (create it once if not).
      3. For each stale file: copy content to archive branch, then delete from main.
      4. Commit both sides.

    The archive branch is a true orphan â€” no shared history with main â€” so it
    never inflates main's object store with old blobs.
    """
    cutoff = date.today() - timedelta(days=DAILY_RETENTION_DAYS)
    daily_dir = DATA_DIR / "daily"

    stale: list[Path] = []
    for f in sorted(daily_dir.glob("*.json")):
        try:
            file_date = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            stale.append(f)

    if not stale:
        log.info("No daily files older than %d days â€” nothing to archive.", DAILY_RETENTION_DAYS)
        return []

    log.info("Archiving %d stale daily file(s) to branch '%s'â€¦", len(stale), ARCHIVE_BRANCH)

    # â”€â”€ Ensure the archive branch exists â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    existing_branches = _git("git branch -r")
    archive_exists = f"origin/{ARCHIVE_BRANCH}" in existing_branches

    if not archive_exists:
        log.info("Creating orphan branch '%s'â€¦", ARCHIVE_BRANCH)
        # Create an orphan branch with an empty initial commit
        _git(f"git checkout --orphan {ARCHIVE_BRANCH}")
        _git("git rm -rf . --quiet || true")
        _git(f'git commit --allow-empty -m "chore: initialise data-archive branch"')
        _git(f"git push origin {ARCHIVE_BRANCH}")
        _git("git checkout main")

    # â”€â”€ Copy each stale file to the archive branch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    import subprocess, tempfile, shutil

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Sparse checkout of archive branch into a temp dir
        _git(f"git worktree add {tmp} {ARCHIVE_BRANCH}")
        archive_daily = tmp_path / "data" / "daily"
        archive_daily.mkdir(parents=True, exist_ok=True)

        for f in stale:
            shutil.copy2(f, archive_daily / f.name)
            log.info("  â†’ archived %s", f.name)

        # Commit to archive branch via the worktree
        _git(f"git add data/", cwd=tmp_path)
        _git(
            f'git commit -m "archive: daily files up to {stale[-1].stem}"',
            cwd=tmp_path,
        )
        _git(f"git push origin {ARCHIVE_BRANCH}", cwd=tmp_path)
        _git(f"git worktree remove --force {tmp}")

    # â”€â”€ Delete stale files from main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for f in stale:
        f.unlink()
        log.info("  âœ• removed from main: %s", f.name)

    log.info("Archive complete. %d file(s) moved off main.", len(stale))
    return stale


def prune_seen_hashes() -> int:
    """
    Remove hashes from seen_hashes.json that belong to articles no longer
    present in any daily file on main (i.e. already archived or deleted).

    This prevents seen_hashes.json from growing unbounded. We keep hashes
    for any article whose source daily file is still in data/daily/, plus
    all hashes from the last HASH_RETENTION_DAYS regardless â€” this gives a
    safe dedup window even for articles whose daily file was just archived.

    Returns the number of hashes pruned.
    """
    existing = load_seen_hashes()
    if not existing:
        log.info("seen_hashes.json is empty â€” nothing to prune.")
        return 0

    # Collect every hash referenced by a daily file still on main
    active_hashes: set[str] = set()
    for f in (DATA_DIR / "daily").glob("*.json"):
        try:
            data = json.loads(f.read_text())
            for art in data.get("articles", []):
                h = art.get("hash") or article_hash(art.get("title", ""), art.get("link", ""))
                active_hashes.add(h)
        except Exception:
            pass

    # Also keep all hashes from the retention window â€” files that were just
    # archived could re-surface if feeds repost old articles.
    retention_cutoff = date.today() - timedelta(days=HASH_RETENTION_DAYS)
    for f in (DATA_DIR / "daily").glob("*.json"):
        try:
            file_date = date.fromisoformat(f.stem)
            if file_date >= retention_cutoff:
                data = json.loads(f.read_text())
                for art in data.get("articles", []):
                    h = art.get("hash") or article_hash(art.get("title", ""), art.get("link", ""))
                    active_hashes.add(h)
        except Exception:
            pass

    pruned = existing - active_hashes
    if not pruned:
        log.info("All %d hashes are still active â€” nothing pruned.", len(existing))
        return 0

    save_seen_hashes(active_hashes)
    log.info(
        "Pruned %d stale hashes from seen_hashes.json (%d â†’ %d).",
        len(pruned), len(existing), len(active_hashes),
    )
    return len(pruned)


def run_archive() -> None:
    """
    Monthly maintenance mode:
      1. Move daily files older than DAILY_RETENTION_DAYS to the archive branch.
      2. Prune stale hashes from seen_hashes.json.
      3. Regenerate index.json to reflect the trimmed data/ directory.
    Intended to run on the 1st of each month via GitHub Actions.
    """
    log.info("=== ARCHIVE MODE: %s ===", date.today().isoformat())
    archived = archive_old_daily_files()
    pruned   = prune_seen_hashes()
    write_index()

    log.info(
        "Maintenance complete â€” %d file(s) archived, %d hash(es) pruned.",
        len(archived), pruned,
    )


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Research Pipeline Processor")
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "monthly", "archive"],
        default="daily",
        help="Run mode",
    )
    args = parser.parse_args()

    # archive mode needs no API key
    if args.mode == "archive":
        (DATA_DIR / "daily").mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "weekly").mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "monthly").mkdir(parents=True, exist_ok=True)
        run_archive()
        return

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



