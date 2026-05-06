import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

from bitbucket_creds_checker import make_auth_header


workspace = os.getenv('BITBUCKET_WORKSPACE')
seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S%z')

headers = make_auth_header()


def get_repositories():
    next_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}"
    while next_url:
        response = requests.get(next_url, headers=headers)
        print(response.status_code)
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Failed to decode JSON for repositories page")
            break
        for repo in response_data.get('values', []):
            print(repo['full_name'])
            yield repo
        next_url = response_data.get('next', None)


def get_commits(repo_slug):
    next_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/commits?since={seven_days_ago}"
    while next_url:
        response = requests.get(next_url, headers=headers)
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Failed to decode JSON for {repo_slug}")
            break
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
