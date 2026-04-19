"""Tests for deployment message parsing."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from slack_audit.deployment_digest.parser import parse_deployment

_BASE_TS = "1713528000.000000"
_BASE_DT = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)


def _msg(text: str, user: str = "U001BOT", **kwargs) -> dict:
    base = {"ts": _BASE_TS, "text": text, "user": user}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Known CI/CD bot message formats
# ---------------------------------------------------------------------------

def test_parses_github_actions_style():
    msg = _msg("Deployed api-service v2.1.4 to production by @alice")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.service == "api-service"
    assert event.version == "v2.1.4"
    assert event.environment == "production"
    assert event.deployer == "@alice"


def test_parses_argocd_style():
    msg = _msg("app: auth-service\nversion: v1.8.0\nenv: staging\nauthor: bob")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.service == "auth-service"
    assert event.version == "v1.8.0"
    assert event.environment == "staging"


def test_parses_deploying_prefix():
    msg = _msg("Deploying payment-service to prod")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.service == "payment-service"
    assert event.environment == "prod"


def test_parses_sha_as_version():
    msg = _msg("Deployed data-pipeline a3fe9e1 to production")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.service == "data-pipeline"
    assert event.version == "a3fe9e1"


def test_parses_semver_with_v_prefix():
    msg = _msg("Deployed frontend v3.0.0-rc.1 to staging by @ci-bot")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.version == "v3.0.0-rc.1"


def test_deployer_falls_back_to_user_field():
    msg = _msg("Deployed worker-service v1.0.0 to prod", user="U999DEPLOY")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.deployer == "U999DEPLOY"


def test_preserves_raw_message_text():
    text = "Deployed api-service v2.1.4 to production by @alice"
    msg = _msg(text)
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.message_text == text


def test_preserves_timestamp():
    msg = _msg("Deployed svc v1.0.0 to prod")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.ts == _BASE_TS
    assert event.timestamp == _BASE_DT


# ---------------------------------------------------------------------------
# Non-deployment messages return None
# ---------------------------------------------------------------------------

def test_returns_none_for_generic_message():
    msg = _msg("Hey team, heads up on the meeting at 3pm")
    assert parse_deployment(msg, _BASE_DT) is None


def test_returns_none_for_empty_text():
    msg = _msg("")
    assert parse_deployment(msg, _BASE_DT) is None


def test_returns_none_for_thread_reply():
    # Thread replies (subtype or parent_user_id) are noise — skip them.
    msg = _msg("LGTM!", subtype="thread_broadcast")
    assert parse_deployment(msg, _BASE_DT) is None


# ---------------------------------------------------------------------------
# Partial matches — service required, others optional
# ---------------------------------------------------------------------------

def test_partial_match_no_version():
    msg = _msg("Deployed notification-service to dev")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.service == "notification-service"
    assert event.version == ""


def test_partial_match_no_environment():
    msg = _msg("Deployed cache-service v0.9.1")
    event = parse_deployment(msg, _BASE_DT)
    assert event is not None
    assert event.service == "cache-service"
    assert event.environment == ""
