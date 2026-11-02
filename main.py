"""OnlineJobs.ph -> Make.com job scraper.

Polite by design: public pages only (no login, no paywalled data), real
browser headers, randomized human-like delays, tiny daily volume, and
honest backoff-and-retry when the site serves a transient block page.

Config via environment variables:
  CATEGORIES        Pipe-separated categories, semicolon-separated keywords
                    inside each. First keyword names the category.
                    Default: automation;n8n;make.com;zapier|python|customer support;email support;chat support|virtual assistant
  MAX_PER_CATEGORY  Jobs kept per category per run (default 1)
  WEBHOOK_URL       Make.com webhook to POST each job to (required unless DRY_RUN=1)
  DRY_RUN           Set to 1 to print payloads instead of sending them
"""
from datetime import datetime
from html import unescape
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

import requests

BASE_URL = 'https://www.onlinejobs.ph'
TODAY = datetime.now().strftime('%Y-%m-%d')

DEFAULT_CATEGORIES = 'automation;n8n;make.com;zapier|python|customer support;email support;chat support|virtual assistant'

SEEN_FILE = os.environ.get('SEEN_FILE', 'seen_jobs.json')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')


def _env_int(name, default):
  """Read an int env var, treating empty/unset as the default."""
  raw = (os.environ.get(name) or '').strip()
  try:
    return int(raw) if raw else default
  except ValueError:
    return default


MAX_PER_CATEGORY = _env_int('MAX_PER_CATEGORY', 1)
MAX_DESCRIPTION_CHARS = 600
MAX_HOWTO_CHARS = 300

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;q=0.9,'
        'image/avif,image/webp,*/*;q=0.8'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': BASE_URL + '/',
}


def load_categories(raw):
  """'automation;n8n|python|virtual assistant' -> [('automation', [..]), ('python', [..]), ...]"""
  categories = []
  for group in raw.split('|'):
    keywords = [k.strip().lower() for k in group.split(';') if k.strip()]
    if keywords:
      categories.append((keywords[0], keywords))
  return categories


def http_get(url, timeout=15):
  req = urllib.request.Request(url, headers=HEADERS)
  with urllib.request.urlopen(req, timeout=timeout) as response:
    return response.read().decode('utf-8')


def strip_tags(raw_html):
  # Unwrap anti-scraping <ojfilter> tags without losing the text inside them
  text = re.sub(r'<ojfilter[^>]*>', '', raw_html)
  text = text.replace('</ojfilter>', '')
  text = re.sub(r'<br\s*/?>', '\n', text)
  text = re.sub(r'</p>', '\n', text)
  text = re.sub(r'<[^>]+>', '', text)
  text = unescape(text)
  lines = [line.strip() for line in text.split('\n')]
  return re.sub(r'\n{2,}', '\n', '\n'.join(line for line in lines if line)).strip()


def parse_posted(block):
  """Card timestamp ('Posted on 2026-09-23 13:49:33') -> datetime, newest-first sorting."""
  match = re.search(r'Posted on\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', block)
  if not match:
    return None
  try:
    return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
  except ValueError:
    return None


def parse_listing_card(block):
  link_match = re.search(r'href="(/jobseekers/job/[^"]+)"', block)
  if not link_match:
    return None

  title_match = re.search(r'<h4 class="fs-16 fw-700">(.*?)</h4>', block, re.DOTALL)
  if not title_match:
    return None

  # The employment type badge sits inside the title heading; drop it first
  title_inner = re.sub(r'<span[^>]*>.*?</span>', '', title_match.group(1), flags=re.DOTALL)
  clean_title = strip_tags(title_inner)
  if not clean_title or len(clean_title) < 3:
    return None

  badge_match = re.search(r'<span class="badge[^"]*">\s*(.*?)\s*</span>', block, re.DOTALL)
  salary_match = re.search(r'<dd class="col">\s*(.*?)\s*</dd>', block, re.DOTALL)
  desc_match = re.search(
      r'<div class="desc fs-14 d-none d-sm-block">(.*?)</div>', block, re.DOTALL)
  company_match = re.search(r'<img[^>]+jobpost-cat-box-logo[^>]+alt="([^"]+)"', block)

  return {
      'url': BASE_URL + link_match.group(1),
      'title': clean_title,
      'employmentType': strip_tags(badge_match.group(1)) if badge_match else '',
      # Rate as shown on the card, e.g. "$444.50 PHP Per Hour"
      'rate': strip_tags(salary_match.group(1)) if salary_match else '',
      'summary': strip_tags(desc_match.group(1)) if desc_match else '',
      'company': company_match.group(1).strip() if company_match else '',
      'postedAt': parse_posted(block),
  }


