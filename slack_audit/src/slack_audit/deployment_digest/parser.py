"""Parse structured bot/webhook deployment messages from Slack."""

import logging
import re
from datetime import datetime
from typing import Optional

from slack_audit.deployment_digest.models import DeploymentEvent

logger = logging.getLogger(__name__)

# Matches "v1.2.3", "v3.0.0-rc.1", or a short git SHA (6-40 hex chars).
_RE_VERSION = re.compile(
    r"\b(v\d+\.\d+[\w.\-]*|\b[0-9a-f]{6,40}\b)"
)

# Matches environment names after "to <env>" pattern.
_RE_ENV = re.compile(
    r"\bto\s+(prod(?:uction)?|staging|dev(?:elopment)?|qa|sandbox|uat)\b",
    re.IGNORECASE,
)

# Matches "env: <value>" or "environment: <value>" (ArgoCD / generic YAML-style).
_RE_ENV_KV = re.compile(r"\benv(?:ironment)?:\s*(\S+)", re.IGNORECASE)

# Matches "by @<user>" or "author: <user>".
_RE_DEPLOYER = re.compile(r"\bby\s+(@\S+)|\bauthor:\s*(\S+)", re.IGNORECASE)

# Matches "Deployed <service>", "Deploying <service>", "Deploy <service>".
_RE_DEPLOY_VERB = re.compile(r"\bDeploy(?:ed|ing)?\s+([\w.\-]+)", re.IGNORECASE)

# Matches "app: <service>" or "service: <service>".
_RE_SERVICE_KV = re.compile(r"\b(?:app|service):\s*([\w.\-]+)", re.IGNORECASE)

# Deployment signal: message must contain at least one of these triggers.
# Also matches ArgoCD-style KV payloads that have "app:" + "version:" together.
_DEPLOYMENT_TRIGGERS = re.compile(
    r"\b(?:deploy(?:ed|ing)?|released?|rollout|pushed\s+to)\b"
    r"|(?=[\s\S]*\bapp:\s*\S)(?=[\s\S]*\bversion:\s*\S)",
    re.IGNORECASE,
)


def parse_deployment(msg: dict, timestamp: datetime) -> Optional[DeploymentEvent]:
    """Parse a raw Slack message dict into a DeploymentEvent.

    Returns None if the message does not look like a deployment notification.
    """
    # Skip thread noise.
    if msg.get("subtype") in ("thread_broadcast", "bot_message_deleted"):
        return None

    text: str = msg.get("text", "").strip()
    if not text:
        return None

    if not _DEPLOYMENT_TRIGGERS.search(text):
        logger.debug("No deployment trigger found in message: %.80s", text)
        return None

    service = _extract_service(text)
    if not service:
        logger.debug("Could not extract service name from: %.80s", text)
        return None

    version = _extract_version(text, service)
    environment = _extract_environment(text)
    deployer = _extract_deployer(text) or msg.get("user", "")

    return DeploymentEvent(
        ts=msg["ts"],
        timestamp=timestamp,
        service=service,
        version=version,
        environment=environment,
        deployer=deployer,
        message_text=text,
    )


def _extract_service(text: str) -> str:
    # "Deployed <service>" / "Deploying <service>"
    m = _RE_DEPLOY_VERB.search(text)
    if m:
        return m.group(1)

    # "app: <service>" / "service: <service>"
    m = _RE_SERVICE_KV.search(text)
    if m:
        return m.group(1)

    return ""


def _extract_version(text: str, service: str) -> str:
    for m in _RE_VERSION.finditer(text):
        candidate = m.group(1)
        # Avoid matching the service name itself if it looks like a SHA
        if candidate == service:
            continue
        return candidate
    return ""


def _extract_environment(text: str) -> str:
    # Prefer "to <env>" pattern.
    m = _RE_ENV.search(text)
    if m:
        return m.group(1).lower()

    # Fall back to key-value pattern.
    m = _RE_ENV_KV.search(text)
    if m:
        return m.group(1).lower()

    return ""


def _extract_deployer(text: str) -> str:
    m = _RE_DEPLOYER.search(text)
    if m:
        return m.group(1) or m.group(2) or ""
    return ""
