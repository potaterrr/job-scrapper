from datetime import datetime
import os
import random
import time
import requests

# Your Make.com Webhook URL
webhook_url = os.environ.get('WEBHOOK_URL')
todays_date = datetime.now().strftime('%Y-%m-%d')


def fetch_jobs():
  # Add a random sleep between 10 and 60 seconds to look natural and avoid bot blocks
  delay = random.randint(10, 60)
  print(f'Waiting {delay} seconds before starting...')
  time.sleep(delay)

  print('Fetching live automation job listings...')

  # Example live payload structure
  jobs = [
      {
          'jobTitle': 'Python & Make.com Automation Specialist',
          'company': 'CloudScale Remote',
          'salary': '$2,000 / month',
          'employmentType': 'Full Time',
          'url': 'https://www.onlinejobs.ph/jobseekers/job/automation-specialist',
          'datePosted': todays_date,
          'description': (
              'Looking for an expert to manage automated pipelines,'
              ' webhooks, and AI integrations.'
          ),
      }
  ]
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
