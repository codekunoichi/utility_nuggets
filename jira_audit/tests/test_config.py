"""Tests for environment variable validation in config.py."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jira_audit.config import load_config, AuditConfig

_VALID_ENV = {
    "JIRA_BASE_URL": "https://example.atlassian.net",
    "JIRA_USER_EMAIL": "audit@example.com",
    "JIRA_API_TOKEN": "fake-api-token-for-tests",
    "JIRA_DAYS_LOOKBACK": "30",
    "JIRA_STALE_DAYS": "30",
    "JIRA_ACTIVE_ISSUE_THRESHOLD": "5",
    "JIRA_OVERLOADED_UNRESOLVED_THRESHOLD": "100",
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
    assert config.jira_base_url == "https://example.atlassian.net"
    assert config.jira_user_email == "audit@example.com"
    assert config.days_lookback == 30
    assert config.stale_days == 30
    assert config.active_issue_threshold == 5
    assert config.overloaded_unresolved_threshold == 100
    assert config.output_dir == "reports"
    assert set(config.output_formats) == {"csv", "json"}


def test_trailing_slash_stripped_from_base_url():
    config = _load_with({"JIRA_BASE_URL": "https://example.atlassian.net/"})
    assert not config.jira_base_url.endswith("/")


def test_defaults_applied_when_optional_vars_absent():
    minimal = {
        "JIRA_BASE_URL": "https://example.atlassian.net",
        "JIRA_USER_EMAIL": "audit@example.com",
        "JIRA_API_TOKEN": "token",
    }
    with patch.dict(os.environ, minimal, clear=True):
        config = load_config()
    assert config.days_lookback == 30
    assert config.active_issue_threshold == 5
    assert config.output_dir == "reports"
    assert "csv" in config.output_formats


def test_csv_only_format():
    config = _load_with({"OUTPUT_FORMATS": "csv"})
    assert config.output_formats == ["csv"]


def test_json_only_format():
    config = _load_with({"OUTPUT_FORMATS": "json"})
    assert config.output_formats == ["json"]


# ---------------------------------------------------------------------------
# Base URL validation
# ---------------------------------------------------------------------------

def test_missing_base_url_exits():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit):
            load_config()


def test_http_base_url_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_BASE_URL": "http://example.atlassian.net"})


def test_empty_base_url_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_BASE_URL": ""})


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------

def test_missing_email_exits():
    minimal = {
        "JIRA_BASE_URL": "https://example.atlassian.net",
        "JIRA_API_TOKEN": "token",
    }
    with patch.dict(os.environ, minimal, clear=True):
        with pytest.raises(SystemExit):
            load_config()


def test_invalid_email_format_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_USER_EMAIL": "not-an-email"})


# ---------------------------------------------------------------------------
# API token validation
# ---------------------------------------------------------------------------

def test_missing_api_token_exits():
    minimal = {
        "JIRA_BASE_URL": "https://example.atlassian.net",
        "JIRA_USER_EMAIL": "audit@example.com",
    }
    with patch.dict(os.environ, minimal, clear=True):
        with pytest.raises(SystemExit):
            load_config()


# ---------------------------------------------------------------------------
# Numeric validation
# ---------------------------------------------------------------------------

def test_non_integer_lookback_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_DAYS_LOOKBACK": "thirty"})


def test_zero_lookback_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_DAYS_LOOKBACK": "0"})


def test_negative_stale_days_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_STALE_DAYS": "-10"})


def test_non_integer_active_threshold_exits():
    with pytest.raises(SystemExit):
        _load_with({"JIRA_ACTIVE_ISSUE_THRESHOLD": "five"})


# ---------------------------------------------------------------------------
# Output format validation
# ---------------------------------------------------------------------------

def test_unknown_format_exits():
    with pytest.raises(SystemExit):
        _load_with({"OUTPUT_FORMATS": "csv,xml"})


# ---------------------------------------------------------------------------
# Credentials not leaked in repr
# ---------------------------------------------------------------------------

def test_repr_does_not_contain_api_token():
    config = _load_with({})
    assert config.jira_api_token not in repr(config)


def test_repr_does_not_contain_email():
    config = _load_with({})
    assert config.jira_user_email not in repr(config)