def parse_search_results(html_content):
  listings = []
  for block in re.split(r'<!-- Start -->', html_content)[1:]:
    listing = parse_listing_card(block)
    if listing:
      listings.append(listing)
  # Most recent postings first; cards without a timestamp sink to the end
  listings.sort(key=lambda l: l['postedAt'] or datetime.min, reverse=True)
  return listings


def looks_like_bot_check(page_html):
  # Interstitial/block markers; note 'challenge-platform' also appears on
  # legitimate pages, so it must NOT be treated as a block signal by itself
  return any(
      marker in page_html
      for marker in ('Just a moment', 'Attention Required', 'cf-error-code')
  )


def fetch_full_description(job_url, attempts=4):
  for attempt in range(1, attempts + 1):
    try:
      page_html = http_get(job_url)
      match = re.search(r'<p id="job-description"[^>]*>(.*?)</p>', page_html, re.DOTALL)
      if match:
        description = strip_tags(match.group(1))
        if description:
          return description
      if looks_like_bot_check(page_html):
        print(f'Attempt {attempt}: bot-check page served instead of job page.')
      else:
        print(f'Attempt {attempt}: description block not found (page fetched).')
    except Exception as e:
      print(f'Attempt {attempt}: could not fetch {job_url}: {e}')
    if attempt < attempts:
      # Blocks are transient rate limits; waiting longer helps
      time.sleep(random.randint(10, 20))
  print(f'WARNING: full description unavailable for {job_url}; sending listing teaser.')
  return ''


def split_how_to_apply(description):
  """Peel the employer's 'How to Apply' section out of the description."""
  match = re.search(r'\bhow\s*to\s*apply\b[^:\n]*:?\s*', description, re.IGNORECASE)
  if not match or match.start() < 20:
    return description, ''
  how_to = description[match.end():].strip(' -\n')
  lead = description[:match.start()].rstrip(' -\n')
  return (lead or description), how_to


def truncate(text, limit):
  if len(text) <= limit:
    return text
  cut = text[:limit].rsplit(' ', 1)[0].rstrip()
  return (cut or text[:limit]) + ' …'


def fetch_search_results(target_url, attempts=3):
  for attempt in range(1, attempts + 1):
    try:
      listings = parse_search_results(http_get(target_url))
      if listings:
        return listings
      print(f'Attempt {attempt}: no listings parsed (page may have been blocked).')
    except Exception as e:
      print(f'Attempt {attempt}: could not fetch search results: {e}')
    if attempt < attempts:
      time.sleep(random.randint(8, 15))
  return []


def build_job(listing, category, full_description):
  description, how_to_apply = split_how_to_apply(full_description or listing['summary'])
  posted = listing['postedAt']
  return {
      'jobTitle': listing['title'],
      'company': listing['company'] or 'OnlineJobs.ph Employer',
      'category': category,
      # Both keys carry the card rate (e.g. "$444.50 PHP Per Hour");
      # 'salary' kept for backward compatibility with existing Make scenarios
      'rate': listing['rate'] or 'See listing',
      'salary': listing['rate'] or 'See listing',
      'employmentType': listing['employmentType'] or 'Remote',
      'url': listing['url'],
      # Real posting timestamp from the listing card - empty (never faked)
      # when the card hides it, so 'latest' judgements stay honest
      'datePosted': posted.strftime('%Y-%m-%d') if posted else '',
      'postedAt': posted.strftime('%Y-%m-%d %H:%M:%S') if posted else '',
      'description': truncate(description or f'Live scraped listing for {category}.',
                              MAX_DESCRIPTION_CHARS),
      'howToApply': truncate(how_to_apply, MAX_HOWTO_CHARS) if how_to_apply else '',
  }




def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen_set):
    try:
        with open(SEEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(seen_set), f, indent=2)
            f.write('\n')
    except Exception as e:
        print(f'Failed to save seen cache: {e}')


def summarize_job(job):
    """Use Gemini to produce a concise Discord-friendly summary. Fallback to raw fields."""
    if not GEMINI_API_KEY:
        return None
    prompt = (
        "Summarize this job listing in 2-4 sentences for a Discord post. "
        "Include role, key skills, and a one-line 'why it is interesting' hook. "
        "Do not invent details. Keep it concise and professional.\n\n"
        f"Title: {job.get('jobTitle','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Category: {job.get('category','')}\n"
        f"Rate: {job.get('rate','')}\n"
        f"Type: {job.get('employmentType','')}\n"
        f"Description: {job.get('description','')}\n"
        f"How to apply: {job.get('howToApply','')}"
    )
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}")
    try:
        resp = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=30)
        if resp.status_code != 200:
            print(f'Gemini error {resp.status_code}: {resp.text[:200]}')
            return None
        data = resp.json()
        text = (data.get('candidates', [{}])[0]
                .get('content', {}).get('parts', [{}])[0].get('text', ''))
        return text.strip() or None
    except Exception as e:
        print(f'Gemini request failed: {e}')
        return None


