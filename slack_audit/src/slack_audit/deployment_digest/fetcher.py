"""Fetch raw messages from a Slack channel within a time window."""

import logging
from datetime import datetime, timezone
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from slack_audit.api import _call_with_retry

logger = logging.getLogger(__name__)

_HISTORY_PAGE_SIZE = 200


def fetch_messages(
    client: WebClient,
    channel_id: str,
    since: datetime,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Return all messages from a channel between since and until (inclusive).

    Args:
        client: Authenticated Slack WebClient.
        channel_id: The channel to fetch history from.
        since: UTC datetime; oldest boundary.
        until: UTC datetime; newest boundary. Defaults to now.

    Returns:
        List of raw Slack message dicts, newest-first order from API.
    """
    oldest_ts = str(since.timestamp())
    latest_ts = str((until or datetime.now(tz=timezone.utc)).timestamp())
    cursor: Optional[str] = None
    messages: list[dict] = []

    while True:
        kwargs: dict = {
            "channel": channel_id,
            "oldest": oldest_ts,
            "latest": latest_ts,
            "limit": _HISTORY_PAGE_SIZE,
            "inclusive": True,
        }
        if cursor:
            kwargs["cursor"] = cursor

        try:
            response = _call_with_retry(client.conversations_history, **kwargs)
        except SlackApiError as exc:
            error_code = exc.response.get("error", "unknown")
            if error_code in ("not_in_channel", "channel_not_found", "is_archived"):
                logger.debug("Cannot read history for %s: %s", channel_id, error_code)
            else:
                logger.warning(
                    "Error fetching messages from %s: %s", channel_id, error_code
                )
            break

        messages.extend(response.get("messages", []))

        next_cursor = (
            response.get("response_metadata", {}).get("next_cursor", "") or ""
        )
        if not next_cursor:
            break
        cursor = next_cursor

    return messages
