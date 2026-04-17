"""Jira Cloud REST API client — read-only, paginated, rate-limit-aware.

Endpoints used:
  GET /rest/api/3/project/search  — paginated project inventory
  GET /rest/api/3/search          — JQL-based issue counting and date retrieval

Authentication: HTTP Basic Auth (email + API token).
All queries use resolution = Unresolved for backlog counts, not workflow status names.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Iterator, Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_BUFFER_SECONDS = 0.5
_PROJECT_PAGE_SIZE = 50   # Jira Cloud max for project/search
_ISSUE_COUNT_MAX = 0      # maxResults=0 returns total without issue data
_ISSUE_DATE_MAX = 1       # maxResults=1 fetches one issue for its date fields


def build_session(user_email: str, api_token: str) -> requests.Session:
    """Create a reusable session with auth and JSON headers pre-configured."""
    session = requests.Session()
    session.auth = HTTPBasicAuth(user_email, api_token)
    session.headers.update({"Accept": "application/json"})
    return session


def _get_with_retry(
    session: requests.Session,
    url: str,
    params: Optional[dict] = None,
) -> requests.Response:
    """GET with automatic retry on 429 rate-limit responses.

    Raises requests.HTTPError for non-recoverable HTTP errors.
    """
    for attempt in range(_MAX_RETRIES + 1):
        response = session.get(url, params=params, timeout=30)

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "1"))
            wait = retry_after + _RETRY_BUFFER_SECONDS
            logger.warning(
                "Rate limited. Waiting %.1fs (attempt %d/%d).",
                wait, attempt + 1, _MAX_RETRIES,
            )
            time.sleep(wait)
            if attempt == _MAX_RETRIES:
                response.raise_for_status()
            continue

        response.raise_for_status()
        return response

    # Unreachable, but satisfies type checkers.
    raise RuntimeError("Exceeded retry attempts without a successful response.")


def parse_jira_datetime(date_str: str) -> Optional[datetime]:
    """Parse a Jira ISO 8601 datetime string to a UTC-aware datetime.

    Handles Jira's compact timezone format (+0000) as well as the standard
    colon-separated form (+00:00).
    """
    if not date_str:
        return None
    try:
        # Normalize compact tz offset: +0530 → +05:30
        normalized = re.sub(r"([+-])(\d{2})(\d{2})$", r"\1\2:\3", date_str)
        dt = datetime.fromisoformat(normalized)
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        logger.debug("Could not parse datetime string: %r", date_str)
        return None


def iter_projects(session: requests.Session, base_url: str) -> Iterator[dict]:
    """Yield raw project dicts from /rest/api/3/project/search with full pagination."""
    url = f"{base_url}/rest/api/3/project/search"
    start_at = 0

    while True:
        params = {
            "startAt": start_at,
            "maxResults": _PROJECT_PAGE_SIZE,
            "expand": "lead",
        }

        try:
            response = _get_with_retry(session, url, params=params)
        except requests.HTTPError as exc:
            logger.error("Failed to fetch project list: %s", exc)
            return

        data = response.json()
        projects = data.get("values", [])
        for project in projects:
            yield project

        if data.get("isLast", True):
            break

        start_at += len(projects)


def _jql_count(session: requests.Session, base_url: str, jql: str) -> int:
    """Return the total number of issues matching a JQL query.

    Uses maxResults=0 so no issue data is returned — efficient for counting.
    """
    url = f"{base_url}/rest/api/3/search"
    params = {"jql": jql, "maxResults": _ISSUE_COUNT_MAX, "fields": ""}
    try:
        response = _get_with_retry(session, url, params=params)
        return int(response.json().get("total", 0))
    except requests.HTTPError as exc:
        logger.warning("JQL count failed (%r): %s", jql[:60], exc)
        return 0


def _jql_first_date(
    session: requests.Session,
    base_url: str,
    jql: str,
    field: str,
) -> Optional[datetime]:
    """Return the parsed date of the first issue matching a JQL query + ORDER BY.

    The `jql` argument should already include an ORDER BY clause.
    `field` is the Jira issue field name to read (e.g. 'created', 'updated').
    """
    url = f"{base_url}/rest/api/3/search"
    params = {"jql": jql, "maxResults": _ISSUE_DATE_MAX, "fields": field}
    try:
        response = _get_with_retry(session, url, params=params)
        issues = response.json().get("issues", [])
        if not issues:
            return None
        raw = issues[0].get("fields", {}).get(field)
        return parse_jira_datetime(raw) if raw else None
    except requests.HTTPError as exc:
        logger.warning("JQL date fetch failed (%r): %s", jql[:60], exc)
        return None


def _jql_first_with_count(
    session: requests.Session,
    base_url: str,
    jql: str,
    field: str,
) -> tuple[int, Optional[datetime]]:
    """Return (total_count, first_issue_date) in a single API call.

    Used to get unresolved count and oldest unresolved date together.
    The JQL should be ordered so that the 'first' result is the desired one.
    """
    url = f"{base_url}/rest/api/3/search"
    params = {"jql": jql, "maxResults": _ISSUE_DATE_MAX, "fields": field}
    try:
        response = _get_with_retry(session, url, params=params)
        data = response.json()
        total = int(data.get("total", 0))
        issues = data.get("issues", [])
        date: Optional[datetime] = None
        if issues:
            raw = issues[0].get("fields", {}).get(field)
            date = parse_jira_datetime(raw) if raw else None
        return total, date
    except requests.HTTPError as exc:
        logger.warning("JQL count+date failed (%r): %s", jql[:60], exc)
        return 0, None


def get_project_stats(
    session: requests.Session,
    base_url: str,
    project_key: str,
    days_lookback: int,
) -> dict:
    """Gather all activity metrics for a single project.

    Makes up to 5 JQL API calls per project:
      1. Unresolved count + oldest unresolved issue date
      2. Issues created in the last N days (count)
      3. Issues resolved in the last N days (count)
      4. Most recently created issue date
      5. Most recently updated issue date

    Returns a dict with keys:
      unresolved_count, oldest_unresolved_date,
      issues_created_last_n, issues_resolved_last_n,
      last_created_at, last_updated_at
    """
    k = project_key

    # 1. Unresolved count + oldest unresolved date (one call).
    unresolved_jql = (
        f'project = "{k}" AND resolution = Unresolved ORDER BY created ASC'
    )
    unresolved_count, oldest_unresolved_date = _jql_first_with_count(
        session, base_url, unresolved_jql, "created"
    )

    # 2. Issues created in the lookback window.
    created_count = _jql_count(
        session, base_url,
        f'project = "{k}" AND created >= -{days_lookback}d',
    )

    # 3. Issues resolved in the lookback window.
    resolved_count = _jql_count(
        session, base_url,
        f'project = "{k}" AND resolved >= -{days_lookback}d',
    )

    # 4. Most recently created issue.
    last_created_at = _jql_first_date(
        session, base_url,
        f'project = "{k}" ORDER BY created DESC',
        "created",
    )

    # 5. Most recently updated issue.
    last_updated_at = _jql_first_date(
        session, base_url,
        f'project = "{k}" ORDER BY updated DESC',
        "updated",
    )

    return {
        "unresolved_count": unresolved_count,
        "oldest_unresolved_date": oldest_unresolved_date,
        "issues_created_last_n": created_count,
        "issues_resolved_last_n": resolved_count,
        "last_created_at": last_created_at,
        "last_updated_at": last_updated_at,
    }
