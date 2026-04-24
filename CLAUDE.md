# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A collection of utility tools for auditing and analytics:
- **`jira_audit/`** — Read-only Jira project sprawl auditor (classifies projects as active/slow/stale/overloaded/dormant)
- **`slack_audit/`** — Read-only Slack channel auditor + deployment digest generator
- **`bitbucket/`** — Bitbucket workspace analytics script
- **`mssql/`** — SQL Server introspection query templates
- **`csv_manipulation/`** — CSV processing utilities

## Environment Setup

Each Python project (`jira_audit/`, `slack_audit/`) uses its own isolated virtual environment:

```bash
cd jira_audit          # or slack_audit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in credentials
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

### Key Design Constraints
- **Read-only:** Neither tool writes back to Jira or Slack.
- **Config validation at startup:** `config.load_config()` raises immediately on missing required vars so runs never fail mid-way.
- **CLI overrides env:** All `.env` thresholds can be overridden via CLI flags without editing the file.
- **Output goes to `reports/`** (gitignored) by default.