def send_discord(job, summary):
    if not DISCORD_WEBHOOK_URL:
        print('Error: DISCORD_WEBHOOK_URL is not set.')
        return False
    embed = {
        "title": job.get('jobTitle', 'Job listing'),
        "url": job.get('url'),
        "description": (summary or job.get('description', ''))[:4000],
        "fields": [
            {"name": "Category", "value": job.get('category', 'N/A'), "inline": True},
            {"name": "Rate", "value": job.get('rate', 'N/A'), "inline": True},
            {"name": "Type", "value": job.get('employmentType', 'N/A'), "inline": True},
            {"name": "Posted", "value": job.get('datePosted') or 'N/A', "inline": True},
        ],
    }
    how = (job.get('howToApply') or '').strip()
    if how:
        embed["fields"].append({"name": "How to apply", "value": how[:1024], "inline": False})
    payload = {"embeds": [embed]}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        if resp.status_code in (200, 204):
            print(f"Sent to Discord: {job.get('jobTitle')}")
            return True
        print(f"Discord failed {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"Discord request failed: {e}")
        return False


def fetch_jobs(categories):
  jobs = []
  seen_urls = set()

  for category, keywords in categories:
    picked = []
    for keyword in keywords:
      # Random short sleep between searches to look natural
      time.sleep(random.randint(5, 12))
      print(f'[{category}] searching: {keyword} ...')
      target_url = (f'{BASE_URL}/jobseekers/jobsearch?jobkeyword='
                    + urllib.parse.quote(keyword))
      try:
        listings = fetch_search_results(target_url)
      except Exception as e:
        print(f'Error scraping keyword {keyword}: {e}')
        continue

      for listing in listings:
        if listing['url'] in seen_urls:
          continue
        seen_urls.add(listing['url'])
        picked.append(listing)
        break  # newest listing for this keyword

    # Newest first across the category's keywords, capped per category
    picked.sort(key=lambda l: l['postedAt'] or datetime.min, reverse=True)
    picked = picked[:MAX_PER_CATEGORY]

    for listing in picked:
      # Polite pause before visiting each job page for the full description
      time.sleep(random.randint(2, 5))
      full_description = fetch_full_description(listing['url'])
      jobs.append(build_job(listing, category, full_description))
      print(f"[{category}] picked: {listing['title']} ({listing['url']})")

  return jobs


def main():
  dry_run = os.environ.get('DRY_RUN') == '1'
  if not DISCORD_WEBHOOK_URL and not dry_run:
    print("Error: DISCORD_WEBHOOK_URL environment variable is not set.")
    print("Set it to your Discord channel webhook URL.")
    print("Or set DRY_RUN=1 to preview payloads without sending.")
    sys.exit(1)

  categories = load_categories(os.environ.get('CATEGORIES') or DEFAULT_CATEGORIES)
  print(f'Categories: {", ".join(name for name, _ in categories)}'
        f' | max {MAX_PER_CATEGORY} per category')
  jobs = fetch_jobs(categories)

  if not jobs:
    print('No jobs found.')
    if dry_run:
      return
    # Fallback safety net so downstream automations never stall
    jobs.append({
        'jobTitle': 'Job Scraper Fallback',
        'company': 'OnlineJobs.ph Direct',
        'category': 'fallback',
        'rate': 'Competitive',
        'salary': 'Competitive',
        'employmentType': 'Remote',
        'url': f'{BASE_URL}/jobseekers/jobsearch?jobkeyword=automation',
        'datePosted': TODAY,
        'postedAt': '',
        'description': 'Live check finished. Click to view all live matches.',
        'howToApply': '',
    })

  seen = load_seen()
  new_jobs = [j for j in jobs if j.get('url') not in seen]

  if not new_jobs:
    print('No new jobs found.')
    if not dry_run and DISCORD_WEBHOOK_URL:
      requests.post(DISCORD_WEBHOOK_URL, json={
          "content": "No new job listings this run."
      }, timeout=30)
    return

  print(f'Sending {len(new_jobs)} new jobs to Discord...')
  for job in new_jobs:
    if dry_run:
      print(json.dumps(job, indent=2))
      summary = summarize_job(job)
      if summary:
        print(f"AI summary: {summary}")
      continue
    summary = summarize_job(job)
    if send_discord(job, summary):
      if job.get('url'):
        seen.add(job['url'])
        save_seen(seen)
    time.sleep(1.5)


if __name__ == '__main__':
  main()
