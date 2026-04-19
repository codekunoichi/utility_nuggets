# Slack Utility

A collection of lightweight, read-only Python tools for understanding what's happening in your Slack workspace — from channel health to deployment history.

---

## Tools in this package

| Script | What it does |
|--------|-------------|
| `main.py` | **Workspace Audit** — audits every channel for activity, stale status, and purpose clarity |
| `digest_main.py` | **Deployment Digest** — generates a weekly Markdown report of what was deployed, when, and any post-deploy impact alerts |

---

## Workspace Audit (`main.py`)

A read-only audit of Slack channel sprawl and communication overload. Collects channel metadata and activity signals, then produces a CSV/JSON report and a console summary.

Useful for understanding which channels are active, slow, stale, or unclear in purpose.

---

## What It Does

For every accessible channel in your workspace it collects:

| Field | Source |
|---|---|
| Channel name and ID | `conversations.list` |
| Public or private | `conversations.list` |
| Purpose and topic | `conversations.list` |
| Member count | `conversations.list` |
| Created date | `conversations.list` |
| Last message timestamp | `conversations.history` |
| Message count (last N days) | `conversations.history` (paginated) |
| Activity classification | Computed locally |

Each channel is classified into one of four buckets:

| Bucket | Meaning |
|---|---|
| `active` | ≥ N messages in the lookback window |
| `slow` | 1–(N-1) messages in the lookback window |
| `stale` | No messages within the stale-days threshold |
| `unclear-purpose` | Active or slow, but no purpose AND no topic set |

All thresholds are configurable.

---

## Required Slack Scopes

This tool uses the minimum scopes needed for a read-only metadata audit:

| Scope | Why |
|---|---|
| `channels:read` | List public channels and retrieve channel metadata |
| `channels:history` | Read message timestamps and counts in public channels |
| `groups:read` | List private channels the app has been added to |
| `groups:history` | Read message history in accessible private channels |

No user data, no profile access, no write permissions are requested or needed.

---

## Setting Up a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App → From scratch**.
2. Give it a name (e.g. `workspace-audit`) and choose your workspace.
3. Under **OAuth & Permissions → Scopes → Bot Token Scopes**, add:
   - `channels:read`
   - `channels:history`
   - `groups:read`
   - `groups:history`
4. Click **Install to Workspace** and authorize.
5. Copy the **Bot User OAuth Token** (starts with `xoxb-`).

> **Private channels:** The bot only sees private channels it has been explicitly added to. For a comprehensive private channel audit, invite the bot to those channels first, or use a user token (`xoxp-`) with the same scopes.

---

## Installation

```bash
git clone <this-repo>
cd slack_audit

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your bot token:

```bash
cp .env.example .env
```

Edit `.env`:

```
SLACK_BOT_TOKEN=xoxb-your-actual-token
SLACK_DAYS_LOOKBACK=30
SLACK_STALE_DAYS=30
SLACK_ACTIVE_MESSAGE_THRESHOLD=10
OUTPUT_DIR=reports
OUTPUT_FORMATS=csv,json
```

All variables except `SLACK_BOT_TOKEN` have sensible defaults. The tool validates all required variables at startup and exits with a clear message if anything is missing or malformed.

---

## Running the Workspace Audit

```bash
# With defaults from .env:
python main.py

# Override lookback window:
python main.py --days 60

# Write to a custom output directory:
python main.py --output-dir /tmp/audit-results

# Only generate a CSV:
python main.py --formats csv

# Skip private channels:
python main.py --no-private

# Verbose logging for debugging:
python main.py --verbose
```

---

## Output

### Console summary

```
============================================================
  Slack Workspace Audit — Summary
============================================================
  Total channels audited : 84
  Lookback window        : 30 day(s)

  Channel types:
    private                   12
    public                    72

  Activity breakdown:
    active                    31  ###############################
    slow                      18  ##################
    stale                     27  ###########################
    unclear-purpose            8  ########

  Stale channel examples (up to 10):
    #proj-2021-rebrand
    #old-infra-migration
    ...
============================================================
```

### CSV report (`reports/slack_audit_<timestamp>.csv`)

| Column | Description |
|---|---|
| `channel_name` | Human-readable channel name |
| `channel_id` | Slack channel ID |
| `channel_type` | `public` or `private` |
| `purpose` | Channel purpose text (empty if not set) |
| `topic` | Channel topic text (empty if not set) |
| `member_count` | Number of members |
| `created_at` | ISO 8601 creation timestamp |
| `last_message_at` | ISO 8601 timestamp of most recent message |
| `messages_last_30_days` | Message count in the configured lookback window |
| `activity_bucket` | `active` / `slow` / `stale` / `unclear-purpose` |
| `notes` | Human-readable flags (e.g. "archived", "no purpose or topic set") |

### JSON report (`reports/slack_audit_<timestamp>.json`)

Same data as the CSV, wrapped in a top-level object with `generated_at` and `total_channels` fields.

---

---

## Deployment Digest (`digest_main.py`)

Reads two Slack channels — one where your CI/CD bot posts deployment notifications, another where post-deploy alerts land — and produces a weekly Markdown report showing what was deployed when, and which deployments had nearby incident signals.

### What it does

- Fetches all messages from your **deployments channel** for the past N days (default 7)
- Parses structured bot messages to extract service name, version, environment, and deployer
- Fetches all messages from your **impact/alerts channel** in the same window
- Flags any impact message posted within N minutes of a deployment (default 30 min)
- Writes a Markdown digest grouped by day, with a post-deploy impact analysis section

### Additional Slack Scopes Required

The same bot token used for the workspace audit works here, provided it has been added to both channels. No additional scopes are needed beyond what's already listed above.

If your deployment or impact channels are **private**, invite the bot first:
```
/invite @your-bot-name
```

### Additional Environment Variables

Add these to your `.env` file alongside the existing audit variables:

```
# Required — the channel where your CI/CD bot posts deploy notifications
SLACK_DEPLOYMENT_CHANNEL=C0123DEPLOY

