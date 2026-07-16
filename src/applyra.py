"""Optional, read-only Applyra ranking client.

This command never changes App Store Connect. It fetches ranking data into the
private ASC_WORKSPACE_DIR, reports the cached latest positions, and compares
those positions with a local comma-separated keyword field.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import requests

from workspace import workspace_dir


BASE_URL = "https://www.applyra.io/api/v1"
MAX_RETRIES = 4
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_slug(value: str) -> str:
    """Validate an app slug before it is used to construct a workspace path."""
    if not SLUG_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("app must be a lowercase hyphenated slug")
    return value


def validate_country(value: str) -> str:
    """Validate the ISO-style two-letter country argument."""
    value = value.upper()
    if not COUNTRY_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("country must be a two-letter code, e.g. US")
    return value


def api_key() -> str:
    """Read the provider credential without ever accepting it on the CLI."""
    key = (os.environ.get("APPLYRA_API_KEY") or "").strip()
    if not key:
        sys.exit("APPLYRA_API_KEY is required for --fetch; use an environment variable.")
    return key


def app_directory(slug: str, create: bool = False) -> Path:
    """Return the private per-app directory for a validated slug."""
    root = workspace_dir(create=create)
    path = root / slug
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_json_write(path: Path, payload: object) -> None:
    """Write private cache data atomically with owner-only permissions."""
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temp_name = handle.name
    os.chmod(temp_name, 0o600)
    os.replace(temp_name, path)


class ApplyraClient:
    """Small HTTPS-only client with bounded retry behavior for transient errors."""

    def __init__(self, key: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "X-API-Key": key,
            "Accept": "application/json",
        })

    def get(self, path: str, params: dict | None = None) -> object:
        """Fetch JSON without logging response bodies or authentication headers."""
        url = BASE_URL + path
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError("Applyra network request failed") from exc
                time.sleep(2 ** attempt)
                continue
            if response.status_code in {429, 502, 503, 504} and attempt < MAX_RETRIES:
                try:
                    delay = max(1, min(60, int(response.headers.get("Retry-After", ""))))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(delay)
                continue
            if not response.ok:
                raise RuntimeError(f"Applyra request failed with HTTP {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise RuntimeError("Applyra returned invalid JSON") from exc
        raise AssertionError("unreachable")


def read_applyra_app_id(slug: str) -> str:
    """Read the non-secret provider app ID from the private workspace."""
    path = app_directory(slug) / "applyra_app_id.txt"
    if not path.is_file():
        sys.exit(f"Missing {path}; create it in the private workspace first.")
    value = path.read_text(encoding="utf-8").strip()
    if not value or len(value) > 200:
        sys.exit("Applyra app ID must be a non-empty value up to 200 characters.")
    return value


def response_items(value: object) -> list[dict]:
    """Normalize common list wrappers without trusting an undocumented schema."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("data", "keywords"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    return []


def latest_positions(snapshot: dict) -> list[dict]:
    """Extract latest per-keyword ranks from documented and fallback shapes."""
    positions = []
    for item in snapshot.get("per_keyword", []):
        if not isinstance(item, dict) or not item.get("keyword"):
            continue
        history = item.get("ranks_history")
        apps = history.get("data", {}).get("apps", []) if isinstance(history, dict) else []
        if not apps and isinstance(history, dict):
            apps = history.get("apps", [])
        rank = None
        for app in apps if isinstance(apps, list) else []:
            rows = app.get("history", []) if isinstance(app, dict) else []
            if rows and isinstance(rows[-1], dict):
                rank = rows[-1].get("rank") or rows[-1].get("position")
                break
        positions.append({"keyword": str(item["keyword"]), "position": rank})
    return positions


