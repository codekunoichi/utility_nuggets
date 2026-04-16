"""Tests for channel activity classification logic."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slack_audit.classifier import classify_channel, is_archived_note

# Fixed reference time used throughout tests.
NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
ACTIVE_THRESHOLD = 10
STALE_DAYS = 30


def _recent(days_ago: int = 1) -> datetime:
    return NOW - timedelta(days=days_ago)


# ---------------------------------------------------------------------------
# Active channels
# ---------------------------------------------------------------------------

def test_active_channel_with_purpose():
    bucket, notes = classify_channel(
        purpose="Engineering discussions",
        topic="Sprint planning",
        last_message_at=_recent(1),
        messages_last_n_days=15,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "active"
    assert notes == ""


def test_active_channel_exactly_at_threshold():
    bucket, _ = classify_channel(
        purpose="Some purpose",
        topic="",
        last_message_at=_recent(1),
        messages_last_n_days=ACTIVE_THRESHOLD,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "active"


# ---------------------------------------------------------------------------
# Slow channels
# ---------------------------------------------------------------------------

def test_slow_channel():
    bucket, notes = classify_channel(
        purpose="Low traffic team",
        topic="Occasional updates",
        last_message_at=_recent(5),
        messages_last_n_days=3,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "slow"
    assert notes == ""


def test_slow_channel_one_message():
    bucket, _ = classify_channel(
        purpose="Some purpose",
        topic="some topic",
        last_message_at=_recent(2),
        messages_last_n_days=1,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "slow"


# ---------------------------------------------------------------------------
# Stale channels
# ---------------------------------------------------------------------------

def test_stale_channel_no_history():
    bucket, notes = classify_channel(
        purpose="Old project",
        topic="",
        last_message_at=None,
        messages_last_n_days=0,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "stale"
    assert "no message history" in notes


def test_stale_channel_last_message_old():
    bucket, notes = classify_channel(
        purpose="Legacy channel",
        topic="archived project",
        last_message_at=_recent(STALE_DAYS + 1),
        messages_last_n_days=0,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "stale"
    assert "day(s) ago" in notes


def test_stale_channel_exactly_at_stale_boundary():
    """Channel whose last message is exactly stale_days old should be stale."""
    bucket, _ = classify_channel(
        purpose="Edge case",
        topic="edge",
        last_message_at=_recent(STALE_DAYS + 1),
        messages_last_n_days=0,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "stale"


def test_not_stale_just_inside_boundary():
    bucket, _ = classify_channel(
        purpose="Recent enough",
        topic="some topic",
        last_message_at=_recent(STALE_DAYS - 1),
        messages_last_n_days=5,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket != "stale"


# ---------------------------------------------------------------------------
# Unclear-purpose channels
# ---------------------------------------------------------------------------

def test_unclear_purpose_active_channel():
    bucket, notes = classify_channel(
        purpose="",
        topic="",
        last_message_at=_recent(1),
        messages_last_n_days=20,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "unclear-purpose"
    assert "no purpose or topic" in notes


def test_unclear_purpose_slow_channel():
    bucket, notes = classify_channel(
        purpose="",
        topic="",
        last_message_at=_recent(5),
        messages_last_n_days=3,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "unclear-purpose"
    assert "no purpose or topic" in notes


def test_unclear_purpose_stale_stays_stale():
    """A stale channel with no purpose/topic stays stale (not unclear-purpose)."""
    bucket, notes = classify_channel(
        purpose="",
        topic="",
        last_message_at=None,
        messages_last_n_days=0,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket == "stale"
    assert "no purpose or topic" in notes


def test_purpose_only_no_topic_not_unclear():
    """Having a purpose but no topic is enough to avoid unclear-purpose."""
    bucket, _ = classify_channel(
        purpose="Engineering discussions",
        topic="",
        last_message_at=_recent(1),
        messages_last_n_days=20,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket != "unclear-purpose"


def test_topic_only_no_purpose_not_unclear():
    """Having a topic but no purpose is enough to avoid unclear-purpose."""
    bucket, _ = classify_channel(
        purpose="",
        topic="Current sprint work",
        last_message_at=_recent(1),
        messages_last_n_days=20,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket != "unclear-purpose"


# ---------------------------------------------------------------------------
# Timezone-naive last_message_at
# ---------------------------------------------------------------------------

def test_naive_datetime_handled_safely():
    """A timezone-naive datetime should not raise a TypeError."""
    naive_dt = NOW.replace(tzinfo=None) - timedelta(days=1)
    bucket, _ = classify_channel(
        purpose="Some purpose",
        topic="some topic",
        last_message_at=naive_dt,
        messages_last_n_days=5,
        active_threshold=ACTIVE_THRESHOLD,
        stale_days=STALE_DAYS,
        _now=NOW,
    )
    assert bucket in ("active", "slow", "stale", "unclear-purpose")


# ---------------------------------------------------------------------------
# is_archived_note helper
# ---------------------------------------------------------------------------

def test_archived_note_true():
    assert is_archived_note(True) == "archived"


def test_archived_note_false():
    assert is_archived_note(False) == ""
