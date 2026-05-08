"""
heat_map.py
-----------
Produces two CSV files for Power BI:

1. contributor_heatmap.csv
   One row per author-repo combination.
   Columns: author, repo, commits, last_commit_date, days_since_last_commit, recency_color

2. repo_risk_summary.csv
   One row per repository.
   Columns: repo, total_commits, unique_contributors, single_contributor_risk,
            days_since_any_commit, recency_color

Usage:
    export BITBUCKET_USERNAME="your_email"
    export BITBUCKET_TOKEN="your_api_token"
    export BITBUCKET_WORKSPACE="your_workspace_slug"

    python heat_map.py --days 30 --output-dir ./output
    python heat_map.py --days 30 --output-dir ./output --delay 0.3
"""

import os
import time
import argparse
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import requests

from bitbucket_creds_checker import make_auth_header


# ── Rate-limited API helper ───────────────────────────────────────────────────

def api_get(url, headers, delay, max_retries=4):
    time.sleep(delay)
    for attempt in range(max_retries):
        r = requests.get(url, headers=headers)
        if r.status_code == 429:
            wait = 10 * (2 ** attempt)
            print(f"\n  [rate limit] waiting {wait}s before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait)
            continue
        return r
    r.raise_for_status()
    return r


# ── Bitbucket API helpers ─────────────────────────────────────────────────────

def get_repositories(workspace, headers, delay):
    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}?pagelen=100"
    while url:
        r = api_get(url, headers, delay)
        r.raise_for_status()
        data = r.json()
        yield from data.get("values", [])
        url = data.get("next")


def get_commits_since(workspace, repo_slug, since_dt, headers, delay):
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    url = (
        f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"
        f"/commits?pagelen=100&q=date>%3D%22{since_iso}%22"
    )
    while url:
        r = api_get(url, headers, delay)
        if r.status_code == 404:
            return
        r.raise_for_status()
        try:
            data = r.json()
        except Exception:
            print(f"  [warn] JSON decode error for {repo_slug}")
            return
        for c in data.get("values", []):
            raw = c.get("author", {}).get("raw", "unknown")
            user_obj = c.get("author", {}).get("user", {})
            display = user_obj.get("display_name") or user_obj.get("nickname") or raw
            try:
                commit_dt = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
            except Exception:
                commit_dt = None
            yield {"date": commit_dt, "author_display": display}
        url = data.get("next")


# ── Recency color ─────────────────────────────────────────────────────────────

