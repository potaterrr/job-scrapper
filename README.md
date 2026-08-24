# job-scrapper

A Python scraper that searches [OnlineJobs.ph](https://www.onlinejobs.ph) for remote job listings matching configured keywords (e.g. `automation`, `n8n`, `make.com`, `zapier`) and pushes each result as JSON to a Make.com webhook for downstream automation (e.g. Telegram notifications).

## How It Works

1. Searches OnlineJobs.ph for each keyword in the `keywords` list.
2. Waits a random 5–12 seconds between searches to mimic human browsing.
3. Extracts job titles and links from the results page (top **3 per keyword**, deduplicated across keywords).
4. POSTs each listing as JSON to your Make.com webhook.
5. If no listings are found, sends a single fallback search link so downstream automations never stall.

### Webhook Payload

Each job is sent individually with this shape:

```json
{
  "jobTitle": "Automation Specialist",
  "company": "OnlineJobs.ph Employer",
  "salary": "View Listing",
  "employmentType": "Remote",
  "url": "https://www.onlinejobs.ph/jobseekers/job/12345",
  "datePosted": "2026-08-24",
  "description": "Live scraped listing for keyword: automation"
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
| Search keywords | `keywords` list inside `fetch_jobs()` | `automation`, `n8n`, `make.com`, `zapier` |
| Jobs kept per keyword | `keyword_count` limit in `fetch_jobs()` | `3` |
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
- The company name and salary are placeholders (`OnlineJobs.ph Employer`, `View Listing`) since they are not extracted from the listing page.
- Keep the per-keyword cap and random delays in place to avoid hammering the site or spamming your connected automations.
