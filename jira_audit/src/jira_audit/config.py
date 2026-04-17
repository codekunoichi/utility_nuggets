"""Configuration loader with strict environment variable validation.

All secrets and runtime parameters come from the environment.
This module never logs token or credential values.
"""

import os
import sys
from dataclasses import dataclass


@dataclass
class AuditConfig:
    """Validated runtime configuration."""

    jira_base_url: str
    jira_user_email: str
    jira_api_token: str
    days_lookback: int
    stale_days: int
    active_issue_threshold: int
    overloaded_unresolved_threshold: int
    output_dir: str
    output_formats: list[str]

    def __repr__(self) -> str:
        # Prevent accidental token or email leakage in log output.
        return (
            f"AuditConfig("
            f"jira_base_url={self.jira_base_url!r}, "
            f"days_lookback={self.days_lookback}, "
            f"stale_days={self.stale_days}, "
            f"active_issue_threshold={self.active_issue_threshold}, "
            f"overloaded_unresolved_threshold={self.overloaded_unresolved_threshold}, "
            f"output_dir={self.output_dir!r}, "
            f"output_formats={self.output_formats})"
        )


def _require_int(name: str, default: str) -> int:
    """Parse an integer env var; exit with a clear message on failure."""
    raw = os.environ.get(name, default)
    try:
        value = int(raw)
    except ValueError:
        sys.exit(f"ERROR: {name} must be an integer, got: {raw!r}")
    if value <= 0:
        sys.exit(f"ERROR: {name} must be a positive integer, got: {value}")
    return value


def _normalize_base_url(url: str) -> str:
    """Strip trailing slashes from the base URL."""
    return url.rstrip("/")


def load_config() -> AuditConfig:
    """Load and validate all configuration from environment variables.

    Exits immediately with a descriptive message if required variables are
    missing or malformed.  Credential values are never printed.
    """
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    if not base_url:
        sys.exit(
            "ERROR: JIRA_BASE_URL is not set.\n"
            "  Example: JIRA_BASE_URL=https://your-org.atlassian.net"
        )
    if not base_url.startswith("https://"):
        sys.exit(
            "ERROR: JIRA_BASE_URL must start with 'https://'.\n"
            f"  Got: {base_url[:30]}..."
        )

    user_email = os.environ.get("JIRA_USER_EMAIL", "").strip()
    if not user_email:
        sys.exit(
            "ERROR: JIRA_USER_EMAIL is not set.\n"
            "  Set it to the email address associated with your Jira account."
        )
    if "@" not in user_email:
        sys.exit("ERROR: JIRA_USER_EMAIL does not look like a valid email address.")

    api_token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not api_token:
        sys.exit(
            "ERROR: JIRA_API_TOKEN is not set.\n"
            "  Generate one at: https://id.atlassian.com/manage-profile/security/api-tokens"
        )

    days_lookback = _require_int("JIRA_DAYS_LOOKBACK", "30")
    stale_days = _require_int("JIRA_STALE_DAYS", "30")
    active_threshold = _require_int("JIRA_ACTIVE_ISSUE_THRESHOLD", "5")
    overloaded_threshold = _require_int("JIRA_OVERLOADED_UNRESOLVED_THRESHOLD", "100")

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
        jira_base_url=_normalize_base_url(base_url),
        jira_user_email=user_email,
        jira_api_token=api_token,
        days_lookback=days_lookback,
        stale_days=stale_days,
        active_issue_threshold=active_threshold,
        overloaded_unresolved_threshold=overloaded_threshold,
        output_dir=output_dir,
        output_formats=output_formats,
    )
