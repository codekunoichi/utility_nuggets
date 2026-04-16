#!/usr/bin/env python3
"""Slack Workspace Audit Tool — entry point.

Run with:
    python main.py
    python main.py --days 60 --output-dir reports --formats csv json
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running directly from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from slack_sdk import WebClient
from tqdm import tqdm

from slack_audit.api import count_messages_since, get_last_message_timestamp, iter_channels
from slack_audit.classifier import classify_channel, is_archived_note
from slack_audit.config import load_config
from slack_audit.models import ChannelRecord
from slack_audit.reporter import print_console_summary, write_csv, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Slack workspace audit: channel activity and purpose clarity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "All secrets must be provided via environment variables or a .env file.\n"
            "See .env.example for required variables."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        metavar="N",
        help="Lookback window in days (overrides SLACK_DAYS_LOOKBACK env var).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="PATH",
        help="Directory to write reports (overrides OUTPUT_DIR env var).",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["csv", "json"],
        default=None,
        metavar="FORMAT",
        help="Output formats: csv json (overrides OUTPUT_FORMATS env var).",
    )
    parser.add_argument(
        "--no-private",
        action="store_true",
        help="Skip private channels entirely.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )
    # Suppress noisy SDK transport logs unless in verbose mode.
    if not verbose:
        logging.getLogger("slack_sdk").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def main() -> None:
    load_dotenv()
    args = parse_args()
    _setup_logging(args.verbose)

    config = load_config()

    # CLI flags override env-var defaults.
    if args.days is not None:
        config.days_lookback = args.days
    if args.output_dir is not None:
        config.output_dir = args.output_dir
    if args.formats is not None:
        config.output_formats = args.formats

    include_private = not args.no_private

    client = WebClient(token=config.slack_bot_token)

    logging.info(
        "Starting audit — lookback: %d days, stale threshold: %d days, "
        "active threshold: %d messages.",
        config.days_lookback,
        config.stale_days,
        config.active_message_threshold,
    )

    lookback_start = datetime.now(timezone.utc) - timedelta(days=config.days_lookback)

    # Phase 1: collect channel list.
    logging.info("Fetching channel list…")
    raw_channels = list(iter_channels(client, include_private=include_private))
    logging.info("Found %d channel(s).", len(raw_channels))

    # Phase 2: gather activity signals and build records.
    records: list[ChannelRecord] = []

    for raw in tqdm(raw_channels, desc="Auditing channels", unit="channel"):
        channel_id: str = raw["id"]
        channel_name: str = raw.get("name", channel_id)
        is_private: bool = raw.get("is_private", False)
        is_archived: bool = raw.get("is_archived", False)
        channel_type = "private" if is_private else "public"

        purpose = (raw.get("purpose") or {}).get("value", "").strip()
        topic = (raw.get("topic") or {}).get("value", "").strip()
        member_count: int = raw.get("num_members", 0)

        created_raw = raw.get("created")
        created_at = (
            datetime.fromtimestamp(float(created_raw), tz=timezone.utc)
            if created_raw
            else None
        )

        if is_archived:
            # Skip history calls for archived channels; flag in notes.
            msg_count = 0
            last_message_at = None
        else:
            msg_count, most_recent_in_window = count_messages_since(
                client, channel_id, lookback_start
            )
            if most_recent_in_window is not None:
                last_message_at = most_recent_in_window
            else:
                # No messages in the window; fetch the actual last message.
                last_message_at = get_last_message_timestamp(client, channel_id)

        activity_bucket, notes = classify_channel(
            purpose=purpose,
            topic=topic,
            last_message_at=last_message_at,
            messages_last_n_days=msg_count,
            active_threshold=config.active_message_threshold,
            stale_days=config.stale_days,
        )

        archived_note = is_archived_note(is_archived)
        if archived_note:
            notes = f"{archived_note}; {notes}" if notes else archived_note
        if is_archived:
            activity_bucket = "stale"

        records.append(
            ChannelRecord(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_type=channel_type,
                purpose=purpose,
                topic=topic,
                member_count=member_count,
                created_at=created_at,
                last_message_at=last_message_at,
                messages_last_n_days=msg_count,
                activity_bucket=activity_bucket,
                notes=notes,
            )
        )

    # Phase 3: write outputs.
    if not records:
        logging.warning("No channels found. Check token scopes and workspace access.")
        return

    print_console_summary(records, config.days_lookback)

    output_paths: list[str] = []
    if "csv" in config.output_formats:
        path = write_csv(records, config.output_dir)
        output_paths.append(str(path))
    if "json" in config.output_formats:
        path = write_json(records, config.output_dir)
        output_paths.append(str(path))

    if output_paths:
        print("Reports written to:")
        for p in output_paths:
            print(f"  {p}")


if __name__ == "__main__":
    main()
