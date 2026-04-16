"""Tests for ChannelRecord serialization and timestamp handling."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slack_audit.models import ChannelRecord


def _make_record(**overrides) -> ChannelRecord:
    defaults = dict(
        channel_id="C01234567",
        channel_name="general",
        channel_type="public",
        purpose="Company-wide announcements",
        topic="Latest news",
        member_count=42,
        created_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
        last_message_at=datetime(2024, 6, 1, 10, 30, 0, tzinfo=timezone.utc),
        messages_last_n_days=25,
        activity_bucket="active",
        notes="",
    )
    defaults.update(overrides)
    return ChannelRecord(**defaults)


# ---------------------------------------------------------------------------
# to_dict keys and types
# ---------------------------------------------------------------------------

def test_to_dict_contains_all_required_keys():
    expected_keys = {
        "channel_name",
        "channel_id",
        "channel_type",
        "purpose",
        "topic",
        "member_count",
        "created_at",
        "last_message_at",
        "messages_last_30_days",
        "activity_bucket",
        "notes",
    }
    record = _make_record()
    assert set(record.to_dict().keys()) == expected_keys


def test_to_dict_datetime_serialized_as_iso_string():
    record = _make_record()
    d = record.to_dict()
    assert "2022-01-01" in d["created_at"]
    assert "2024-06-01" in d["last_message_at"]


def test_to_dict_none_datetime_serialized_as_empty_string():
    record = _make_record(created_at=None, last_message_at=None)
    d = record.to_dict()
    assert d["created_at"] == ""
    assert d["last_message_at"] == ""


def test_to_dict_message_count_key_name():
    """The CSV column name for message count should be messages_last_30_days."""
    record = _make_record(messages_last_n_days=17)
    d = record.to_dict()
    assert d["messages_last_30_days"] == 17


# ---------------------------------------------------------------------------
# Channel type values
# ---------------------------------------------------------------------------

def test_public_channel_type():
    record = _make_record(channel_type="public")
    assert record.to_dict()["channel_type"] == "public"


def test_private_channel_type():
    record = _make_record(channel_type="private")
    assert record.to_dict()["channel_type"] == "private"


# ---------------------------------------------------------------------------
# Activity bucket round-trips
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bucket", ["active", "slow", "stale", "unclear-purpose"])
def test_activity_bucket_preserved(bucket):
    record = _make_record(activity_bucket=bucket)
    assert record.to_dict()["activity_bucket"] == bucket


# ---------------------------------------------------------------------------
# Notes field
# ---------------------------------------------------------------------------

def test_notes_preserved():
    record = _make_record(notes="archived; no purpose or topic set")
    assert record.to_dict()["notes"] == "archived; no purpose or topic set"


def test_empty_notes_preserved():
    record = _make_record(notes="")
    assert record.to_dict()["notes"] == ""
