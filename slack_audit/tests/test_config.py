"""Tests for environment variable validation in config.py."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slack_audit.config import load_config, AuditConfig

_VALID_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-valid-test-token",
    "SLACK_DAYS_LOOKBACK": "30",
    "SLACK_STALE_DAYS": "30",
    "SLACK_ACTIVE_MESSAGE_THRESHOLD": "10",
    "OUTPUT_DIR": "reports",
    "OUTPUT_FORMATS": "csv,json",
}


def _load_with(overrides: dict) -> AuditConfig:
    env = {**_VALID_ENV, **overrides}
    with patch.dict(os.environ, env, clear=True):
        return load_config()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_env_loads_correctly():
    config = _load_with({})
    assert config.days_lookback == 30
    assert config.stale_days == 30
    assert config.active_message_threshold == 10
    assert config.output_dir == "reports"
    assert set(config.output_formats) == {"csv", "json"}


def test_xoxp_token_accepted():
    config = _load_with({"SLACK_BOT_TOKEN": "xoxp-valid-user-token"})
    assert config.slack_bot_token == "xoxp-valid-user-token"


def test_csv_only_format():
    config = _load_with({"OUTPUT_FORMATS": "csv"})
    assert config.output_formats == ["csv"]


def test_json_only_format():
    config = _load_with({"OUTPUT_FORMATS": "json"})
    assert config.output_formats == ["json"]


def test_defaults_applied_when_optional_vars_absent():
    minimal_env = {"SLACK_BOT_TOKEN": "xoxb-minimal"}
    with patch.dict(os.environ, minimal_env, clear=True):
        config = load_config()
    assert config.days_lookback == 30
    assert config.stale_days == 30
    assert config.active_message_threshold == 10
    assert config.output_dir == "reports"
    assert "csv" in config.output_formats


# ---------------------------------------------------------------------------
# Token validation failures
# ---------------------------------------------------------------------------

def test_missing_token_exits():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            load_config()
    assert exc_info.value.code != 0


def test_empty_token_exits():
    with patch.dict(os.environ, {"SLACK_BOT_TOKEN": ""}, clear=True):
        with pytest.raises(SystemExit):
            load_config()


def test_invalid_token_prefix_exits():
    with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "not-a-real-token"}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            load_config()
    # The error message should not contain the token value.
    assert "not-a-real-token" not in str(exc_info.value.code or "")


# ---------------------------------------------------------------------------
# Numeric validation failures
# ---------------------------------------------------------------------------

def test_non_integer_lookback_exits():
    with pytest.raises(SystemExit):
        _load_with({"SLACK_DAYS_LOOKBACK": "thirty"})


def test_zero_lookback_exits():
    with pytest.raises(SystemExit):
        _load_with({"SLACK_DAYS_LOOKBACK": "0"})


def test_negative_stale_days_exits():
    with pytest.raises(SystemExit):
        _load_with({"SLACK_STALE_DAYS": "-5"})


def test_non_integer_active_threshold_exits():
    with pytest.raises(SystemExit):
        _load_with({"SLACK_ACTIVE_MESSAGE_THRESHOLD": "ten"})


# ---------------------------------------------------------------------------
# Output format validation
# ---------------------------------------------------------------------------

def test_unknown_format_exits():
    with pytest.raises(SystemExit):
        _load_with({"OUTPUT_FORMATS": "csv,xml"})


# ---------------------------------------------------------------------------
# Token not leaked in repr
# ---------------------------------------------------------------------------

def test_repr_does_not_contain_token():
    config = _load_with({})
    assert config.slack_bot_token not in repr(config)
