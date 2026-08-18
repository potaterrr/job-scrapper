from datetime import datetime
import os
import random
import time
from bs4 import BeautifulSoup
import requests

webhook_url = os.environ.get('WEBHOOK_URL')
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
    response = requests.get(target_url, headers=headers, timeout=15)
    if response.status_code == 200:
      soup = BeautifulSoup(response.text, 'html.parser')

      # Locate job items on OnlineJobs.ph search results
      # (Targeting individual rows/cards on the search result table)
      job_rows = soup.select(
          'tr'
      )  # Fallback broad selector or specific table rows

      for row in job_rows:
        link_elem = row.select_one('a[href*="/jobseekers/job/"]')
        if link_elem:
          title = link_elem.get_text(strip=True)
          link = link_elem['href']
          if not link.startswith('http'):
            link = 'https://www.onlinejobs.ph' + link

          # Avoid duplicate entries
          if not any(j['url'] == link for j in jobs):
            jobs.append({
                'jobTitle': title if title else 'Automation Role',
                'company': 'OnlineJobs.ph Employer',
                'salary': 'View Listing',
                'employmentType': 'Remote',
                'url': link,
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
