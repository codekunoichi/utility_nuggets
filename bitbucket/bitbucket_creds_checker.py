"""
bitbucket_creds_checker.py
--------------------------
Shared auth helper for all Bitbucket scripts.

Bitbucket's API tokens with scopes (the replacement for app passwords) use
Basic auth: base64(username:token). Set both env vars before running any script.

Run directly to verify your credentials are configured correctly:
    export BITBUCKET_USERNAME="your_bitbucket_username"
    export BITBUCKET_TOKEN="your_api_token"
    export BITBUCKET_WORKSPACE="your_workspace_slug"
    python bitbucket_creds_checker.py
"""

import os
import sys
import base64
import requests


def make_auth_header():
    username = os.getenv("BITBUCKET_USERNAME")
    token = os.getenv("BITBUCKET_TOKEN")
    if not username:
        raise EnvironmentError(
            "BITBUCKET_USERNAME is not set. Set it to your Bitbucket account username."
        )
    if not token:
        raise EnvironmentError(
            "BITBUCKET_TOKEN is not set. "
            "Create an API token at Bitbucket > Account settings > API tokens "
            "with Repositories: Read scope."
        )
    encoded = base64.b64encode(f"{username}:{token}".encode("ascii")).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def check_credentials():
    errors = []

    username = os.getenv("BITBUCKET_USERNAME")
    token = os.getenv("BITBUCKET_TOKEN")
    workspace = os.getenv("BITBUCKET_WORKSPACE")

    errors.append(f"  BITBUCKET_USERNAME : {username if username else 'NOT SET'}")
    errors.append(f"  BITBUCKET_TOKEN    : {'set (' + str(len(token)) + ' chars)' if token else 'NOT SET'}")
    errors.append(f"  BITBUCKET_WORKSPACE: {workspace if workspace else 'NOT SET'}")

    print("\nEnvironment variables:")
    for line in errors:
        print(line)

    if not username or not token or not workspace:
        print("\n[FAIL] Missing required environment variables.\n")
        sys.exit(1)

    print("\nTesting API connection...")
    try:
        response = requests.get(
            f"https://api.bitbucket.org/2.0/repositories/{workspace}?pagelen=1",
            headers=make_auth_header(),
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            repo_count = data.get("size", "unknown")
            print(f"[OK] Connected — workspace '{workspace}' has {repo_count} repositories.\n")
        elif response.status_code == 401:
            print("[FAIL] 401 Unauthorized — token is invalid or expired.\n")
            sys.exit(1)
        elif response.status_code == 403:
            print("[FAIL] 403 Forbidden — token lacks Repositories: Read scope.\n")
            sys.exit(1)
        elif response.status_code == 404:
            print(f"[FAIL] 404 Not Found — workspace '{workspace}' does not exist or is not accessible.\n")
            sys.exit(1)
        else:
            print(f"[FAIL] Unexpected response: {response.status_code} — {response.text[:200]}\n")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("[FAIL] Could not reach api.bitbucket.org — check your network connection.\n")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("[FAIL] Request timed out.\n")
        sys.exit(1)


if __name__ == "__main__":
    check_credentials()
