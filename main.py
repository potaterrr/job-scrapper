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
  # Define your keywords list here
  keywords = ['automation', 'n8n', 'make.com', 'zapier']
  jobs = []

  for keyword in keywords:
    # Add a short random sleep between each keyword search to look natural
    delay = random.randint(5, 12)
    time.sleep(delay)

    print(f'Fetching live listings for keyword: {keyword}...')
    target_url = f'https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword={urllib.parse.quote(keyword)}'
    
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
            ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }

    try:
      req = urllib.request.Request(target_url, headers=headers)
      with urllib.request.urlopen(req, timeout=15) as response:
        html_content = response.read().decode('utf-8')

        # Use regex to find job links and titles safely
        pattern = r'<a[^>]+href="(/jobseekers/job/[^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html_content, re.DOTALL)

        keyword_count = 0
        for link, title_html in matches:
          clean_title = re.sub(r'<[^>]+>', '', title_html).strip()
          if not clean_title or len(clean_title) < 3:
            continue

          full_link = 'https://www.onlinejobs.ph' + link

          # Avoid duplicate entries across keywords
          if not any(j['url'] == full_link for j in jobs):
            jobs.append({
                'jobTitle': clean_title,
                'company': 'OnlineJobs.ph Employer',
                'salary': 'View Listing',
                'employmentType': 'Remote',
                'url': full_link,
                'datePosted': todays_date,
                'description': f'Live scraped listing for keyword: {keyword}',
            })
            keyword_count += 1

          # Limit to top 3 jobs per keyword to prevent spamming Telegram
          if keyword_count >= 3:
            break
            
    except Exception as e:
      print(f'Error scraping keyword {keyword}: {e}')

  # Fallback safety net if no jobs are returned
  if not jobs:
    print('Using dynamic fallback job link...')
    jobs.append({
        'jobTitle': 'Automation & Workflow Specialist (Fallback)',
        'company': 'OnlineJobs.ph Direct',
        'salary': 'Competitive',
        'employmentType': 'Full Time',
        'url': 'https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword=automation',
        'datePosted': todays_date,
        'description': 'Live check finished. Click to view all live matches.',
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
