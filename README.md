# 🤖 Zero-Cost AI Research Pipeline

An automated system that scrapes top AI/Tech newsletters, summarises them with **Gemini 2.0 Flash** (free tier), stores results as JSON in this repo via **GitOps**, and displays them on a **React dashboard** hosted on **Vercel** — for **$0/month**.

```
GitHub Actions (cron)
  └─► Python scraper (feedparser)
        └─► Gemini 2.0 Flash API
              └─► data/ JSON files (committed to repo)
                    └─► Vercel (static site) ◄── React dashboard
```

---

## 🗂 Project Structure

```
.
├── .github/workflows/main.yml   # Cron-triggered GitHub Actions
├── data/
│   ├── index.json               # Frontend discovery manifest
│   ├── daily/   YYYY-MM-DD.json
│   ├── weekly/  YYYY-WNN.json
│   └── monthly/ YYYY-MM.json
├── scripts/
│   ├── processor.py             # Scraper + Gemini summariser
│   ├── seed_data.py             # One-time placeholder generator
│   ├── feeds.json               # RSS feed list (customise this!)
│   └── requirements.txt
├── frontend/                    # React + Vite + Tailwind dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/   (Home, Archive, Weekly, Monthly)
│   │   ├── components/
│   │   └── hooks/useData.ts
│   └── package.json
└── vercel.json
```

---

## ⚙️ Setup Guide

### Step 1 — Fork / Clone

```bash
git clone https://github.com/Yash-1505/ai-research-pipeline.git
cd ai-research-pipeline
```

### Step 2 — Get a Gemini API Key (Free)

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API Key**
3. Copy the key — it starts with `AIza…`

> **Free tier limits (as of mid-2024):**  
> 15 requests/minute · 1 million tokens/minute · 1,500 requests/day  
> This is more than enough for daily summarisation.

### Step 3 — Add GitHub Secrets

Go to your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name       | Value                                   |
|-------------------|-----------------------------------------|
| `GEMINI_API_KEY`  | Your Gemini API key (`AIza…`)           |
| `VERCEL_TOKEN`    | From vercel.com → Settings → Tokens    |
| `VERCEL_ORG_ID`   | From `.vercel/project.json` after link  |
| `VERCEL_PROJECT_ID` | From `.vercel/project.json` after link |

> **Vercel secrets** are only needed if you want GitHub Actions to auto-deploy. If you use Vercel's own Git integration (recommended for simplicity), you only need `GEMINI_API_KEY`.

### Step 4 — Seed Placeholder Data

Before deploying, generate placeholder files so the dashboard isn't empty:

```bash
pip install feedparser google-generativeai
python scripts/seed_data.py
git add data/
git commit -m "chore: seed placeholder data"
git push
```

### Step 5 — Deploy to Vercel

#### Option A — Vercel Git Integration (Recommended, Zero Config)

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repo
3. Vercel auto-detects the `vercel.json` config
4. Click **Deploy**

Every time the GitHub Action commits new data, Vercel will **auto-redeploy** via its Git webhook.

#### Option B — Manual / GitHub Actions Deploy

1. Install Vercel CLI: `npm i -g vercel`
2. In the repo root: `vercel link` — this creates `.vercel/project.json`
3. Copy `orgId` and `projectId` into your GitHub Secrets (see Step 3)
4. The workflow's `deploy` job will then handle deployment automatically

### Step 6 — Test the Pipeline Manually

Go to your repo → **Actions → AI Research Pipeline → Run workflow**

Select mode:
- `daily` — scrapes last 24h, summarises, commits
- `weekly` — aggregates the past 7 daily files
- `monthly` — aggregates the past 4–5 weekly files

---

## 🕐 Cron Schedule

| Job            | Schedule              | Runs at (UTC) |
|----------------|-----------------------|---------------|
| Daily Digest   | `0 7 * * *`           | 07:00 every day |
| Weekly Digest  | `0 8 * * 1`           | 08:00 every Monday |
| Monthly Report | `0 9 5 * *`           | 09:00 on the 5th |

---

## 📡 Customising RSS Feeds

Edit `scripts/feeds.json` to add/remove feeds:

```json
[
  {
    "name":  "My Custom Feed",
    "url":   "https://example.com/feed.xml",
    "tags":  ["AI", "research"]
  }
]
```

Any valid RSS or Atom feed works with `feedparser`.

---

## 🧠 How Deduplication Works

- Each article gets a 16-char SHA-256 hash of its normalised `title + url`
- Seen hashes are stored in `data/seen_hashes.json` (committed to repo)
- Articles with a known hash are skipped on subsequent runs
- Reset deduplication by deleting `data/seen_hashes.json`

---

## 💰 Cost Breakdown

| Component          | Service                | Cost      |
|--------------------|------------------------|-----------|
| Scraping & AI logic | GitHub Actions         | **$0**   |
| LLM summarisation  | Gemini 2.0 Flash       | **$0**   |
| Data storage       | GitHub repo (`data/`)  | **$0**   |
| Frontend hosting   | Vercel Hobby           | **$0**   |
| **Total**          |                        | **$0/mo** |

---

## 🛡️ Security Notes

- `GEMINI_API_KEY` is only ever accessed inside GitHub Actions as an encrypted secret — it is never committed to the repository
- The frontend is fully static; no secrets ever touch the client
- `data/seen_hashes.json` contains only hashes, no article content

---

## 🔧 Local Development

```bash
# Run the pipeline locally (needs GEMINI_API_KEY in env)
export GEMINI_API_KEY="AIza..."
pip install -r scripts/requirements.txt
python scripts/processor.py --mode daily

# Run the frontend dev server
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

> The Vite dev server serves `data/` as static files from the repo root via `publicDir: "../data"` in `vite.config.ts`.

---

## 📝 License

MIT — use freely, attribution appreciated.
