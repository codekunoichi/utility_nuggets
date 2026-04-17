#!/usr/bin/env python3
"""Jira Project Activity Audit Tool — entry point.

Run with:
    python main.py
    python main.py --days 60 --output-dir reports --formats csv json
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from tqdm import tqdm

from jira_audit.api import build_session, get_project_stats, iter_projects
from jira_audit.classifier import classify_project, compute_flow_ratio
from jira_audit.config import load_config
from jira_audit.models import ProjectRecord
from jira_audit.reporter import print_console_summary, write_csv, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Jira project audit: activity levels, backlog health, "
            "and flow signals."
        ),
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
        help="Lookback window in days (overrides JIRA_DAYS_LOOKBACK env var).",
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
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


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

    logging.info(
        "Starting audit — lookback: %d days, stale threshold: %d days, "
        "active threshold: %d issues, overloaded threshold: %d unresolved.",
        config.days_lookback,
        config.stale_days,
        config.active_issue_threshold,
        config.overloaded_unresolved_threshold,
    )

    session = build_session(config.jira_user_email, config.jira_api_token)
    now = datetime.now(timezone.utc)

    # Phase 1: collect project list.
    logging.info("Fetching project list from %s …", config.jira_base_url)
    raw_projects = list(iter_projects(session, config.jira_base_url))
    logging.info("Found %d accessible project(s).", len(raw_projects))

    if not raw_projects:
        logging.warning(
            "No projects found. Check JIRA_BASE_URL, credentials, and permissions."
        )
        return

    # Phase 2: gather per-project activity stats and build records.
    records: list[ProjectRecord] = []

    for raw in tqdm(raw_projects, desc="Auditing projects", unit="project"):
        project_key: str = raw.get("key", "")
        project_name: str = raw.get("name", project_key)
        project_type: str = raw.get("projectTypeKey", "")
        lead_info = raw.get("lead") or {}
        project_lead: str = lead_info.get("displayName", "")

        stats = get_project_stats(
            session,
            config.jira_base_url,
            project_key,
            config.days_lookback,
        )

        unresolved_count: int = stats["unresolved_count"]
        oldest_unresolved_date: datetime | None = stats["oldest_unresolved_date"]
        issues_created: int = stats["issues_created_last_n"]
        issues_resolved: int = stats["issues_resolved_last_n"]
        last_created_at: datetime | None = stats["last_created_at"]
        last_updated_at: datetime | None = stats["last_updated_at"]

        oldest_unresolved_age_days: int | None = None
        if oldest_unresolved_date is not None:
            if oldest_unresolved_date.tzinfo is None:
                oldest_unresolved_date = oldest_unresolved_date.replace(
                    tzinfo=timezone.utc
                )
            oldest_unresolved_age_days = (now - oldest_unresolved_date).days

        flow_ratio = compute_flow_ratio(issues_resolved, issues_created)

        activity_bucket, notes = classify_project(
            unresolved_count=unresolved_count,
            issues_created_last_n=issues_created,
            issues_resolved_last_n=issues_resolved,
            last_issue_updated_at=last_updated_at,
            flow_ratio=flow_ratio,
            active_threshold=config.active_issue_threshold,
            overloaded_threshold=config.overloaded_unresolved_threshold,
            _now=now,
        )

        records.append(
            ProjectRecord(
                project_key=project_key,
                project_name=project_name,
                project_type=project_type,
                project_lead=project_lead,
                unresolved_issue_count=unresolved_count,
                issues_created_last_n_days=issues_created,
                issues_resolved_last_n_days=issues_resolved,
                last_issue_created_at=last_created_at,
                last_issue_updated_at=last_updated_at,
                oldest_unresolved_issue_age_days=oldest_unresolved_age_days,
                flow_ratio=flow_ratio,
                activity_bucket=activity_bucket,
                notes=notes,
            )
        )

    # Phase 3: write outputs.
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
