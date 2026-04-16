"""Configuration loader with strict environment variable validation.

All secrets and runtime parameters come from the environment.
This module never logs token values.
"""

import os
import sys
from dataclasses import dataclass


REQUIRED_TOKEN_PREFIXES = ("xoxb-", "xoxp-")


@dataclass
class AuditConfig:
    """Validated runtime configuration."""

    slack_bot_token: str
    days_lookback: int
    stale_days: int
    active_message_threshold: int
    output_dir: str
    output_formats: list[str]

    def __repr__(self) -> str:
        # Prevent accidental token leakage in log output.
        return (
            f"AuditConfig(days_lookback={self.days_lookback}, "
            f"stale_days={self.stale_days}, "
            f"active_message_threshold={self.active_message_threshold}, "
            f"output_dir={self.output_dir!r}, "
            f"output_formats={self.output_formats})"
        )


def _require_int(name: str, default: str) -> int:
    """Parse an integer environment variable; exit with a clear message on failure."""
    raw = os.environ.get(name, default)
    try:
        value = int(raw)
    except ValueError:
        sys.exit(f"ERROR: {name} must be an integer, got: {raw!r}")
    if value <= 0:
        sys.exit(f"ERROR: {name} must be a positive integer, got: {value}")
    return value


def load_config() -> AuditConfig:
    """Load and validate all configuration from environment variables.

    Exits immediately with a descriptive message if required variables are
    missing or malformed.  Token values are never printed.
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()

    if not token:
        sys.exit(
            "ERROR: SLACK_BOT_TOKEN is not set.\n"
            "  Set it in your .env file and load it before running:\n"
            "    export $(grep -v '^#' .env | xargs)\n"
            "  or use: python-dotenv, direnv, etc."
        )

    if not any(token.startswith(prefix) for prefix in REQUIRED_TOKEN_PREFIXES):
        sys.exit(
            "ERROR: SLACK_BOT_TOKEN does not look like a valid Slack token.\n"
            "  Expected a bot token (xoxb-...) or user token (xoxp-...).\n"
            "  Check the value in your .env file."
        )

    days_lookback = _require_int("SLACK_DAYS_LOOKBACK", "30")
    stale_days = _require_int("SLACK_STALE_DAYS", "30")
    active_threshold = _require_int("SLACK_ACTIVE_MESSAGE_THRESHOLD", "10")

    output_dir = os.environ.get("OUTPUT_DIR", "reports").strip() or "reports"
    formats_raw = os.environ.get("OUTPUT_FORMATS", "csv,json").strip()
    output_formats = [f.strip().lower() for f in formats_raw.split(",") if f.strip()]

    valid_formats = {"csv", "json"}
    unknown = set(output_formats) - valid_formats
    if unknown:
        sys.exit(
            f"ERROR: OUTPUT_FORMATS contains unknown format(s): {', '.join(sorted(unknown))}.\n"
            f"  Supported formats: {', '.join(sorted(valid_formats))}"
        )

    return AuditConfig(
        slack_bot_token=token,
        days_lookback=days_lookback,
        stale_days=stale_days,
        active_message_threshold=active_threshold,
        output_dir=output_dir,
        output_formats=output_formats,
    )
