"""Time-proximity correlation between deployment and impact events."""

from datetime import timedelta

from slack_audit.deployment_digest.models import DeploymentEvent, DigestEntry, ImpactEvent


def correlate(
    deployments: list[DeploymentEvent],
    impact_events: list[ImpactEvent],
    window_minutes: int,
) -> list[DigestEntry]:
    """Match each deployment with impact events within the post-deploy window.

    An impact event is included if:
        deploy.timestamp <= event.timestamp <= deploy.timestamp + window

    A single impact event can appear under multiple deployments when their
    windows overlap — each deployment's list is independent.

    Returns DigestEntry list sorted by deployment timestamp ascending.
    """
    window = timedelta(minutes=window_minutes)
    sorted_deploys = sorted(deployments, key=lambda d: d.timestamp)
    entries: list[DigestEntry] = []

    for deploy in sorted_deploys:
        window_end = deploy.timestamp + window
        matched = [
            evt for evt in impact_events
            if deploy.timestamp <= evt.timestamp <= window_end
        ]
        entries.append(DigestEntry(deployment=deploy, impacts=matched))

    return entries
