"""Tests for time-proximity deployment/impact correlation."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from slack_audit.deployment_digest.correlator import correlate
from slack_audit.deployment_digest.models import DeploymentEvent, ImpactEvent

_BASE = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)


def _deploy(offset_minutes: int = 0, service: str = "svc") -> DeploymentEvent:
    dt = _BASE + timedelta(minutes=offset_minutes)
    return DeploymentEvent(
        ts=str(dt.timestamp()),
        timestamp=dt,
        service=service,
        version="v1.0.0",
        environment="prod",
        deployer="@bot",
        message_text=f"Deployed {service} v1.0.0 to prod",
    )


def _impact(offset_minutes: int) -> ImpactEvent:
    dt = _BASE + timedelta(minutes=offset_minutes)
    return ImpactEvent(
        ts=str(dt.timestamp()),
        timestamp=dt,
        message_text=f"Alert at +{offset_minutes}min",
    )


# ---------------------------------------------------------------------------
# Basic correlation
# ---------------------------------------------------------------------------

def test_impact_within_window_is_correlated():
    entries = correlate([_deploy(0)], [_impact(15)], window_minutes=30)
    assert len(entries) == 1
    assert len(entries[0].impacts) == 1


def test_impact_outside_window_is_excluded():
    entries = correlate([_deploy(0)], [_impact(45)], window_minutes=30)
    assert len(entries) == 1
    assert entries[0].impacts == []


def test_impact_at_exact_window_boundary_is_included():
    entries = correlate([_deploy(0)], [_impact(30)], window_minutes=30)
    assert len(entries) == 1
    assert len(entries[0].impacts) == 1


def test_impact_before_deploy_is_excluded():
    entries = correlate([_deploy(0)], [_impact(-5)], window_minutes=30)
    assert len(entries) == 1
    assert entries[0].impacts == []


def test_multiple_impacts_per_deploy():
    impacts = [_impact(5), _impact(15), _impact(25), _impact(35)]
    entries = correlate([_deploy(0)], impacts, window_minutes=30)
    assert len(entries[0].impacts) == 3  # 35 min is outside window


# ---------------------------------------------------------------------------
# Multiple deployments
# ---------------------------------------------------------------------------

def test_impacts_assigned_to_correct_deployment():
    deploy_a = _deploy(0, service="svc-a")
    deploy_b = _deploy(60, service="svc-b")
    # Impact at +10min → belongs to deploy_a; impact at +70min → belongs to deploy_b
    impact_a = _impact(10)
    impact_b = _impact(70)
    entries = correlate([deploy_a, deploy_b], [impact_a, impact_b], window_minutes=30)
    assert len(entries) == 2
    svc_a_entry = next(e for e in entries if e.deployment.service == "svc-a")
    svc_b_entry = next(e for e in entries if e.deployment.service == "svc-b")
    assert len(svc_a_entry.impacts) == 1
    assert len(svc_b_entry.impacts) == 1


def test_impact_can_match_overlapping_deploy_windows():
    # Two deploys 20 min apart with a 30-min window — impact at +25 min from first
    # falls in both windows. Each deploy should list it independently.
    deploy_a = _deploy(0, service="svc-a")
    deploy_b = _deploy(20, service="svc-b")
    shared_impact = _impact(25)
    entries = correlate([deploy_a, deploy_b], [shared_impact], window_minutes=30)
    a_entry = next(e for e in entries if e.deployment.service == "svc-a")
    b_entry = next(e for e in entries if e.deployment.service == "svc-b")
    assert len(a_entry.impacts) == 1
    assert len(b_entry.impacts) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_deployments_returns_empty():
    entries = correlate([], [_impact(10)], window_minutes=30)
    assert entries == []


def test_empty_impacts_returns_clean_entries():
    entries = correlate([_deploy(0), _deploy(60)], [], window_minutes=30)
    assert len(entries) == 2
    assert all(e.is_clean for e in entries)


def test_result_sorted_by_deployment_timestamp():
    deploys = [_deploy(60), _deploy(0), _deploy(120)]
    entries = correlate(deploys, [], window_minutes=30)
    timestamps = [e.deployment.timestamp for e in entries]
    assert timestamps == sorted(timestamps)
