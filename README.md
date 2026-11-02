# job-scrapper

A Python scraper that searches [OnlineJobs.ph](https://www.onlinejobs.ph) for the **most recent** remote job postings across configurable **categories** and posts a **Discord embed per job**, summarized by **Gemini**. Runs on GitHub Actions every 4 hours.

## How It Works

1. For each **category**, searches OnlineJobs.ph for each of its keywords (random 5–12s pause between searches).
2. Parses every result card and **sorts by the exact posting timestamp**.
3. Keeps the top listing per keyword, dedupes across keywords, caps at `MAX_PER_CATEGORY` per category.
4. Visits each picked listing and pulls the **full description**, splitting out the employer's **"How to Apply"** section when present.
5. Summarizes each job with Gemini and posts **one Discord embed per job**.
6. Dedupes by URL via `seen_jobs.json` so repeat runs don't spam the channel.

## Categories

Categories come from the `CATEGORIES` env var: **pipe** `|` separates categories, **semicolon** `;` separates keywords inside a category. The first keyword names the category.

```
automation;n8n;make.com;zapier|python|customer support;email support;chat support|virtual assistant
```

## Discord Embed Payload

Each job is sent individually as a Discord embed with:
- Title + link to the listing
- AI summary (2–4 sentences)
- Fields: Category, Rate, Employment type, Posted date, How to apply

## Local Usage

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export GEMINI_API_KEY="your-gemini-key"
python main.py                       # default categories, 1 per category

# Preview payloads without sending anything:
DRY_RUN=1 python main.py

# Custom categories and caps:
CATEGORIES="python coder|customer support;chat support" MAX_PER_CATEGORY=2 python main.py
```

Requirements: Python 3.8+ and `requests`.

## GitHub Actions (every 4 hours)

The workflow runs on cron `0 */4 * * *` (UTC) and can be triggered manually.

### Secrets
- `DISCORD_WEBHOOK_URL` — Discord channel webhook
- `GEMINI_API_KEY` — Google AI Studio key

### Variables (optional)
- `GEMINI_MODEL` — default `gemini-1.5-flash`
- `CATEGORIES`
- `MAX_PER_CATEGORY`

### State
- `seen_jobs.json` is committed back to the repo after each run to prevent duplicate posts.

## Fair-Use & TOS Notes

- **Public pages only** — search results and job listings a logged-out visitor sees.
- **Human-like pacing** — randomized 5–12s pauses between searches, 2–5s before detail pages, exponential backoff on bot-check pages.
- **Tiny volume** — one run every 4 hours, a handful of requests per run.
- Respects anti-bot interstitials instead of evading them.