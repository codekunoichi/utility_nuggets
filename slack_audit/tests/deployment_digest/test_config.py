"""Tests for DigestConfig environment variable loading and validation."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from slack_audit.deployment_digest.config import load_digest_config, DigestConfig

_VALID_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-valid-test-token",
    "SLACK_DEPLOYMENT_CHANNEL": "C111DEPLOY",
    "SLACK_IMPACT_CHANNEL": "C222IMPACT",
    "DIGEST_LOOKBACK_DAYS": "7",
    "IMPACT_WINDOW_MINUTES": "30",
    "OUTPUT_DIR": "reports",
}


def _load_with(overrides: dict) -> DigestConfig:
    env = {**_VALID_ENV, **overrides}
    with patch.dict(os.environ, env, clear=True):
        return load_digest_config()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_env_loads_correctly():
    config = _load_with({})
    assert config.slack_bot_token == "xoxb-valid-test-token"
    assert config.deployment_channel == "C111DEPLOY"
    assert config.impact_channel == "C222IMPACT"
    assert config.lookback_days == 7
    assert config.impact_window_minutes == 30
    assert config.output_dir == "reports"


def test_xoxp_token_accepted():
    config = _load_with({"SLACK_BOT_TOKEN": "xoxp-user-token"})
    assert config.slack_bot_token == "xoxp-user-token"


def test_defaults_applied_when_optional_vars_absent():
    minimal = {
        "SLACK_BOT_TOKEN": "xoxb-minimal",
        "SLACK_DEPLOYMENT_CHANNEL": "C111DEPLOY",
        "SLACK_IMPACT_CHANNEL": "C222IMPACT",
    }
    with patch.dict(os.environ, minimal, clear=True):
        config = load_digest_config()
    assert config.lookback_days == 7
    assert config.impact_window_minutes == 30
    assert config.output_dir == "reports"


def test_custom_lookback_days():
    config = _load_with({"DIGEST_LOOKBACK_DAYS": "14"})
    assert config.lookback_days == 14


def test_custom_impact_window():
    config = _load_with({"IMPACT_WINDOW_MINUTES": "60"})
    assert config.impact_window_minutes == 60


# ---------------------------------------------------------------------------
# Token validation failures
# ---------------------------------------------------------------------------

def test_missing_token_exits():
    env = {k: v for k, v in _VALID_ENV.items() if k != "SLACK_BOT_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit):
            load_digest_config()


def test_invalid_token_prefix_exits():
    with pytest.raises(SystemExit):
        _load_with({"SLACK_BOT_TOKEN": "invalid-token"})


# ---------------------------------------------------------------------------
# Required channel validation
# ---------------------------------------------------------------------------

def test_missing_deployment_channel_exits():
    env = {k: v for k, v in _VALID_ENV.items() if k != "SLACK_DEPLOYMENT_CHANNEL"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit):
            load_digest_config()


def test_missing_impact_channel_exits():
    env = {k: v for k, v in _VALID_ENV.items() if k != "SLACK_IMPACT_CHANNEL"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit):
            load_digest_config()


# ---------------------------------------------------------------------------
# Numeric validation failures
# ---------------------------------------------------------------------------

def test_non_integer_lookback_exits():
    with pytest.raises(SystemExit):
        _load_with({"DIGEST_LOOKBACK_DAYS": "seven"})


def test_zero_lookback_exits():
    with pytest.raises(SystemExit):
        _load_with({"DIGEST_LOOKBACK_DAYS": "0"})


def test_negative_window_exits():
    with pytest.raises(SystemExit):
        _load_with({"IMPACT_WINDOW_MINUTES": "-5"})


# ---------------------------------------------------------------------------
# Token not leaked in repr
# ---------------------------------------------------------------------------

def test_repr_does_not_contain_token():
    config = _load_with({})
    assert config.slack_bot_token not in repr(config)
