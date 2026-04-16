# Slack Workspace Audit Tool

A lightweight, read-only Python tool for auditing Slack channel sprawl and communication overload. It collects channel metadata and activity signals, then produces a CSV/JSON report and a console summary — without modifying anything in your workspace.

Useful for understanding which channels are active, slow, stale, or unclear in purpose, as evidence for decisions about reducing cognitive load and improving focus.

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
