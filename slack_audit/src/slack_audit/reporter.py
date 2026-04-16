"""Output generation: CSV, JSON, and console summary."""

import csv
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .models import ChannelRecord

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
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
]


def _ensure_output_dir(output_dir: str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_filename(output_dir: str, ext: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return _ensure_output_dir(output_dir) / f"slack_audit_{timestamp}.{ext}"


def write_csv(records: list[ChannelRecord], output_dir: str) -> Path:
    """Write all channel records to a timestamped CSV file."""
    path = _report_filename(output_dir, "csv")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())
    logger.info("CSV report written to %s", path)
    return path


def write_json(records: list[ChannelRecord], output_dir: str) -> Path:
    """Write all channel records to a timestamped JSON file."""
    path = _report_filename(output_dir, "json")
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_channels": len(records),
        "channels": [r.to_dict() for r in records],
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("JSON report written to %s", path)
    return path


def print_console_summary(records: list[ChannelRecord], days_lookback: int) -> None:
    """Print a concise summary to stdout."""
    bucket_counts: Counter = Counter(r.activity_bucket for r in records)
    type_counts: Counter = Counter(r.channel_type for r in records)

    total = len(records)
    print("\n" + "=" * 60)
    print("  Slack Workspace Audit — Summary")
    print("=" * 60)
    print(f"  Total channels audited : {total}")
    print(f"  Lookback window        : {days_lookback} day(s)")
    print()
    print("  Channel types:")
    for ctype, count in sorted(type_counts.items()):
        print(f"    {ctype:<20} {count:>5}")
    print()
    print("  Activity breakdown:")
    for bucket in ("active", "slow", "stale", "unclear-purpose"):
        count = bucket_counts.get(bucket, 0)
        bar = "#" * count if count <= 60 else "#" * 60 + f"… (+{count - 60})"
        print(f"    {bucket:<20} {count:>5}  {bar}")
    print()

    stale = [r for r in records if r.activity_bucket == "stale"]
    if stale:
        print(f"  Stale channel examples (up to 10):")
        for r in stale[:10]:
            print(f"    #{r.channel_name}")
        if len(stale) > 10:
            print(f"    … and {len(stale) - 10} more. See the CSV/JSON report.")
    print("=" * 60 + "\n")