def recency_color(days_since):
    if days_since is None:
        return "Red"
    if days_since <= 14:
        return "Green"
    if days_since <= 45:
        return "Amber"
    return "Red"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bitbucket contributor heat map")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--output-dir", default="./output", help="Output directory for CSVs")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds to wait between API requests to avoid rate limiting (default: 0.5)")
    args = parser.parse_args()

    workspace = os.getenv("BITBUCKET_WORKSPACE")
    if not workspace:
        raise EnvironmentError("BITBUCKET_WORKSPACE is not set")

    headers = make_auth_header()
    since_dt = datetime.now(timezone.utc) - timedelta(days=args.days)
    now = datetime.now(timezone.utc)

    print(f"\n{'='*60}")
    print(f"  Bitbucket Contributor Heat Map")
    print(f"  Workspace : {workspace}")
    print(f"  Window    : last {args.days} days (since {since_dt.strftime('%Y-%m-%d')})")
    print(f"  API delay : {args.delay}s between requests")
    print(f"{'='*60}\n")

    os.makedirs(args.output_dir, exist_ok=True)

    # heatmap[author][repo] = {commits, last_commit_date}
    heatmap = defaultdict(lambda: defaultdict(lambda: {"commits": 0, "last_commit_date": None}))
    repo_meta = {}

    repos = list(get_repositories(workspace, headers, args.delay))
    print(f"  Found {len(repos)} repositories\n")

    for i, repo in enumerate(repos, 1):
        slug = repo["slug"]
        full_name = repo["full_name"]
        print(f"  [{i}/{len(repos)}] {full_name} ...", end=" ", flush=True)

        commit_count = 0
        latest_commit_dt = None

        for commit in get_commits_since(workspace, slug, since_dt, headers, args.delay):
            commit_count += 1
            author = commit["author_display"]
            cell = heatmap[author][full_name]
            cell["commits"] += 1
            if commit["date"]:
                if cell["last_commit_date"] is None or commit["date"] > cell["last_commit_date"]:
                    cell["last_commit_date"] = commit["date"]
                if latest_commit_dt is None or commit["date"] > latest_commit_dt:
                    latest_commit_dt = commit["date"]

        days_since_any = (now - latest_commit_dt).days if latest_commit_dt else None
        repo_meta[full_name] = {
            "total_commits": commit_count,
            "days_since_any_commit": days_since_any,
        }
        print(f"{commit_count} commits")

    # ── Write CSV 1: Contributor Heat Map ─────────────────────────────────────

    heatmap_path = os.path.join(args.output_dir, "contributor_heatmap.csv")
    heatmap_rows = []

    for author, repos_data in heatmap.items():
        for repo_name, cell in repos_data.items():
            last_dt = cell["last_commit_date"]
            days_since = (now - last_dt).days if last_dt else None
            heatmap_rows.append({
                "author": author,
                "repo": repo_name,
                "commits": cell["commits"],
                "last_commit_date": last_dt.strftime("%Y-%m-%d") if last_dt else "",
                "days_since_last_commit": days_since if days_since is not None else "",
                "recency_color": recency_color(days_since),
            })

    heatmap_rows.sort(key=lambda r: (r["author"], -r["commits"]))

    with open(heatmap_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "author", "repo", "commits", "last_commit_date",
            "days_since_last_commit", "recency_color"
        ])
        writer.writeheader()
        writer.writerows(heatmap_rows)

    print(f"\n  Saved: {heatmap_path}")

    # ── Write CSV 2: Repo Risk Summary ────────────────────────────────────────

    risk_path = os.path.join(args.output_dir, "repo_risk_summary.csv")
    risk_rows = []

    for repo_name, meta in repo_meta.items():
        contributors = [
            a for a, rd in heatmap.items()
            if repo_name in rd and rd[repo_name]["commits"] > 0
        ]
        unique_count = len(contributors)
        single_risk = "YES" if unique_count == 1 else ("NONE" if unique_count == 0 else "No")
        color = recency_color(meta["days_since_any_commit"])

        risk_rows.append({
            "repo": repo_name,
            "total_commits": meta["total_commits"],
            "unique_contributors": unique_count,
            "single_contributor_risk": single_risk,
            "days_since_any_commit": meta["days_since_any_commit"] if meta["days_since_any_commit"] is not None else "no commits",
            "recency_color": color,
        })

    risk_rows.sort(key=lambda r: (0 if r["single_contributor_risk"] == "YES" else 1, -r["total_commits"]))

    with open(risk_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "repo", "total_commits", "unique_contributors",
            "single_contributor_risk", "days_since_any_commit", "recency_color"
        ])
        writer.writeheader()
        writer.writerows(risk_rows)

    print(f"  Saved: {risk_path}")

    # ── Console summary ───────────────────────────────────────────────────────

    single_risk_repos = [r for r in risk_rows if r["single_contributor_risk"] == "YES"]
    inactive_repos = [r for r in risk_rows if r["recency_color"] == "Red"]

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Repos scanned          : {len(repos)}")
    print(f"  Active repos (commits) : {sum(1 for r in risk_rows if r['total_commits'] > 0)}")
    print(f"  Unique contributors    : {len(heatmap)}")
    print(f"  Single-contributor risk: {len(single_risk_repos)} repos")
    print(f"  Inactive (>45 days)    : {len(inactive_repos)} repos")

    if single_risk_repos:
        print(f"\n  Single-contributor repos:")
        for r in single_risk_repos[:10]:
            print(f"     {r['repo']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
