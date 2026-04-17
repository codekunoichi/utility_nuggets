"""Tests for project activity classification and flow ratio logic."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jira_audit.classifier import classify_project, compute_flow_ratio

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
ACTIVE_THRESHOLD = 5
OVERLOADED_THRESHOLD = 100


def _recent(days_ago: int = 1) -> datetime:
    return NOW - timedelta(days=days_ago)


# ---------------------------------------------------------------------------
# compute_flow_ratio
# ---------------------------------------------------------------------------

def test_flow_ratio_normal():
    assert compute_flow_ratio(resolved_last_n=10, created_last_n=20) == pytest.approx(0.5)


def test_flow_ratio_perfect():
    assert compute_flow_ratio(resolved_last_n=10, created_last_n=10) == pytest.approx(1.0)


def test_flow_ratio_above_one():
    assert compute_flow_ratio(resolved_last_n=15, created_last_n=10) == pytest.approx(1.5)


def test_flow_ratio_no_activity_returns_none():
    assert compute_flow_ratio(resolved_last_n=0, created_last_n=0) is None


def test_flow_ratio_resolved_but_no_created_returns_inf():
    assert compute_flow_ratio(resolved_last_n=5, created_last_n=0) == float("inf")


def test_flow_ratio_zero_resolved():
    assert compute_flow_ratio(resolved_last_n=0, created_last_n=10) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Dormant projects
# ---------------------------------------------------------------------------

def test_dormant_project_no_issues():
    bucket, notes = classify_project(
        unresolved_count=0,
        issues_created_last_n=0,
        issues_resolved_last_n=0,
        last_issue_updated_at=None,
        flow_ratio=None,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "dormant"
    assert "no issues" in notes


def test_dormant_not_triggered_when_unresolved_exist():
    bucket, _ = classify_project(
        unresolved_count=5,
        issues_created_last_n=0,
        issues_resolved_last_n=0,
        last_issue_updated_at=_recent(60),
        flow_ratio=None,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket != "dormant"


# ---------------------------------------------------------------------------
# Overloaded projects
# ---------------------------------------------------------------------------

def test_overloaded_high_backlog_poor_flow():
    bucket, notes = classify_project(
        unresolved_count=150,
        issues_created_last_n=20,
        issues_resolved_last_n=5,
        last_issue_updated_at=_recent(1),
        flow_ratio=0.25,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "overloaded"
    assert "150" in notes


def test_overloaded_at_exact_threshold():
    bucket, _ = classify_project(
        unresolved_count=OVERLOADED_THRESHOLD,
        issues_created_last_n=10,
        issues_resolved_last_n=5,
        last_issue_updated_at=_recent(1),
        flow_ratio=0.5,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "overloaded"


def test_not_overloaded_good_flow():
    """High backlog but good flow ratio should not be overloaded."""
    bucket, _ = classify_project(
        unresolved_count=150,
        issues_created_last_n=10,
        issues_resolved_last_n=12,
        last_issue_updated_at=_recent(1),
        flow_ratio=1.2,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket != "overloaded"


def test_not_overloaded_below_threshold():
    """Low unresolved count is not overloaded even with bad flow."""
    bucket, _ = classify_project(
        unresolved_count=50,
        issues_created_last_n=10,
        issues_resolved_last_n=2,
        last_issue_updated_at=_recent(1),
        flow_ratio=0.2,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket != "overloaded"


def test_not_overloaded_inf_flow_ratio():
    """A project resolving without creating (inf ratio) is not overloaded."""
    bucket, _ = classify_project(
        unresolved_count=150,
        issues_created_last_n=0,
        issues_resolved_last_n=10,
        last_issue_updated_at=_recent(1),
        flow_ratio=float("inf"),
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket != "overloaded"


# ---------------------------------------------------------------------------
# Active projects
# ---------------------------------------------------------------------------

def test_active_via_created():
    bucket, _ = classify_project(
        unresolved_count=10,
        issues_created_last_n=ACTIVE_THRESHOLD,
        issues_resolved_last_n=0,
        last_issue_updated_at=_recent(1),
        flow_ratio=0.0,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "active"


def test_active_via_resolved():
    bucket, _ = classify_project(
        unresolved_count=10,
        issues_created_last_n=0,
        issues_resolved_last_n=ACTIVE_THRESHOLD,
        last_issue_updated_at=_recent(1),
        flow_ratio=float("inf"),
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "active"


def test_active_high_unresolved_gets_note():
    """Active project with high unresolved count should include a warning note."""
    bucket, notes = classify_project(
        unresolved_count=OVERLOADED_THRESHOLD + 50,
        issues_created_last_n=10,
        issues_resolved_last_n=12,  # good flow, so not overloaded
        last_issue_updated_at=_recent(1),
        flow_ratio=1.2,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "active"
    assert "high unresolved backlog" in notes


# ---------------------------------------------------------------------------
# Slow projects
# ---------------------------------------------------------------------------

def test_slow_some_created():
    bucket, notes = classify_project(
        unresolved_count=5,
        issues_created_last_n=2,
        issues_resolved_last_n=1,
        last_issue_updated_at=_recent(3),
        flow_ratio=0.5,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "slow"
    assert str(ACTIVE_THRESHOLD) in notes


def test_slow_one_issue_total():
    bucket, _ = classify_project(
        unresolved_count=3,
        issues_created_last_n=1,
        issues_resolved_last_n=0,
        last_issue_updated_at=_recent(5),
        flow_ratio=0.0,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "slow"


# ---------------------------------------------------------------------------
# Stale projects
# ---------------------------------------------------------------------------

def test_stale_no_recent_activity():
    bucket, notes = classify_project(
        unresolved_count=20,
        issues_created_last_n=0,
        issues_resolved_last_n=0,
        last_issue_updated_at=_recent(60),
        flow_ratio=None,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "stale"
    assert "60" in notes


def test_stale_no_recent_activity_no_last_updated():
    bucket, _ = classify_project(
        unresolved_count=5,
        issues_created_last_n=0,
        issues_resolved_last_n=0,
        last_issue_updated_at=None,
        flow_ratio=None,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket == "stale"


# ---------------------------------------------------------------------------
# Timezone-naive datetime
# ---------------------------------------------------------------------------

def test_naive_datetime_does_not_raise():
    naive = NOW.replace(tzinfo=None) - timedelta(days=5)
    bucket, _ = classify_project(
        unresolved_count=10,
        issues_created_last_n=0,
        issues_resolved_last_n=0,
        last_issue_updated_at=naive,
        flow_ratio=None,
        active_threshold=ACTIVE_THRESHOLD,
        overloaded_threshold=OVERLOADED_THRESHOLD,
        _now=NOW,
    )
    assert bucket in ("active", "slow", "stale", "overloaded", "dormant")
