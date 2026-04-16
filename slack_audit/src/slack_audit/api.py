"""Slack API client — read-only, paginated, rate-limit-aware.

This module wraps only the endpoints needed for a metadata audit:
  - conversations.list  (channel inventory)
  - conversations.history  (activity signals)

No write operations. No user data. No profile access.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Iterator, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Maximum retries on a 429 rate-limit response before giving up on a channel.
_MAX_RETRIES = 5

# Seconds to add as a safety buffer on top of the Retry-After header value.
_RETRY_BUFFER = 0.5

# Pages fetched per conversations.history call; Slack max is 200.
_HISTORY_PAGE_SIZE = 200


def _call_with_retry(fn, *args, **kwargs):
    """Invoke a Slack SDK call, retrying on 429 rate-limit responses.

    Raises SlackApiError for any non-recoverable API error.
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except SlackApiError as exc:
            if exc.response.status_code == 429:
                retry_after = float(
                    exc.response.headers.get("Retry-After", "1")
                )
                wait = retry_after + _RETRY_BUFFER
                logger.warning(
                    "Rate limited by Slack API. Waiting %.1fs (attempt %d/%d).",
                    wait,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(wait)
                if attempt == _MAX_RETRIES:
                    raise
            else:
                raise


def iter_channels(client: WebClient, include_private: bool = True) -> Iterator[dict]:
    """Yield raw channel objects from conversations.list with full pagination.

    Args:
        client: Authenticated Slack WebClient.
        include_private: Whether to include private channels the token can see.
    """
    channel_types = "public_channel,private_channel" if include_private else "public_channel"
    cursor: Optional[str] = None

    while True:
        kwargs: dict = {
            "types": channel_types,
            "limit": 1000,
            "exclude_archived": False,  # Include archived so we can flag them.
        }
        if cursor:
            kwargs["cursor"] = cursor

        try:
            response = _call_with_retry(client.conversations_list, **kwargs)
        except SlackApiError as exc:
            logger.error("Failed to list channels: %s", exc.response["error"])
            return

        for channel in response.get("channels", []):
            yield channel

        next_cursor = (
            response.get("response_metadata", {}).get("next_cursor", "") or ""
        )
        if not next_cursor:
            break
        cursor = next_cursor


def get_last_message_timestamp(
    client: WebClient, channel_id: str
) -> Optional[datetime]:
    """Return the UTC datetime of the most recent message, or None if inaccessible."""
    try:
        response = _call_with_retry(
            client.conversations_history,
            channel=channel_id,
            limit=1,
        )
    except SlackApiError as exc:
        error_code = exc.response.get("error", "unknown")
        if error_code in ("not_in_channel", "channel_not_found", "is_archived"):
            logger.debug(
                "Cannot read history for %s: %s", channel_id, error_code
            )
        else:
            logger.warning(
                "Unexpected error reading last message for %s: %s",
                channel_id,
                error_code,
            )
        return None

    messages = response.get("messages", [])
    if not messages:
        return None

    try:
        ts = float(messages[0]["ts"])
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (KeyError, ValueError):
        return None


def count_messages_since(
    client: WebClient,
    channel_id: str,
    since: datetime,
) -> tuple[int, Optional[datetime]]:
    """Count messages posted on or after `since` and return the most recent timestamp.

    Uses paginated conversations.history to stay within the lookback window.

    Args:
        client: Authenticated Slack WebClient.
        channel_id: The channel to query.
        since: UTC datetime; only messages at or after this time are counted.

    Returns:
        (message_count, most_recent_message_datetime_or_None)
    """
    oldest_ts = str(since.timestamp())
    count = 0
    most_recent: Optional[datetime] = None
    cursor: Optional[str] = None

    while True:
        kwargs: dict = {
            "channel": channel_id,
            "oldest": oldest_ts,
            "limit": _HISTORY_PAGE_SIZE,
        }
        if cursor:
            kwargs["cursor"] = cursor

        try:
            response = _call_with_retry(client.conversations_history, **kwargs)
        except SlackApiError as exc:
            error_code = exc.response.get("error", "unknown")
            if error_code in ("not_in_channel", "channel_not_found", "is_archived"):
                logger.debug(
                    "Cannot read history for %s: %s", channel_id, error_code
                )
            else:
                logger.warning(
                    "Error reading history for %s: %s", channel_id, error_code
                )
            break

        messages = response.get("messages", [])
        count += len(messages)

        if messages and most_recent is None:
            # Messages are returned newest-first; first item is the most recent.
            try:
                ts = float(messages[0]["ts"])
                most_recent = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (KeyError, ValueError):
                pass

        next_cursor = (
            response.get("response_metadata", {}).get("next_cursor", "") or ""
        )
        if not next_cursor:
            break
        cursor = next_cursor

    return count, most_recent