def fetch_snapshot(slug: str, country: str) -> dict:
    """Fetch ranking data, retaining per-keyword failures as structured data."""
    provider_id = read_applyra_app_id(slug)
    client = ApplyraClient(api_key())
    encoded_id = quote(provider_id, safe="")
    scores = client.get(f"/applications/{encoded_id}/scores/history", {"country": country})
    keywords = client.get(f"/keywords?app_id={encoded_id}", {"country": country})
    per_keyword = []
    for keyword in response_items(keywords):
        keyword_id = keyword.get("id") or keyword.get("keyword_id")
        term = keyword.get("keyword") or keyword.get("term") or keyword.get("name")
        if keyword_id is None or not isinstance(term, str):
            continue
        try:
            history = client.get(
                f"/keywords/{quote(str(keyword_id), safe='')}/ranks/history",
                {"country": country},
            )
            per_keyword.append({"keyword": term, "ranks_history": history})
        except RuntimeError as exc:
            per_keyword.append({"keyword": term, "ranks_history": None, "error": str(exc)})
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "country": country,
        "app_id_applyra": provider_id,
        "app_scores_history": scores,
        "per_keyword": per_keyword,
    }


def cmd_fetch(args: argparse.Namespace) -> None:
    """Fetch and cache a private snapshot, optionally retaining a history copy."""
    payload = fetch_snapshot(args.app, args.country)
    app_dir = app_directory(args.app, create=True)
    current = app_dir / "applyra.json"
    atomic_json_write(current, payload)
    print(f"Wrote private cache: {current}")
    if args.history:
        history = app_dir / "applyra_history"
        history.mkdir(exist_ok=True)
        stamped = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ.json")
        atomic_json_write(history / stamped, payload)
        print(f"Wrote private history: {history / stamped}")


def read_snapshot(slug: str) -> dict:
    """Load the cached snapshot without contacting Applyra."""
    path = app_directory(slug) / "applyra.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"No cached snapshot at {path}; run --fetch first.")
    except json.JSONDecodeError as exc:
        sys.exit(f"Cached snapshot is invalid JSON: {exc.msg}")
    if not isinstance(data, dict):
        sys.exit("Cached snapshot must be a JSON object.")
    return data


def cmd_report(args: argparse.Namespace) -> None:
    """Print a credential-free ranking report from cached data."""
    snapshot = read_snapshot(args.app)
    print(f"Fetched: {snapshot.get('fetched_at', 'unknown')} ({snapshot.get('country', 'unknown')})")
    for item in sorted(latest_positions(snapshot), key=lambda row: (row["position"] is None, row["position"] or 0)):
        print(f"{item['keyword']}: {item['position'] if item['position'] is not None else '-'}")


def cmd_audit(args: argparse.Namespace) -> None:
    """Compare cached terms with an explicitly selected private keyword file."""
    snapshot = read_snapshot(args.app)
    keyword_file = app_directory(args.app) / args.version / args.locale / "keywords.txt"
    if not keyword_file.is_file():
        sys.exit(f"Keyword file not found: {keyword_file}")
    listing = {term.strip().casefold() for term in keyword_file.read_text().split(",") if term.strip()}
    ranked = {item["keyword"].casefold(): item["position"] for item in latest_positions(snapshot)}
    print("Listing terms without cached rank data:")
    for term in sorted(listing - set(ranked)):
        print(f"- {term}")
    print("Cached ranked terms absent from listing:")
    for term in sorted(set(ranked) - listing):
        print(f"- {term} (rank {ranked[term] if ranked[term] is not None else '-'})")


def main() -> None:
    """Parse the mutually exclusive read-only provider commands."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app", required=True, type=validate_slug)
    parser.add_argument("--country", default="US", type=validate_country)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fetch", action="store_true")
    modes.add_argument("--report", action="store_true")
    modes.add_argument("--audit", action="store_true")
    parser.add_argument("--history", action="store_true", help="retain a private dated snapshot with --fetch")
    parser.add_argument("--version", help="workspace version for --audit")
    parser.add_argument("--locale", default="en-US", help="locale for --audit")
    args = parser.parse_args()
    if args.audit and not args.version:
        parser.error("--audit requires --version")
    if args.history and not args.fetch:
        parser.error("--history is only valid with --fetch")
    if args.fetch:
        cmd_fetch(args)
    elif args.report:
        cmd_report(args)
    else:
        cmd_audit(args)


if __name__ == "__main__":
    main()
