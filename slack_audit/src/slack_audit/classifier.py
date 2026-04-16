"""Channel activity classification logic.

Pure functions with no I/O — easy to unit-test in isolation.

Activity buckets:
  active          — recent messages at or above the configured threshold
  slow            — some recent messages, below threshold
  stale           — no messages within the stale-days window
  unclear-purpose — active or slow, but no purpose and no topic set
"""

from datetime import datetime, timezone
from typing import Optional


def classify_channel(
    purpose: str,
    topic: str,
    last_message_at: Optional[datetime],
    messages_last_n_days: int,
    active_threshold: int,
    stale_days: int,
    _now: Optional[datetime] = None,
) -> tuple[str, str]:
    """Classify a channel and produce a short notes string.

    Args:
        purpose: Channel purpose text (may be empty).
        topic: Channel topic text (may be empty).
        last_message_at: UTC datetime of the most recent message, or None.
        messages_last_n_days: Count of messages within the lookback window.
        active_threshold: Minimum message count to be considered active.
        stale_days: Days of silence that mark a channel as stale.
        _now: Reference time for staleness calculation; defaults to UTC now.
              Pass an explicit value in tests to avoid relying on the system clock.

    Returns:
        A (activity_bucket, notes) tuple.
    """
    notes: list[str] = []

    has_purpose = bool(purpose and purpose.strip())
    has_topic = bool(topic and topic.strip())
    unclear = not has_purpose and not has_topic

    if unclear:
        notes.append("no purpose or topic set")

    # Determine base activity level.
    if last_message_at is None:
        base_bucket = "stale"
        notes.append("no message history accessible")
    else:
        now = _now if _now is not None else datetime.now(timezone.utc)
        # Ensure last_message_at is timezone-aware for safe comparison.
        if last_message_at.tzinfo is None:
            last_message_at = last_message_at.replace(tzinfo=timezone.utc)

        days_since = (now - last_message_at).days
        if days_since > stale_days:
            base_bucket = "stale"
            notes.append(f"last message {days_since} day(s) ago")
        elif messages_last_n_days >= active_threshold:
            base_bucket = "active"
        elif messages_last_n_days > 0:
            base_bucket = "slow"
        else:
            base_bucket = "stale"
            notes.append(f"no messages in lookback window")

    # Promote active/slow channels with no purpose to unclear-purpose.
    if unclear and base_bucket in ("active", "slow"):
        final_bucket = "unclear-purpose"
    else:
        final_bucket = base_bucket

    return final_bucket, "; ".join(notes)


def is_archived_note(is_archived: bool) -> str:
    """Return a note string if the channel is archived."""
    return "archived" if is_archived else ""
