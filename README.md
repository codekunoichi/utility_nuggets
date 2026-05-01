# utility_nuggets

A collection of utility tools for auditing and analytics across Jira, Slack, Bitbucket, SQL Server, and CSV data.

## Tools

### `jira_audit/` — Jira Project Sprawl Auditor
Read-only auditor that classifies Jira projects as **active**, **slow**, **stale**, **overloaded**, or **dormant** based on configurable activity thresholds.

```bash
cd jira_audit && source venv/bin/activate
python main.py [--days 30] [--output-dir reports] [--formats csv json] [--verbose]
```

### `slack_audit/` — Slack Channel Auditor + Deployment Digest
Two tools in one:
- **Channel auditor** — classifies Slack channels by activity level
- **Deployment digest** — correlates deployment events (GitHub Actions, ArgoCD, Jenkins) with impact events using time-proximity matching

```bash
cd slack_audit && source venv/bin/activate

# Channel audit
python main.py [--days 30] [--output-dir reports] [--formats csv json] [--no-private] [--verbose]

# Deployment digest
python digest_main.py [--days 7] [--deployment-channel C0123...] [--impact-channel C0456...] [--verbose]
```

### `bitbucket/` — Bitbucket Workspace Analytics

| Script | Description |
|---|---|
| `repo_activity.py` | Ranks all repos by commit count over a configurable window |
| `counter.py` | Counts commits per repo and per author for a given year |
| `stats_counter.py` | Counts commits per author over the last 7 days |
| `organize_author_repos.py` | Post-processes `counter.py` output to sort authors and repos |

**`repo_activity.py` — rank repos by activity:**
```bash
export BITBUCKET_CREDS=username:app_password
export BITBUCKET_WORKSPACE=myworkspace

python bitbucket/repo_activity.py                        # last 30 days, all repos
python bitbucket/repo_activity.py --days 90 --top 10    # last 90 days, top 10 only
python bitbucket/repo_activity.py --output both --output-dir reports/
```

### `mssql/` — SQL Server Introspection Queries
Ready-to-run SQL templates for exploring SQL Server schemas:
- List tables with row counts and activity stats
- List columns with key and index metadata

### `csv_manipulation/` — CSV Processing Utilities
Scripts for merging and deduplicating CSV data.

## Environment Setup

Each Python project uses its own isolated virtual environment:

```bash
cd <project>           # jira_audit or slack_audit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
```

Bitbucket scripts read credentials directly from environment variables — no `.env` file needed:

```bash
export BITBUCKET_CREDS=username:app_password
export BITBUCKET_WORKSPACE=your_workspace_slug
```

## Running Tests

```bash
cd jira_audit && source venv/bin/activate && pytest tests/ -v
cd slack_audit && source venv/bin/activate && pytest tests/ -v
```
