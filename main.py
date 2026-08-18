from datetime import datetime
import os
import random
import re
import time
import urllib.request
import json
import requests

webhook_url = 'https://hook.us2.make.com/x6o3kicj053whas3fg7oj775xa51mvey'
todays_date = datetime.now().strftime('%Y-%m-%d')


def fetch_jobs():
  # Add a random sleep to look natural and avoid bot blocks
  delay = random.randint(10, 30)
  print(f'Waiting {delay} seconds before starting...')
  time.sleep(delay)

  print('Fetching live automation job listings from OnlineJobs.ph...')

  target_url = (
      'https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword=automation'
  )
  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
          ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
      )
  }

  jobs = []
  try:
    req = urllib.request.Request(target_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
      html_content = response.read().decode('utf-8')

      # Use regex to find job links and titles safely without external parsers
      # Matching links that look like /jobseekers/job/...
      pattern = r'<a[^>]+href="(/jobseekers/job/[^"]+)"[^>]*>(.*?)</a>'
      matches = re.findall(pattern, html_content, re.DOTALL)

      for link, title_html in matches:
        # Clean up HTML tags from the title string
        clean_title = re.sub(r'<[^>]+>', '', title_html).strip()
        if not clean_title or len(clean_title) < 3:
          continue

        full_link = 'https://www.onlinejobs.ph' + link

        # Avoid duplicates
        if not any(j['url'] == full_link for j in jobs):
          jobs.append({
              'jobTitle': clean_title,
              'company': 'OnlineJobs.ph Employer',
              'salary': 'View Listing',
              'employmentType': 'Remote',
              'url': full_link,
              'datePosted': todays_date,
              'description': (
                  'Live scraped listing from OnlineJobs.ph search results.'
              ),
          })
        if len(jobs) >= 5:  # Limit to top 5 jobs per run
          break
  except Exception as e:
    print(f'Error scraping OnlineJobs.ph: {e}')

  # Fallback safety net if layout changes or structure blocks scraper
  if not jobs:
    print('Using dynamic fallback job link...')
    jobs.append({
        'jobTitle': 'Python & Automation Specialist (Fallback)',
        'company': 'OnlineJobs.ph Direct',
        'salary': 'Competitive',
        'employmentType': 'Full Time',
        'url': 'https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword=python',
        'datePosted': todays_date,
        'description': (
            'Live scrape check finished. Click to view all live automation'
            ' matches.'
        ),
    })

  return jobs


if __name__ == '__main__':
  jobs = fetch_jobs()
  if not jobs:
    print('No jobs found.')
  else:
    print(f'Sending {len(jobs)} jobs to Make.com...')
    for job in jobs:
      response = requests.post(webhook_url, json=job)
      print(f"Sent: {job['jobTitle']} | Status: {response.status_code}")
