import os
import requests
import dateutil.parser
import base64
import math


# Configuration
year = 2023
login_string = os.getenv('BITBUCKET_CREDS') 
workspace = os.getenv('BITBUCKET_WORKSPACE')
# By a lot of repo's 100 is recommended because of the rate limit of the API
pagelen = 100

# vars
totalCommits = 0
commitCount = 0
commits = []

print("")
print("Stats for {year}".format(year=year))
print("")


login_string_bytes = login_string.encode("ascii")
base64_login_bytes = base64.b64encode(login_string_bytes)
base64_string = base64_login_bytes.decode("ascii")
r = requests.get('https://api.bitbucket.org/2.0/repositories/{workspace}/?q=updated_on>="{year}-06-01"&pagelen={pagelen}'.format(
    year=year, workspace=workspace, pagelen=pagelen), headers={'Authorization': 'Basic {base64_string}'.format(base64_string=base64_string)})

counterPages = 0
commitsAuthors = {}
repoCommits = {}
repos = r.json()
amountOfPages = math.ceil(repos['size'] / pagelen)
totalSize = repos['size']

while counterPages < amountOfPages:
    counterPages += 1
    for repo in repos["values"]:
        commitLink = repo["links"]["commits"]["href"] + \
            '?pagelen={pagelen}'.format(pagelen=pagelen)
        repoSlug = repo["slug"]

        # print(repoSlug)
        # continue
        r = requests.get(commitLink,
                         headers={'Authorization': 'Basic {base64_string}'.format(base64_string=base64_string)})
        try:
            c = r.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Failed to decode JSON for {repoSlug}")
            continue
        commits.extend(c['values'])
        while 'next' in c:
            # print("next page")
            r = requests.get("{next}".format(next=c['next']),
                             headers={'Authorization': 'Basic {base64_string}'.format(base64_string=base64_string)})
            try:
                c = r.json()
            except requests.exceptions.JSONDecodeError:
                print(f"Failed to decode JSON for {repoSlug}")
                continue
            commits.extend(c['values'])

        for commit in commits:
            # print("count commit")
            commitDate = dateutil.parser.parse(commit['date'])
            if commitDate.year == year:
                commitCount += 1
                if commit['author']['raw'] in commitsAuthors:
                    commitsAuthors[commit['author']['raw']] += 1
                else:
                    commitsAuthors[commit['author']['raw']] = 1
        if (commitCount >= 1):
            repoCommits['{workspace}/{repo}'.format(
                repo=repoSlug)] = commitCount
            print("Total authors: {authors}".format(authors=commitsAuthors))
            print(
                "Total commits in {workspace}/{repo}: {count}".format(repo=repoSlug, count=commitCount))
        totalCommits += commitCount
        # reset counters
        commitCount = 0
        commits = []

    if "next" in repos and repos['next'] is not None:
        r = requests.get("{next}".format(next=repos['next']), headers={
                         'Authorization': 'Basic {base64_string}'.format(base64_string=base64_string)})
        repos = r.json()


print("")
print("Total overall commits: {count}".format(count=totalCommits))
print("Total authors: {authors}".format(authors=commitsAuthors))
print("Total repoCommits: {authors}".format(authors=repoCommits))
print("")
