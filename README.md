# job-scrapper

A Python scraper that searches [OnlineJobs.ph](https://www.onlinejobs.ph) for remote job listings matching configured keywords (e.g. `automation`, `n8n`, `make.com`, `zapier`) and pushes each result as JSON to a Make.com webhook for downstream automation (e.g. Telegram notifications).

## How It Works

1. Searches OnlineJobs.ph for each keyword in the `KEYWORDS` list.
2. Waits a random 5–12 seconds between searches to mimic human browsing.
3. Extracts from each results-page card: job title, salary, employment type, employer name (when shown), and link — top **1 per keyword** (deduplicated across keywords), so each keyword contributes at most one notification per run.
4. Visits each listing's page (with a polite 2–5 second pause) to pull the **full job description**.
5. POSTs each listing as JSON to your Make.com webhook.
6. If no listings are found, sends a single fallback search link so downstream automations never stall.

### Webhook Payload

Each job is sent individually with this shape:

```json
{
  "jobTitle": "Senior Digital Marketing, AI Content & E-Commerce Manager",
  "company": "MadeEA",
  "salary": "$1200/month",
  "employmentType": "Full Time",
  "url": "https://www.onlinejobs.ph/jobseekers/job/12345",
  "datePosted": "2026-08-24",
  "description": "About the Role\nWe are an established and growing…"
}
```

## Requirements

- Python 3.8+ (CI uses 3.11)
- [`requests`](https://pypi.org/project/requests/)

## Local Usage

```bash
git clone https://github.com/<your-username>/job-scrapper.git
cd job-scrapper

pip install requests

# Required: your Make.com webhook URL
export WEBHOOK_URL="https://hook.us2.make.com/your-hook-id"

python main.py
```

The script exits immediately with an error if `WEBHOOK_URL` is not set.

## Configuration

All configuration lives in `main.py`:

| Setting | Location | Default |
|---|---|---|
| Search keywords | `KEYWORDS` list (top of `main.py`) | `automation`, `n8n`, `make.com`, `zapier` |
| Jobs kept per keyword | `MAX_JOBS_PER_KEYWORD` | `1` |
| Webhook URL | `WEBHOOK_URL` environment variable | — (required) |

## Automated Runs (GitHub Actions)

The included workflow [`.github/workflows/scrape.yml`](.github/workflows/scrape.yml):

- Runs automatically **every 4 hours** (`0 */4 * * *`)
- Can be triggered manually anytime via the **Run workflow** button on the Actions tab
- Injects the webhook URL from the `WEBHOOK_URL` repository secret

### Setting Up Your Own Fork

1. Go to **Settings → Secrets and variables → Actions → New repository secret**
2. Name: `WEBHOOK_URL` — Value: your Make.com webhook URL
3. Make sure **Actions are enabled** on the repository (Settings → Actions)
4. Trigger a test run: **Actions tab → Run Job Scraper Hourly → Run workflow**

## Notes & Limitations

- Listings are parsed with regex over raw HTML; if OnlineJobs.ph changes its markup, the scraper may return zero results (the fallback link will be sent instead).
- OnlineJobs.ph hides employer names from logged-out visitors; the real company name is only included when the listing shows an employer logo — otherwise it falls back to `OnlineJobs.ph Employer`.
- Descriptions are sent in full (tags stripped, whitespace cleaned), ready to be passed through an AI step for proposal generation.
- Each run makes one extra request per job (for the full description); the random delays keep this polite for the site.
- OnlineJobs.ph occasionally rate-limits into temporary bot-checks; both search and description fetches retry several times with growing waits before falling back (warnings appear in the Actions log when a teaser is sent instead of the full text).
- Keep the per-keyword cap and random delays in place to avoid hammering the site or spamming your connected automations.
