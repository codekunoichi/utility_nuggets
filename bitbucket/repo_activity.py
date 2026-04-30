import os
import base64
import argparse
import csv
import json
from datetime import datetime, timedelta, timezone

import requests


def make_auth_header():
    login_string = os.getenv("BITBUCKET_CREDS")
    if not login_string:
        raise EnvironmentError("BITBUCKET_CREDS environment variable is not set")
    encoded = base64.b64encode(login_string.encode("ascii")).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def get_repositories(workspace, headers):
    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}?pagelen=100"
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        yield from data.get("values", [])
        url = data.get("next")


def count_commits(workspace, repo_slug, since_iso, headers):
    url = (
        f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"
        f"/commits?pagelen=100&q=date>%3D%22{since_iso}%22"
    )
    count = 0
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return 0
        response.raise_for_status()
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"  [warn] Failed to decode JSON for {repo_slug}")
            return count
        values = data.get("values", [])
        count += len(values)
        url = data.get("next")
    return count


def save_csv(rows, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "repository", "commits"])
        writer.writeheader()
        writer.writerows(rows)


def save_json(rows, path):
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Rank Bitbucket repositories by commit activity."
    )
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--top", type=int, default=None, help="Show only top N repos")
    parser.add_argument("--output", choices=["csv", "json", "both"], default=None, help="Save results to file")
    parser.add_argument("--output-dir", default=".", help="Directory for output files (default: current dir)")
    args = parser.parse_args()

    workspace = os.getenv("BITBUCKET_WORKSPACE")
    if not workspace:
        raise EnvironmentError("BITBUCKET_WORKSPACE environment variable is not set")

    headers = make_auth_header()
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    print(f"\nFetching repositories for workspace: {workspace}")
    print(f"Counting commits since: {since.strftime('%Y-%m-%d')} ({args.days} days)\n")

    repo_counts = {}
    for repo in get_repositories(workspace, headers):
        slug = repo["slug"]
        full_name = repo["full_name"]
        print(f"  Scanning {full_name} ...", end=" ", flush=True)
        count = count_commits(workspace, slug, since_iso, headers)
        print(count)
        repo_counts[full_name] = count

    sorted_repos = sorted(repo_counts.items(), key=lambda x: x[1], reverse=True)
    if args.top:
        sorted_repos = sorted_repos[: args.top]

    print("\n" + "=" * 55)
    print(f"  {'RANK':<6} {'REPOSITORY':<35} {'COMMITS':>7}")
    print("=" * 55)
    rows = []
    for rank, (repo, count) in enumerate(sorted_repos, start=1):
        print(f"  {rank:<6} {repo:<35} {count:>7}")
        rows.append({"rank": rank, "repository": repo, "commits": count})
    print("=" * 55)
    print(f"\n  Total repositories scanned: {len(repo_counts)}")
    print(f"  Total commits in window:    {sum(repo_counts.values())}\n")

    if args.output:
        os.makedirs(args.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.output in ("csv", "both"):
            path = os.path.join(args.output_dir, f"repo_activity_{timestamp}.csv")
            save_csv(rows, path)
            print(f"  Saved CSV: {path}")
        if args.output in ("json", "both"):
            path = os.path.join(args.output_dir, f"repo_activity_{timestamp}.json")
            save_json(rows, path)
            print(f"  Saved JSON: {path}")
        print()


if __name__ == "__main__":
    main()
