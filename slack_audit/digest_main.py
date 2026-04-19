#!/usr/bin/env python3
"""Slack Deployment Digest — entry point.

Fetches deployment notifications and post-deploy impact alerts from two
dedicated Slack channels, correlates them by time proximity, and renders
a weekly Markdown digest.

Run with:
    python digest_main.py
    python digest_main.py --days 14 --output-dir reports --verbose
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from slack_sdk import WebClient

from slack_audit.deployment_digest.config import load_digest_config
from slack_audit.deployment_digest.correlator import correlate
from slack_audit.deployment_digest.fetcher import fetch_messages
from slack_audit.deployment_digest.models import ImpactEvent
from slack_audit.deployment_digest.parser import parse_deployment
from slack_audit.deployment_digest.reporter import print_console_summary, write_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a weekly digest of Slack deployment activity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="All secrets must be provided via environment variables or a .env file.\n"
               "See .env.example for required variables.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        metavar="N",
        help="Lookback window in days (overrides DIGEST_LOOKBACK_DAYS).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="PATH",
        help="Directory to write the Markdown report (overrides OUTPUT_DIR).",
    )
    parser.add_argument(
        "--deployment-channel",
        default=None,
        metavar="CHANNEL",
        help="Slack channel ID or name for deployments (overrides SLACK_DEPLOYMENT_CHANNEL).",
    )
    parser.add_argument(
        "--impact-channel",
        default=None,
        metavar="CHANNEL",
        help="Slack channel ID or name for impact alerts (overrides SLACK_IMPACT_CHANNEL).",
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
    if not verbose:
        logging.getLogger("slack_sdk").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def main() -> None:
    load_dotenv()
    args = parse_args()
    _setup_logging(args.verbose)

    config = load_digest_config()

    # CLI flags override env-var defaults.
    if args.days is not None:
        config.lookback_days = args.days
    if args.output_dir is not None:
        config.output_dir = args.output_dir
    if args.deployment_channel is not None:
        config.deployment_channel = args.deployment_channel
    if args.impact_channel is not None:
        config.impact_channel = args.impact_channel

    until = datetime.now(tz=timezone.utc)
    since = until - timedelta(days=config.lookback_days)

    client = WebClient(token=config.slack_bot_token)

    logging.info(
        "Fetching deployments from #%s (past %d days)…",
        config.deployment_channel,
        config.lookback_days,
    )
    raw_deploys = fetch_messages(client, config.deployment_channel, since, until)
    logging.info("Fetched %d message(s) from deployment channel.", len(raw_deploys))

    logging.info("Fetching impact events from #%s…", config.impact_channel)
    raw_impacts = fetch_messages(client, config.impact_channel, since, until)
    logging.info("Fetched %d message(s) from impact channel.", len(raw_impacts))

    # Parse deployment messages. Messages arrive newest-first; iterate oldest-first.
    deployments = []
    for raw in reversed(raw_deploys):
        ts = raw.get("ts", "0")
        timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        event = parse_deployment(raw, timestamp)
        if event:
            deployments.append(event)

    logging.info("Parsed %d deployment event(s).", len(deployments))

    # Build impact events (all messages from that channel are potential signals).
    impact_events = []
    for raw in raw_impacts:
        text = raw.get("text", "").strip()
        if not text:
            continue
        ts = raw.get("ts", "0")
        timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        impact_events.append(ImpactEvent(ts=ts, timestamp=timestamp, message_text=text))

    logging.info("Found %d impact event(s).", len(impact_events))

    entries = correlate(deployments, impact_events, config.impact_window_minutes)

    print_console_summary(entries)

    output_path = Path(config.output_dir) / f"deployment_digest_{since.strftime('%Y%m%d')}_{until.strftime('%Y%m%d')}.md"
    write_markdown(entries, config, since, until, str(output_path))
    print(f"Digest written to: {output_path}")


if __name__ == "__main__":
    main()