# Required — the channel where post-deploy alerts or incident notices land
SLACK_IMPACT_CHANNEL=C0456IMPACT

# Optional — how many days back to scan (default: 7)
DIGEST_LOOKBACK_DAYS=7

# Optional — minutes after a deploy to check for impact events (default: 30)
IMPACT_WINDOW_MINUTES=30
```

#### How to find your Channel IDs

Channel IDs look like `C0123ABCDEF`. The easiest ways to find one:

1. **In Slack:** Open the channel → click the channel name at the top → scroll to the bottom of the popup — the ID is shown there (e.g. `Channel ID: C0123ABCDEF`).
2. **Via URL:** In Slack's browser app, the URL contains the channel ID: `https://app.slack.com/client/TXXXXXXX/C0123ABCDEF` — the part starting with `C` is the channel ID.
3. **Channel name also works:** You can use the channel name (e.g. `deployments`) instead of the ID — the Slack API accepts both.

### Running the Deployment Digest

```bash
# With defaults from .env (past 7 days, 30-min impact window):
python digest_main.py

# Look back 14 days instead:
python digest_main.py --days 14

# Override channels without editing .env:
python digest_main.py --deployment-channel C0123DEPLOY --impact-channel C0456IMPACT

# Write report to a custom directory:
python digest_main.py --output-dir /tmp/digests

# Verbose logging to see what the parser is extracting:
python digest_main.py --verbose
```

### Deployment Digest Output

#### Console summary
```
Deployments: 12 | Services: 5 | With impacts: 2 | Clean: 10
Digest written to: reports/deployment_digest_20260413_20260419.md
```

#### Markdown report (`reports/deployment_digest_YYYYMMDD_YYYYMMDD.md`)

```markdown
# Weekly Deployment Digest
**Period:** Mon Apr 13 – Sun Apr 19, 2026 | **Generated:** 2026-04-19 18:00 UTC

## Summary
| Metric | Value |
|--------|-------|
| Total deployments | 12 |
| Unique services | 5 |
| Deployments with nearby impacts | 2 |
| Clean deployments | 10 |

## Deployments by Day

### Monday, April 13
| Time (UTC) | Service | Version | Environment | Deployer |
|------------|---------|---------|-------------|----------|
| 10:23 | api-service | v2.1.4 | production | @alice |

## Post-Deployment Impact Analysis

### ⚠️ Deployments with Nearby Incidents (within 30 min)
**api-service v2.1.4** → production (Mon Apr 13, 10:23 UTC)
- [10:47] "High error rate on /api/users" _(24 min after deploy)_

### ✅ Clean Deployments
- auth-service v1.8.0 → staging (Mon Apr 13, 15:45) — no impacts in 30-min window
```

### Supported Bot Message Formats

The parser recognises common CI/CD bot patterns out of the box:

| CI/CD Tool | Example message |
|---|---|
| GitHub Actions | `Deployed api-service v2.1.4 to production by @alice` |
| ArgoCD | `app: auth-service\nversion: v1.8.0\nenv: staging\nauthor: bob` |
| Jenkins / generic | `Deploying payment-service to prod` |
| Any tool | `Released frontend v3.0.0-rc.1 to staging` |

If your bot uses a different format, run with `--verbose` to see what the parser is extracting and what it skips — then open an issue or tweak the regex patterns in `src/slack_audit/deployment_digest/parser.py`.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover classification logic, environment variable validation, and model serialization. No real credentials are used.

---

## Security Notes

This repository is intended to be public. A few things to keep in mind:

- **Never commit `.env`.** It is listed in `.gitignore`. The tool will not run without a token set in the environment, and exits immediately if the token is absent or malformed.
- **The `reports/` folder is gitignored.** Report files contain channel names and metadata from your workspace. Do not commit them unless they have been sanitized.
- **Tokens are never printed.** The `AuditConfig.__repr__` is overridden to omit the token. Nothing in the logging pipeline prints secret values.
- **Minimal scopes.** The tool requests only the four scopes it actually uses. Do not expand scopes for convenience.
- **Read-only.** The tool makes no write calls to Slack. It cannot post messages, modify channels, or change any workspace settings.

---

## Limitations

- **Private channel visibility** depends entirely on whether the bot has been added to each channel. Channels the bot cannot access are silently skipped.
- **Message counts are approximate** for very high-traffic channels. The tool paginates through history but stops at Slack's API boundaries.
- **Archived channels** are flagged as `stale` in the output; their message history is not fetched.
- **Rate limits:** Slack throttles `conversations.history` calls. On large workspaces (hundreds of channels) the audit may take several minutes. The tool backs off automatically on 429 responses.
- **Bot messages** are counted along with user messages. The tool does not distinguish between human-generated and automated traffic.
- **Direct messages and group DMs** are not included; only channels are audited.
