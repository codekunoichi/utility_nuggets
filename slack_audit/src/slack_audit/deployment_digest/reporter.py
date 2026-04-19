"""Generate the weekly deployment digest Markdown report."""

import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from slack_audit.deployment_digest.config import DigestConfig
from slack_audit.deployment_digest.models import DigestEntry


def write_markdown(
    entries: list[DigestEntry],
    config: DigestConfig,
    since: datetime,
    until: datetime,
    output_path: str,
) -> None:
    """Write the full Markdown digest to output_path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    content = _render(entries, config, since, until)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(content)


def print_console_summary(entries: list[DigestEntry]) -> None:
    """Print a brief summary to stdout."""
    total = len(entries)
    impacted = sum(1 for e in entries if not e.is_clean)
    services = {e.deployment.service for e in entries}
    print(f"Deployments: {total} | Services: {len(services)} | With impacts: {impacted} | Clean: {total - impacted}")


def _render(
    entries: list[DigestEntry],
    config: DigestConfig,
    since: datetime,
    until: datetime,
) -> str:
    generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    period_start = since.strftime("%a %b %-d")
    period_end = until.strftime("%a %b %-d, %Y")

    total = len(entries)
    services = {e.deployment.service for e in entries}
    impacted = [e for e in entries if not e.is_clean]
    clean = [e for e in entries if e.is_clean]

    lines: list[str] = []
    lines.append("# Weekly Deployment Digest")
    lines.append(f"**Period:** {period_start} – {period_end} | **Generated:** {generated}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total deployments | {total} |")
    lines.append(f"| Unique services | {len(services)} |")
    lines.append(f"| Deployments with nearby impacts | {len(impacted)} |")
    lines.append(f"| Clean deployments | {len(clean)} |")
    lines.append("")

    # Day-by-day table
    lines.append("## Deployments by Day")
    lines.append("")
    by_day: dict[str, list[DigestEntry]] = defaultdict(list)
    for entry in entries:
        day_key = entry.deployment.timestamp.strftime("%A, %B %-d")
        by_day[day_key].append(entry)

    for day, day_entries in by_day.items():
        lines.append(f"### {day}")
        lines.append("")
        lines.append("| Time (UTC) | Service | Version | Environment | Deployer |")
        lines.append("|------------|---------|---------|-------------|----------|")
        for entry in day_entries:
            d = entry.deployment
            time_str = d.timestamp.strftime("%H:%M")
            lines.append(
                f"| {time_str} | {d.service} | {d.version or '—'} | {d.environment or '—'} | {d.deployer or '—'} |"
            )
        lines.append("")

    # Impact analysis
    lines.append("## Post-Deployment Impact Analysis")
    lines.append("")

    if impacted:
        lines.append(f"### Deployments with Nearby Incidents (within {config.impact_window_minutes} min)")
        lines.append("")
        for entry in impacted:
            d = entry.deployment
            deploy_time = d.timestamp.strftime("%a %b %-d, %H:%M UTC")
            env = f" → {d.environment}" if d.environment else ""
            lines.append(f"**{d.service} {d.version}**{env} ({deploy_time})")
            for impact in entry.impacts:
                delta_min = int((impact.timestamp - d.timestamp).total_seconds() / 60)
                impact_time = impact.timestamp.strftime("%H:%M")
                lines.append(
                    f"- [{impact_time}] \"{impact.message_text}\" _({delta_min} min after deploy)_"
                )
            lines.append("")
    else:
        lines.append("No post-deployment impacts detected in any deploy window.")
        lines.append("")

    if clean:
        lines.append("### Clean Deployments")
        lines.append("")
        for entry in clean:
            d = entry.deployment
            deploy_time = d.timestamp.strftime("%a %b %-d, %H:%M")
            env = f" → {d.environment}" if d.environment else ""
            lines.append(
                f"- {d.service} {d.version}{env} ({deploy_time}) — no impacts in "
                f"{config.impact_window_minutes}-min window"
            )
        lines.append("")

    return "\n".join(lines)
