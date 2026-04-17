"""Output generation: CSV, JSON, and console summary."""

import csv
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .models import ProjectRecord

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
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
]


def _ensure_output_dir(output_dir: str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_filename(output_dir: str, ext: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return _ensure_output_dir(output_dir) / f"jira_audit_{timestamp}.{ext}"


def write_csv(records: list[ProjectRecord], output_dir: str) -> Path:
    """Write all project records to a timestamped CSV file."""
    path = _report_filename(output_dir, "csv")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())
    logger.info("CSV report written to %s", path)
    return path


def write_json(records: list[ProjectRecord], output_dir: str) -> Path:
    """Write all project records to a timestamped JSON file."""
    path = _report_filename(output_dir, "json")
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_projects": len(records),
        "projects": [r.to_dict() for r in records],
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("JSON report written to %s", path)
    return path


def print_console_summary(records: list[ProjectRecord], days_lookback: int) -> None:
    """Print a concise project health summary to stdout."""
    bucket_counts: Counter = Counter(r.activity_bucket for r in records)
    total = len(records)
    total_unresolved = sum(r.unresolved_issue_count for r in records)

    print("\n" + "=" * 64)
    print("  Jira Project Activity Audit — Summary")
    print("=" * 64)
    print(f"  Total projects audited   : {total}")
    print(f"  Lookback window          : {days_lookback} day(s)")
    print(f"  Total unresolved issues  : {total_unresolved}")
    print()
    print("  Activity breakdown:")
    for bucket in ("active", "slow", "stale", "overloaded", "dormant"):
        count = bucket_counts.get(bucket, 0)
        bar = "#" * min(count, 50)
        if count > 50:
            bar += f"… (+{count - 50})"
        print(f"    {bucket:<14} {count:>5}  {bar}")
    print()

    overloaded = [r for r in records if r.activity_bucket == "overloaded"]
    if overloaded:
        print("  Overloaded projects (high backlog, low flow):")
        for r in overloaded[:10]:
            print(
                f"    [{r.project_key}] {r.project_name}"
                f" — {r.unresolved_issue_count} unresolved"
                f", flow ratio: {r.to_dict()['flow_ratio'] or 'N/A'}"
            )
        if len(overloaded) > 10:
            print(f"    … and {len(overloaded) - 10} more. See the full report.")
        print()

    stale = [r for r in records if r.activity_bucket == "stale"]
    if stale:
        print(f"  Stale projects (no recent activity, up to 10):")
        for r in stale[:10]:
            print(f"    [{r.project_key}] {r.project_name}")
        if len(stale) > 10:
            print(f"    … and {len(stale) - 10} more. See the CSV/JSON report.")
    print("=" * 64 + "\n")
