# Jira Project Activity Audit Tool

A lightweight, read-only Python tool for auditing Jira project sprawl, backlog health, and delivery flow signals. It uses the Jira Cloud REST API to collect project-level metrics, then produces a CSV/JSON report and a console summary — without modifying anything in your Jira instance.

The goal is operational visibility: understanding which projects are active, which are accumulating unresolved work, and which have gone quiet — as evidence for decisions about portfolio hygiene and reducing cognitive overhead.

---

## What It Does

For every accessible Jira project it collects:

| Field | How it's gathered |
|---|---|
| Project key, name, type, lead | `GET /rest/api/3/project/search` |
| Unresolved issue count | JQL: `resolution = Unresolved` |
| Issues created last N days | JQL: `created >= -{N}d` |
| Issues resolved last N days | JQL: `resolved >= -{N}d` |
| Last issue created date | JQL: `ORDER BY created DESC` |
| Last issue updated date | JQL: `ORDER BY updated DESC` |
| Oldest unresolved issue age | JQL: `resolution = Unresolved ORDER BY created ASC` |
| Flow ratio | `resolved_last_N / created_last_N` |
| Activity classification | Computed locally |

All unresolved queries use `resolution = Unresolved` — not workflow status names like "To Do" or "In Progress", which vary by team and configuration.

Each project is classified into one of five buckets:

| Bucket | Meaning |
|---|---|
| `active` | Created or resolved issues in the window meet or exceed the threshold |
| `slow` | Some movement in the window, but below the threshold |
| `stale` | No issues created or resolved in the lookback window |
| `overloaded` | Unresolved count exceeds the threshold AND flow ratio ≤ 0.5 |
| `dormant` | Project exists but contains no issues at all |

All thresholds are configurable.

### Flow Ratio

`flow_ratio = issues_resolved_last_N / issues_created_last_N`

| Value | Interpretation |
|---|---|
| > 1.0 | Team is resolving faster than work is arriving |
| 1.0 | Even throughput — resolving at the same rate as creating |
| < 1.0 | Backlog is growing — more created than resolved |
| `inf` | Resolving old issues with no new ones arriving |
| (empty) | No activity in either direction |

---

## Required Jira Permissions

This tool only reads data. No write permissions are needed. The API token must belong to an account that can:

- **Browse projects** — to list accessible projects
- **Browse issues** — to run JQL queries against project issues

Projects or issues the token cannot access are silently skipped.

---

## Authentication

Jira Cloud uses HTTP Basic Authentication with an API token (not your account password):

```
Authorization: Basic base64(email:api_token)
```

**To generate an API token:**
1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Give it a label (e.g. `workspace-audit`) and copy the token value
4. Store it in your `.env` file as `JIRA_API_TOKEN`

The token grants the same project access as your account. It does not expire unless you revoke it.

---

## Installation

```bash
git clone <this-repo>
cd jira_audit

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
JIRA_DAYS_LOOKBACK=30
JIRA_STALE_DAYS=30
JIRA_ACTIVE_ISSUE_THRESHOLD=5
JIRA_OVERLOADED_UNRESOLVED_THRESHOLD=100
OUTPUT_DIR=reports
OUTPUT_FORMATS=csv,json
```

The tool validates all required variables at startup and exits with a clear message if anything is missing or malformed. The API token and email are never printed.

---

## Running the Tool

```bash
# With defaults from .env:
python main.py

# Override lookback window:
python main.py --days 60

# Write to a custom output directory:
python main.py --output-dir /tmp/audit-results

# Only generate a CSV:
python main.py --formats csv

# Verbose logging for debugging:
python main.py --verbose
```

---

## Output

### Console summary

```
================================================================
  Jira Project Activity Audit — Summary
================================================================
  Total projects audited   : 38
  Lookback window          : 30 day(s)
  Total unresolved issues  : 2,847

  Activity breakdown:
    active          12  ############
    slow             7  #######
    stale            9  #########
    overloaded       4  ####
    dormant          6  ######

  Overloaded projects (high backlog, low flow):
    [PLATFORM] Platform Engineering — 342 unresolved, flow ratio: 0.21
    [LEGACY] Legacy Migration — 218 unresolved, flow ratio: 0.33
    ...

  Stale projects (no recent activity, up to 10):
    [OPS-2021] Ops Automation 2021
    [MOBILE-V1] Mobile App V1
    ...
================================================================
```

### CSV report (`reports/jira_audit_<timestamp>.csv`)

| Column | Description |
|---|---|
| `project_key` | Jira project key (e.g. ENG, PLAT) |
| `project_name` | Full project name |
| `project_type` | Jira project type (e.g. software, business) |
| `project_lead` | Display name of the project lead |
| `unresolved_issue_count` | Total open issues with `resolution = Unresolved` |
| `issues_created_last_30_days` | Issues created in the configured lookback window |
| `issues_resolved_last_30_days` | Issues resolved in the configured lookback window |
| `last_issue_created_at` | ISO 8601 timestamp of the most recently created issue |
| `last_issue_updated_at` | ISO 8601 timestamp of the most recently updated issue |
| `oldest_unresolved_issue_age_days` | Age in days of the oldest open issue |
| `flow_ratio` | `resolved / created` for the lookback window |
| `activity_bucket` | Classification: active / slow / stale / overloaded / dormant |
| `notes` | Human-readable context (e.g. backlog size, flow signal) |

### JSON report (`reports/jira_audit_<timestamp>.json`)

Same fields wrapped in a top-level object with `generated_at` and `total_projects`.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover classification logic, flow ratio calculation, environment variable validation, datetime parsing, and model serialization. No real credentials are used.

---

## Security Notes

- **Never commit `.env`** — it is listed in `.gitignore`. The tool exits immediately if required credentials are missing.
- **The `reports/` directory is gitignored** — report files contain project names and issue counts from your workspace. Do not commit them unless sanitized.
- **Credentials are never printed** — `AuditConfig.__repr__` omits the API token and email address. Nothing in the logging pipeline outputs credential values.
- **Read-only** — the tool makes no write calls. It cannot create, update, or delete issues, projects, or comments.
- **HTTPS required** — the config loader rejects any base URL that does not start with `https://`.

---

## Limitations

- **Project visibility** depends on the permissions of the account that owns the API token. Projects the account cannot browse are silently skipped.
- **Private or restricted projects** may return empty counts rather than an error. The tool handles this gracefully but the data will show as dormant or stale.
- **Rate limits** — Jira Cloud enforces API rate limits. On large workspaces (many projects with deep histories), the audit may take several minutes. The tool backs off automatically on 429 responses.
- **Jira Cloud only** — this tool targets the Jira Cloud REST API v3. Jira Data Center uses different endpoints and auth; it is not supported without modifications.
- **Archived projects** are included in the project list if the account can see them. Their metrics reflect whatever historical data Jira returns.
- **Bot and automation issues** are counted alongside human-created issues. The tool does not distinguish between automated and manual ticket creation.

---

## Interpretation Caveats

Jira data reflects how teams use Jira, not necessarily how they work. Before acting on these signals:

- **Stale ≠ abandoned.** A project with no recent issues may be complete, in maintenance mode, or tracked elsewhere.
- **Overloaded ≠ struggling.** A large backlog can be intentional (a feature backlog, an icebox, a support queue). Flow ratio alone does not explain why.
- **Active ≠ healthy.** High ticket volume can indicate a noisy incident queue or poor issue hygiene as easily as it indicates good delivery cadence.
- **Dormant ≠ useless.** Empty projects are sometimes placeholders, archived templates, or spaces kept for configuration reasons.

Use this data as a starting point for conversations, not as a verdict.
