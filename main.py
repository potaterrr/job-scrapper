from datetime import datetime
import os
import random
import re
import time
import urllib.parse
import urllib.request
import sys
from html import unescape

import requests

webhook_url = os.environ.get('WEBHOOK_URL')
todays_date = datetime.now().strftime('%Y-%m-%d')

# Define your keywords list here
KEYWORDS = ['automation', 'n8n', 'make.com', 'zapier']

MAX_JOBS_PER_KEYWORD = 1  # One job per keyword keeps the Make.com queue light
DESCRIPTION_MAX_CHARS = 600

BASE_URL = 'https://www.onlinejobs.ph'
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
}


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


def truncate(text, limit=DESCRIPTION_MAX_CHARS):
  if len(text) <= limit:
    return text
  cut = text[:limit].rsplit(' ', 1)[0].rstrip(' \n')
  return cut + '\u2026'


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
      'salary': strip_tags(salary_match.group(1)) if salary_match else '',
      'summary': strip_tags(desc_match.group(1)) if desc_match else '',
      'company': company_match.group(1).strip() if company_match else '',
  }


def parse_search_results(html_content):
  listings = []
  for block in re.split(r'<!-- Start -->', html_content)[1:]:
    listing = parse_listing_card(block)
    if listing:
      listings.append(listing)
  return listings


def fetch_full_description(job_url):
  try:
    page_html = http_get(job_url)
    match = re.search(r'<p id="job-description"[^>]*>(.*?)</p>', page_html, re.DOTALL)
    if match:
      return strip_tags(match.group(1))
  except Exception as e:
    print(f'Could not fetch job details for {job_url}: {e}')
  return ''


def fetch_jobs():
  jobs = []
  seen_urls = set()

  for keyword in KEYWORDS:
    # Add a short random sleep between each keyword search to look natural
    delay = random.randint(5, 12)
    time.sleep(delay)

    print(f'Fetching live listings for keyword: {keyword}...')
    target_url = f'{BASE_URL}/jobseekers/jobsearch?jobkeyword={urllib.parse.quote(keyword)}'

    try:
      listings = parse_search_results(http_get(target_url))
    except Exception as e:
      print(f'Error scraping keyword {keyword}: {e}')
      continue

    keyword_count = 0
    for listing in listings:
      if keyword_count >= MAX_JOBS_PER_KEYWORD:
        break

      # Avoid duplicate entries across keywords
      if listing['url'] in seen_urls:
        continue
      seen_urls.add(listing['url'])

      # Polite pause before visiting each job page for the full description
      time.sleep(random.randint(2, 5))
      full_description = fetch_full_description(listing['url'])
      description = full_description or listing['summary'] or \
          f'Live scraped listing for keyword: {keyword}'

      jobs.append({
          'jobTitle': listing['title'],
          'company': listing['company'] or 'OnlineJobs.ph Employer',
          'salary': listing['salary'] or 'View Listing',
          'employmentType': listing['employmentType'] or 'Remote',
          'url': listing['url'],
          'datePosted': todays_date,
          'description': truncate(description),
      })
      keyword_count += 1

  # Fallback safety net if no jobs are returned
  if not jobs:
    print('Using dynamic fallback job link...')
    jobs.append({
        'jobTitle': 'Automation & Workflow Specialist (Fallback)',
        'company': 'OnlineJobs.ph Direct',
        'salary': 'Competitive',
        'employmentType': 'Full Time',
        'url': f'{BASE_URL}/jobseekers/jobsearch?jobkeyword=automation',
        'datePosted': todays_date,
        'description': 'Live check finished. Click to view all live matches.',
    })

  return jobs


if __name__ == '__main__':
  if not webhook_url:
    print("Error: WEBHOOK_URL environment variable is not set.")
    print("Set it to your Make.com webhook URL, e.g.:")
    print('  export WEBHOOK_URL="https://hook.us2.make.com/your-hook-id"')
    sys.exit(1)
  jobs = fetch_jobs()
  if not jobs:
    print('No jobs found.')
  else:
    print(f'Sending {len(jobs)} jobs to Make.com...')
    for job in jobs:
      response = requests.post(webhook_url, json=job)
      print(f"Sent: {job['jobTitle']} | Status: {response.status_code}")
