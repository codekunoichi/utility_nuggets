"""Project activity and backlog health classification logic.

Pure functions with no I/O — easy to unit-test in isolation.

Activity buckets:
  active      — recent creation or resolution activity at or above threshold
  slow        — some recent activity but below threshold
  stale       — no recent activity in the lookback window
  overloaded  — high unresolved backlog with low or negative resolution flow
  dormant     — project has no issues at all; essentially an empty shell
"""

from datetime import datetime, timezone
from typing import Optional


def compute_flow_ratio(
    resolved_last_n: int,
    created_last_n: int,
) -> Optional[float]:
    """Compute resolved/created flow ratio for the lookback window.

    Returns:
        float if both values are meaningful.
        float('inf') if resolved > 0 but nothing was created (net positive flow).
        None if both are zero (no activity to measure).
    """
    if created_last_n == 0 and resolved_last_n == 0:
        return None
    if created_last_n == 0:
        return float("inf")
    return resolved_last_n / created_last_n


def classify_project(
    unresolved_count: int,
    issues_created_last_n: int,
    issues_resolved_last_n: int,
    last_issue_updated_at: Optional[datetime],
    flow_ratio: Optional[float],
    active_threshold: int,
    overloaded_threshold: int,
    _now: Optional[datetime] = None,
) -> tuple[str, str]:
    """Classify a project's activity and backlog health.

    Classification priority (highest wins):
      1. dormant  — project has no issues at all
      2. overloaded — high unresolved backlog with weak flow
      3. active   — recent volume at or above threshold
      4. slow     — some recent activity below threshold
      5. stale    — no recent activity

    Args:
        unresolved_count: Total open issues with resolution = Unresolved.
        issues_created_last_n: Issues created in the lookback window.
        issues_resolved_last_n: Issues resolved in the lookback window.
        last_issue_updated_at: UTC datetime of the most recently updated issue.
        flow_ratio: resolved / created ratio; None if no activity.
        active_threshold: Minimum created or resolved count to be active.
        overloaded_threshold: Unresolved count above which a project may be overloaded.
        _now: Reference time for age calculations; defaults to UTC now.

    Returns:
        (activity_bucket, notes) tuple.
    """
    now = _now if _now is not None else datetime.now(timezone.utc)
    notes: list[str] = []

    total_recent = issues_created_last_n + issues_resolved_last_n

    # 1. Dormant: project contains no issues whatsoever.
    if (
        unresolved_count == 0
        and issues_created_last_n == 0
        and issues_resolved_last_n == 0
        and last_issue_updated_at is None
    ):
        notes.append("no issues found in this project")
        return "dormant", "; ".join(notes)

    # 2. Overloaded: large backlog with poor resolution flow.
    if (
        unresolved_count >= overloaded_threshold
        and flow_ratio is not None
        and flow_ratio != float("inf")
        and flow_ratio <= 0.5
    ):
        notes.append(
            f"{unresolved_count} unresolved issues; "
            f"flow ratio {round(flow_ratio, 2)} (resolving slower than creating)"
        )
        return "overloaded", "; ".join(notes)

    # 3. Active: enough recent movement.
    if (
        issues_created_last_n >= active_threshold
        or issues_resolved_last_n >= active_threshold
    ):
        if unresolved_count >= overloaded_threshold:
            notes.append(
                f"high unresolved backlog ({unresolved_count}); "
                "consider reviewing resolution rate"
            )
        return "active", "; ".join(notes)

    # 4. Slow: some recent movement, below threshold.
    if total_recent > 0:
        notes.append(
            f"{total_recent} issue(s) moved in lookback window "
            f"(threshold: {active_threshold})"
        )
        return "slow", "; ".join(notes)

    # 5. Stale: nothing moved in the lookback window.
    if last_issue_updated_at is not None:
        if last_issue_updated_at.tzinfo is None:
            last_issue_updated_at = last_issue_updated_at.replace(tzinfo=timezone.utc)
        days_since = (now - last_issue_updated_at).days
        notes.append(f"last activity {days_since} day(s) ago")

    return "stale", "; ".join(notes)
