import os
import requests
import base64
from datetime import datetime, timedelta
from collections import defaultdict

login_string = os.getenv('BITBUCKET_CREDS') 
workspace = os.getenv('BITBUCKET_WORKSPACE')
login_string_bytes = login_string.encode("ascii")
base64_login_bytes = base64.b64encode(login_string_bytes)
base64_string = base64_login_bytes.decode("ascii")

# Calculate the date 7 days ago
seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S%z')

def get_repositories():
    next_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}"
    while next_url:
        response = requests.get(next_url, headers={'Authorization': 'Basic {base64_string}'.format(base64_string=base64_string)})
        print(response.status_code)
        
        #response_data = response.json()
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Failed to decode JSON for {repo_slug}")
            continue
        for repo in response_data.get('values', []):
            print(repo['full_name'])
            yield repo
        next_url = response_data.get('next', None)

def get_commits(repo_slug):
    next_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/commits?since={seven_days_ago}"
    while next_url:
        response = requests.get(next_url, headers={'Authorization': 'Basic {base64_string}'.format(base64_string=base64_string)})
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Failed to decode JSON for {repo_slug}")
            continue
        for commit in response_data.get('values', []):
            yield commit
        next_url = response_data.get('next', None)

if __name__ == '__main__':
    user_commits_count = defaultdict(int)

    for repo in get_repositories():
        repo_slug = repo['slug']
        for commit in get_commits(repo_slug):
            user_commits_count[commit['author']['raw']] += 1

    for user, count in user_commits_count.items():
        print(f"User: {user}, Commits in the last 7 days: {count}")
