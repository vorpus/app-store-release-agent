"""
Smoke test: connect to App Store Connect and list all live apps + current
live version. Run this after credential setup to verify connectivity
before doing any mutating operation.

Required environment variables:
    ASC_ISSUER_ID              uuid from App Store Connect → Keys
    ASC_KEY_ID                 10-char key id matching your AuthKey_*.p8
    ASC_PRIVATE_KEY_PATH       absolute path to your AuthKey_*.p8 file
"""
import os
import sys
import time
import jwt
import requests
from pathlib import Path

ROOT = Path(__file__).parent


def _required_env(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Required environment variable {name} is not set; see README.md.")
    return val


ISSUER_ID = _required_env("ASC_ISSUER_ID")
KEY_ID = _required_env("ASC_KEY_ID")
KEY_PATH = Path(_required_env("ASC_PRIVATE_KEY_PATH"))
BASE = "https://api.appstoreconnect.apple.com/v1"


def make_token():
    with open(KEY_PATH) as f:
        private_key = f.read()
    now = int(time.time())
    payload = {
        "iss": ISSUER_ID,
        "iat": now,
        "exp": now + 20 * 60,  # 20 min
        "aud": "appstoreconnect-v1",
    }
    headers = {"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def get(path, params=None):
    token = make_token()
    r = requests.get(
        BASE + path,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code} on {path}: {r.text[:500]}")
    return r.json()


def list_apps():
    data = get("/apps", {"limit": 200})
    return data.get("data", [])


def live_version_for(app_id):
    """Return the current live version string for an app, or None.

    Navigates the app → appStoreVersions relationship and filters for
    state == READY_FOR_SALE. The top-level /appStoreVersions collection
    is forbidden for this key (GET_COLLECTION not allowed), but the
    per-app relationship URL works.
    """
    try:
        data = get(
            f"/apps/{app_id}/appStoreVersions",
            {"filter[appStoreState]": "READY_FOR_SALE", "limit": 1},
        )
    except SystemExit:
        return None
    versions = data.get("data", [])
    if not versions:
        return None
    return versions[0]["attributes"].get("versionString")


def main():
    print(f"Issuer:  {ISSUER_ID}")
    print(f"Key ID:  {KEY_ID}")
    print(f"Key:     {KEY_PATH.name}\n")

    apps = list_apps()
    print(f"Found {len(apps)} app(s):\n")
    print(f"{'Name':<35} {'Bundle ID':<45} {'Live ver':<10} {'SKU'}")
    print("-" * 110)
    for app in apps:
        a = app["attributes"]
        name = a.get("name", "")
        bid = a.get("bundleId", "")
        sku = a.get("sku", "")
        print(f"  → {bid}", end="", flush=True)
        live = live_version_for(app["id"])
        marker = "✓" if live else "·"
        print(f"\r{marker} {name:<33} {bid:<45} {live or '—':<10} {sku}")


if __name__ == "__main__":
    main()