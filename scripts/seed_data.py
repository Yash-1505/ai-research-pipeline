#!/usr/bin/env python3
"""
seed_data.py — Creates placeholder JSON files so the frontend has
something to render on a fresh clone before the pipeline has run.
Run once after cloning: python scripts/seed_data.py
"""

import json
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR  = REPO_ROOT / "data"

PLACEHOLDER_SUMMARY = """## 🔑 Executive Summary

- This is a **placeholder digest** — the real pipeline has not run yet.
- Add your `GEMINI_API_KEY` to GitHub Secrets and trigger the workflow.
- Once the GitHub Action runs, this file will be replaced with live AI summaries.
- Check the README for full setup instructions.

## 🚀 Top Stories

### Pipeline not yet activated
Run the GitHub Action manually via **Actions → AI Research Pipeline → Run workflow** to generate your first real digest.

## 🧠 Key Trends & Signals

- RSS scraping: ✅ configured
- Gemini 1.5 Flash summarisation: ⏳ awaiting API key
- GitOps data storage: ✅ ready
- Vercel deployment: ✅ deployed

## ⚡ Action Items

1. Go to **Settings → Secrets → Actions** in your GitHub repo
2. Add secret `GEMINI_API_KEY` with your Gemini API key
3. Trigger the workflow manually to generate your first digest
"""

def seed_daily():
    d = DATA_DIR / "daily"
    d.mkdir(parents=True, exist_ok=True)
    today = date.today()
    for i in range(3):
        dt = (today - timedelta(days=i)).isoformat()
        f  = d / f"{dt}.json"
        if not f.exists():
            payload = {
                "type": "daily",
                "date": dt,
                "generated_at": f"{dt}T07:00:00Z",
                "article_count": 0,
                "sources": [],
                "summary": PLACEHOLDER_SUMMARY,
                "articles": [],
            }
            f.write_text(json.dumps(payload, indent=2))
            print(f"  Created {f.relative_to(REPO_ROOT)}")


def seed_weekly():
    d = DATA_DIR / "weekly"
    d.mkdir(parents=True, exist_ok=True)
    today = date.today()
    from datetime import date as dt_
    iso = today.isocalendar()
    label = f"{iso.year}-W{iso.week:02d}"
    f = d / f"{label}.json"
    if not f.exists():
        payload = {
            "type": "weekly",
            "week_label": label,
            "generated_at": f"{today.isoformat()}T08:00:00Z",
            "daily_dates": [],
            "summary": PLACEHOLDER_SUMMARY.replace("daily digest", "weekly digest"),
        }
        f.write_text(json.dumps(payload, indent=2))
        print(f"  Created {f.relative_to(REPO_ROOT)}")


def seed_monthly():
    d = DATA_DIR / "monthly"
    d.mkdir(parents=True, exist_ok=True)
    label = date.today().strftime("%Y-%m")
    f = d / f"{label}.json"
    if not f.exists():
        payload = {
            "type": "monthly",
            "month_label": label,
            "generated_at": f"{date.today().isoformat()}T09:00:00Z",
            "weekly_labels": [],
            "summary": PLACEHOLDER_SUMMARY.replace("daily digest", "monthly report"),
        }
        f.write_text(json.dumps(payload, indent=2))
        print(f"  Created {f.relative_to(REPO_ROOT)}")


def seed_index():
    """Build a fresh index.json from whatever's in data/."""
    from datetime import datetime
    index: dict = {"daily": [], "weekly": [], "monthly": []}
    for kind in ("daily", "weekly", "monthly"):
        folder = DATA_DIR / kind
        if folder.exists():
            for fp in sorted(folder.glob("*.json"), reverse=True):
                meta = json.loads(fp.read_text())
                index[kind].append({
                    "file":          f"data/{kind}/{fp.name}",
                    "label":         meta.get("date") or meta.get("week_label") or meta.get("month_label", fp.stem),
                    "date":          meta.get("date") or meta.get("generated_at", "")[:10],
                    "article_count": meta.get("article_count"),
                })
    index["last_updated"] = datetime.utcnow().isoformat() + "Z"
    idx_file = DATA_DIR / "index.json"
    idx_file.write_text(json.dumps(index, indent=2))
    print(f"  Updated {idx_file.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    print("Seeding placeholder data…")
    seed_daily()
    seed_weekly()
    seed_monthly()
    seed_index()
    print("Done. Commit the data/ folder and deploy.")
