"""Configuration loader for the deployment digest tool."""

import os
import sys
from dataclasses import dataclass

from slack_audit.config import REQUIRED_TOKEN_PREFIXES, _require_int


@dataclass
class DigestConfig:
    """Validated runtime configuration for the deployment digest."""

    slack_bot_token: str
    deployment_channel: str
    impact_channel: str
    lookback_days: int
    impact_window_minutes: int
    output_dir: str

    def __repr__(self) -> str:
        return (
            f"DigestConfig(deployment_channel={self.deployment_channel!r}, "
            f"impact_channel={self.impact_channel!r}, "
            f"lookback_days={self.lookback_days}, "
            f"impact_window_minutes={self.impact_window_minutes}, "
            f"output_dir={self.output_dir!r})"
        )


def load_digest_config() -> DigestConfig:
    """Load and validate all configuration from environment variables.

    Exits immediately with a descriptive message on missing or invalid values.
    Token values are never printed.
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()

    if not token:
        sys.exit(
            "ERROR: SLACK_BOT_TOKEN is not set.\n"
            "  Set it in your .env file or export it before running."
        )

    if not any(token.startswith(prefix) for prefix in REQUIRED_TOKEN_PREFIXES):
        sys.exit(
            "ERROR: SLACK_BOT_TOKEN does not look like a valid Slack token.\n"
            "  Expected a bot token (xoxb-...) or user token (xoxp-...)."
        )

    deployment_channel = os.environ.get("SLACK_DEPLOYMENT_CHANNEL", "").strip()
    if not deployment_channel:
        sys.exit("ERROR: SLACK_DEPLOYMENT_CHANNEL is not set.")

    impact_channel = os.environ.get("SLACK_IMPACT_CHANNEL", "").strip()
    if not impact_channel:
        sys.exit("ERROR: SLACK_IMPACT_CHANNEL is not set.")

    lookback_days = _require_int("DIGEST_LOOKBACK_DAYS", "7")
    impact_window_minutes = _require_int("IMPACT_WINDOW_MINUTES", "30")

    output_dir = os.environ.get("OUTPUT_DIR", "reports").strip() or "reports"

    return DigestConfig(
        slack_bot_token=token,
        deployment_channel=deployment_channel,
        impact_channel=impact_channel,
        lookback_days=lookback_days,
        impact_window_minutes=impact_window_minutes,
        output_dir=output_dir,
    )
