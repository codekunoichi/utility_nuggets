# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A collection of utility tools for auditing and analytics:
- **`jira_audit/`** — Read-only Jira project sprawl auditor (classifies projects as active/slow/stale/overloaded/dormant)
- **`slack_audit/`** — Read-only Slack channel auditor + deployment digest generator
- **`bitbucket/`** — Bitbucket workspace analytics scripts (commit activity, contributor heat map, engineer footprint)
- **`mssql/`** — SQL Server introspection query templates
- **`csv_manipulation/`** — CSV processing utilities

## Environment Setup

Each Python project uses its own isolated virtual environment:

```bash
cd <project>           # jira_audit, slack_audit, or bitbucket
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in credentials (jira_audit, slack_audit)
```

**Bitbucket scripts** read credentials directly from environment variables (no `.env.example` — copy `.env` from a teammate or create it manually):

```
BITBUCKET_USERNAME=your_email@company.com
BITBUCKET_TOKEN=your_api_token_with_scopes
BITBUCKET_WORKSPACE=your_workspace_slug
```

Create the token at: Bitbucket > Account settings > API tokens > **Create API token with scopes**, with `read:repository:bitbucket` scope. Always verify credentials first:

```bash
cd bitbucket && source venv/bin/activate
set -a && source .env && set +a
python3 bitbucket_creds_checker.py
```

## Running the Tools

```bash
# Jira audit
cd jira_audit && source venv/bin/activate
python main.py [--days 30] [--output-dir reports] [--formats csv json] [--verbose]

# Slack workspace audit
cd slack_audit && source venv/bin/activate
python main.py [--days 30] [--output-dir reports] [--formats csv json] [--no-private] [--verbose]

# Deployment digest
cd slack_audit && source venv/bin/activate
python digest_main.py [--days 7] [--deployment-channel C0123...] [--impact-channel C0456...] [--verbose]

# Bitbucket — always run from bitbucket/ with venv + .env loaded:
cd bitbucket && source venv/bin/activate && set -a && source .env && set +a

python3 bitbucket_creds_checker.py                          # verify credentials
python3 repo_activity.py [--days 30] [--top 20] [--output csv|json|both] [--output-dir ./output]
python3 heat_map.py [--days 30] [--output-dir ./output] [--delay 0.5]
python3 stats_counter.py                                    # commits per author, last 7 days
python3 counter.py                                          # commits per repo/author for a given year
```

## Running Tests

```bash
# All tests in a project
cd jira_audit && source venv/bin/activate && pytest tests/ -v

# Single test file
pytest tests/test_classifier.py -v

# Single test
pytest tests/test_classifier.py::TestClassName::test_method_name -v
```

## Architecture

Both `jira_audit` and `slack_audit` follow the same structure:

```
<project>/
├── main.py               # Entry point: CLI args → config → API loop → classify → report
├── src/<project>/
│   ├── config.py         # Loads .env + validates; credentials never appear in repr/logs
│   ├── api.py            # API client (Jira REST / Slack SDK)
│   ├── classifier.py     # Bucket assignment logic (thresholds are configurable via env)
│   ├── models.py         # Dataclasses (ProjectRecord / ChannelRecord)
│   └── reporter.py       # CSV/JSON file output + console summary
└── tests/                # pytest; uses unittest.mock.patch for env var injection
```

`slack_audit` additionally has a `deployment_digest/` subpackage under `src/slack_audit/`:
- `fetcher.py` — paginated Slack message retrieval
- `parser.py` — regex-based extraction of deployment events from bot messages (GitHub Actions, ArgoCD, Jenkins, generic)
- `correlator.py` — time-proximity matching of deployments to impact events (default 30-minute window)
- `reporter.py` — Markdown digest output

### Bitbucket scripts structure

```
bitbucket/
├── bitbucket_creds_checker.py  # Shared auth helper; run directly to test credentials
├── repo_activity.py            # Ranks repos by commit count over a time window
├── heat_map.py                 # Engineer footprint: author×repo commit matrix + risk summary
├── stats_counter.py            # Commits per author over last 7 days
├── counter.py                  # Commits per repo and author for a given year
├── organize_author_repos.py    # Post-processes counter.py output (reads count_stats.txt)
├── requirements.txt
└── .env                        # gitignored; holds BITBUCKET_USERNAME/TOKEN/WORKSPACE
```

All scripts import `make_auth_header()` from `bitbucket_creds_checker`. Auth uses Basic auth with `username:api_token` (Bitbucket API tokens with scopes, the replacement for app passwords). `heat_map.py` has a built-in `--delay` param and 429 retry backoff to avoid rate limiting across 180+ repos.

### Key Design Constraints
- **Read-only:** No tool writes back to Jira, Slack, or Bitbucket.
- **Config validation at startup:** `config.load_config()` raises immediately on missing required vars so runs never fail mid-way.
- **CLI overrides env:** All `.env` thresholds can be overridden via CLI flags without editing the file.
- **Output goes to `reports/`** (jira/slack) or `output/`** (bitbucket), both gitignored.
