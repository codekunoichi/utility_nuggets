"""Tests for ProjectRecord serialization, field values, and timestamp handling."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jira_audit.models import ProjectRecord
from jira_audit.api import parse_jira_datetime


def _make_record(**overrides) -> ProjectRecord:
    defaults = dict(
        project_key="ENG",
        project_name="Engineering",
        project_type="software",
        project_lead="Alice Smith",
        unresolved_issue_count=42,
        issues_created_last_n_days=10,
        issues_resolved_last_n_days=8,
        last_issue_created_at=datetime(2024, 6, 10, tzinfo=timezone.utc),
        last_issue_updated_at=datetime(2024, 6, 14, tzinfo=timezone.utc),
        oldest_unresolved_issue_age_days=120,
        flow_ratio=0.8,
        activity_bucket="active",
        notes="",
    )
    defaults.update(overrides)
    return ProjectRecord(**defaults)


# ---------------------------------------------------------------------------
# to_dict keys
# ---------------------------------------------------------------------------

def test_to_dict_contains_all_required_keys():
    expected = {
        "project_key",
        "project_name",
        "project_type",
        "project_lead",
        "unresolved_issue_count",
        "issues_created_last_30_days",
        "issues_resolved_last_30_days",
        "last_issue_created_at",
        "last_issue_updated_at",
        "oldest_unresolved_issue_age_days",
        "flow_ratio",
        "activity_bucket",
        "notes",
    }
    assert set(_make_record().to_dict().keys()) == expected


# ---------------------------------------------------------------------------
# Datetime serialization
# ---------------------------------------------------------------------------

def test_datetime_fields_serialized_as_iso_string():
    d = _make_record().to_dict()
    assert "2024-06-10" in d["last_issue_created_at"]
    assert "2024-06-14" in d["last_issue_updated_at"]


def test_none_datetime_fields_serialized_as_empty_string():
    record = _make_record(last_issue_created_at=None, last_issue_updated_at=None)
    d = record.to_dict()
    assert d["last_issue_created_at"] == ""
    assert d["last_issue_updated_at"] == ""


# ---------------------------------------------------------------------------
# Numeric fields
# ---------------------------------------------------------------------------

def test_message_count_key_names():
    record = _make_record(issues_created_last_n_days=7, issues_resolved_last_n_days=3)
    d = record.to_dict()
    assert d["issues_created_last_30_days"] == 7
    assert d["issues_resolved_last_30_days"] == 3


def test_oldest_unresolved_age_preserved():
    record = _make_record(oldest_unresolved_issue_age_days=45)
    assert record.to_dict()["oldest_unresolved_issue_age_days"] == 45


def test_oldest_unresolved_age_none_is_empty_string():
    record = _make_record(oldest_unresolved_issue_age_days=None)
    assert record.to_dict()["oldest_unresolved_issue_age_days"] == ""


# ---------------------------------------------------------------------------
# flow_ratio serialization
# ---------------------------------------------------------------------------

def test_flow_ratio_rounded_to_two_decimals():
    record = _make_record(flow_ratio=0.333333)
    assert record.to_dict()["flow_ratio"] == "0.33"


def test_flow_ratio_none_is_empty_string():
    record = _make_record(flow_ratio=None)
    assert record.to_dict()["flow_ratio"] == ""


def test_flow_ratio_inf_is_string():
    record = _make_record(flow_ratio=float("inf"))
    assert record.to_dict()["flow_ratio"] == "inf"


def test_flow_ratio_zero():
    record = _make_record(flow_ratio=0.0)
    assert record.to_dict()["flow_ratio"] == "0.0"


# ---------------------------------------------------------------------------
# Activity buckets
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bucket", ["active", "slow", "stale", "overloaded", "dormant"])
def test_activity_bucket_preserved(bucket):
    record = _make_record(activity_bucket=bucket)
    assert record.to_dict()["activity_bucket"] == bucket


# ---------------------------------------------------------------------------
# parse_jira_datetime (utility used in api.py)
# ---------------------------------------------------------------------------

def test_parse_jira_datetime_utc():
    dt = parse_jira_datetime("2024-01-15T10:30:00.000+0000")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15


def test_parse_jira_datetime_with_offset():
    dt = parse_jira_datetime("2024-06-01T08:00:00.000+0530")
    assert dt is not None
    # +0530 offset means UTC is 5h30m behind: 08:00 +05:30 = 02:30 UTC
    assert dt.hour == 2
    assert dt.minute == 30


def test_parse_jira_datetime_colon_tz():
    dt = parse_jira_datetime("2024-06-01T12:00:00.000+00:00")
    assert dt is not None
    assert dt.hour == 12


def test_parse_jira_datetime_empty_string():
    assert parse_jira_datetime("") is None


def test_parse_jira_datetime_none_returns_none():
    assert parse_jira_datetime(None) is None  # type: ignore[arg-type]


def test_parse_jira_datetime_invalid_string():
    assert parse_jira_datetime("not-a-date") is None
