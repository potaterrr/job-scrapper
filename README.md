# job-scrapper

A Python scraper that searches [OnlineJobs.ph](https://www.onlinejobs.ph) for the **most recent** remote job postings across configurable **categories** — automation, Python, customer email/chat support, and general VA by default — and pushes each pick as JSON to a Make.com webhook for downstream automation.

Runs **once a day** on GitHub Actions (06:30 PHT) and stays politely under the radar: public pages only, human-like delays, tiny volume.

## How It Works

1. For each **category**, searches OnlineJobs.ph for each of its keywords (random 5–12s pause between searches).
2. Parses every result card and **sorts by the exact posting timestamp** (`Posted on 2026-09-23 13:49:33`), so the newest listing wins.
3. Keeps the top listing per keyword, dedupes across keywords, caps at `MAX_PER_CATEGORY` per category (newest first).
4. Visits each picked listing (polite 2–5s pause) and pulls the **full description**, splitting out the employer's **"How to Apply"** section when present.
5. POSTs each job as JSON to your Make.com webhook.
6. If nothing is found, sends a single fallback search link so downstream automations never stall.

## Categories

Categories come from the `CATEGORIES` env var: **pipe** `|` separates categories, **semicolon** `;` separates keywords inside a category. The first keyword names the category.

```
automation;n8n;make.com;zapier|python|customer support;email support;chat support|virtual assistant
```

That default = 4 categories: `automation`, `python`, `customer support`, `virtual assistant`. Edit it in **Settings → Secrets and variables → Actions → Variables** (`CATEGORIES`, `MAX_PER_CATEGORY`) — no code changes needed.

## Webhook Payload

Each job is sent individually with this shape:

```json
{
  "jobTitle": "Graphic Designer, Marketing & Operations Coordinator",
  "company": "OnlineJobs.ph Employer",
  "category": "automation",
  "rate": "$444.50 PHP Per Hour",
  "salary": "$444.50 PHP Per Hour",
  "employmentType": "Part Time",
  "url": "https://www.onlinejobs.ph/jobseekers/job/…-1736482",
  "datePosted": "2026-09-23",
  "postedAt": "2026-09-23 13:49:33",
  "description": "The Opportunity\nAre you a mid-level designer…",
  "howToApply": "Please submit:\n● Your Resume and a short video…"
}
```

- `rate` / `salary` — the hourly/monthly rate exactly as shown on the listing card (`salary` kept for backward compatibility with existing Make scenarios)
- `howToApply` — the employer's application instructions, split out of the description when the listing has a "How to Apply" section (empty otherwise)
- `description` — capped at 600 chars (word-boundary cut); `howToApply` at 300
- `datePosted` / `postedAt` — the **real posting timestamp** from the listing card, so Make (and you) can judge freshness; both are empty when a card hides it — never faked to today

## Local Usage

```bash
export WEBHOOK_URL="https://hook.us2.make.com/your-hook-id"
python main.py                       # default categories, 1 per category

# Preview payloads without sending anything:
DRY_RUN=1 python main.py

# Custom categories and caps:
CATEGORIES="python coder|customer support;chat support" MAX_PER_CATEGORY=2 python main.py
```

Requirements: Python 3.8+ and `requests`.

## Schedule

GitHub Actions runs the scraper **daily at 22:30 UTC (06:30 PHT)** — see `.github/workflows/scrape.yml`.
The webhook URL is read from the **`SCRAPE_HOOK`** repository secret (Settings → Secrets and variables → Actions). You can also trigger it manually from the Actions tab (*Run workflow*).

## Fair-Use & TOS Notes

This scraper is built to be a good citizen of OnlineJobs.ph:

- **Public pages only** — search results and job listings a logged-out visitor sees. No login, no paywalled/premium data, no contact details or resumes.
- **Human-like pacing** — randomized 5–12s pauses between searches, 2–5s before each detail page, and exponential backoff with retries when the site serves a transient bot-check page (the run degrades gracefully and sends listing teasers instead of hammering).
- **Tiny daily volume** — one run per day, a handful of requests total (defaults touch ~7 searches + up to 4 detail pages). That's indistinguishable from a person browsing, and far below any load the site cares about.
- **Public data, credited** — every payload links back to the original listing; nothing is republished, only forwarded to a private notification pipeline.
- Respects the site's anti-bot interstitials instead of evading them: retry a few times with patience, then give up for this run.

If OnlineJobs.ph ever indicates automated access is unwelcome, discontinue the scraper.

## Repository Layout

- `main.py` — the scraper (requests-only; this is what CI runs)
- `.github/workflows/scrape.yml` — daily schedule + manual dispatch
