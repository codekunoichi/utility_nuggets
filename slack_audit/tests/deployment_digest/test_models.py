"""Tests for DeploymentEvent, ImpactEvent, and DigestEntry data models."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from slack_audit.deployment_digest.models import DeploymentEvent, ImpactEvent, DigestEntry

_TS = "1713528000.000000"
_DT = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)


def _make_deployment(**kwargs) -> DeploymentEvent:
    defaults = dict(
        ts=_TS,
        timestamp=_DT,
        service="api-service",
        version="v2.1.4",
        environment="production",
        deployer="@alice",
        message_text="Deployed api-service v2.1.4 to production by @alice",
    )
    return DeploymentEvent(**{**defaults, **kwargs})


def _make_impact(**kwargs) -> ImpactEvent:
    defaults = dict(
        ts="1713529800.000000",
        timestamp=datetime(2026, 4, 19, 12, 30, 0, tzinfo=timezone.utc),
        message_text="High error rate detected",
    )
    return ImpactEvent(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# DeploymentEvent
# ---------------------------------------------------------------------------

def test_deployment_event_stores_all_fields():
    d = _make_deployment()
    assert d.ts == _TS
    assert d.timestamp == _DT
    assert d.service == "api-service"
    assert d.version == "v2.1.4"
    assert d.environment == "production"
    assert d.deployer == "@alice"
    assert "api-service" in d.message_text


def test_deployment_event_allows_empty_version():
    d = _make_deployment(version="")
    assert d.version == ""


def test_deployment_event_allows_empty_environment():
    d = _make_deployment(environment="")
    assert d.environment == ""


def test_deployment_event_allows_empty_deployer():
    d = _make_deployment(deployer="")
    assert d.deployer == ""


# ---------------------------------------------------------------------------
# ImpactEvent
# ---------------------------------------------------------------------------

def test_impact_event_stores_all_fields():
    i = _make_impact()
    assert i.ts == "1713529800.000000"
    assert i.message_text == "High error rate detected"
    assert i.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# DigestEntry
# ---------------------------------------------------------------------------

def test_digest_entry_clean_deploy():
    entry = DigestEntry(deployment=_make_deployment(), impacts=[])
    assert entry.impacts == []
    assert entry.is_clean


def test_digest_entry_with_impacts():
    impacts = [_make_impact(), _make_impact()]
    entry = DigestEntry(deployment=_make_deployment(), impacts=impacts)
    assert len(entry.impacts) == 2
    assert not entry.is_clean


def test_digest_entry_exposes_deployment():
    d = _make_deployment()
    entry = DigestEntry(deployment=d, impacts=[])
    assert entry.deployment is d
