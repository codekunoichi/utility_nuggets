"""Data models for the deployment digest tool."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DeploymentEvent:
    """A single deployment parsed from the deployments Slack channel."""

    ts: str
    timestamp: datetime
    service: str
    version: str
    environment: str
    deployer: str
    message_text: str


@dataclass
class ImpactEvent:
    """A message from the impact/alert channel that may relate to a deployment."""

    ts: str
    timestamp: datetime
    message_text: str


@dataclass
class DigestEntry:
    """A deployment paired with any correlated impact events."""

    deployment: DeploymentEvent
    impacts: list[ImpactEvent] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.impacts) == 0
