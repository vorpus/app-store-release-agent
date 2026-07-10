"""
Fetch live metadata for every app in the catalog and write it to disk.

Layout produced under ./metadata/:
  <app-slug>/
    bundle-id.txt
    app-id.txt
    live-version.txt
    <version>/
      <locale>/
        title.txt            (name)
        subtitle.txt
        keywords.txt
        description.txt
        whats-new.txt
        promotional-text.txt
        support-url.txt
        marketing-url.txt
        privacy-policy-url.txt

Required environment variables:
    ASC_ISSUER_ID
    ASC_KEY_ID
    ASC_PRIVATE_KEY_PATH
"""
import os
import re
import sys
import time
from pathlib import Path

import jwt
import requests

ROOT = Path(__file__).parent
BASE = "https://api.appstoreconnect.apple.com/v1"
OUT = ROOT / "metadata"


def _required_env(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Required environment variable {name} is not set; see README.md.")
    return val


ISSUER_ID = _required_env("ASC_ISSUER_ID")
KEY_ID = _required_env("ASC_KEY_ID")
KEY_PATH = Path(_required_env("ASC_PRIVATE_KEY_PATH"))


def make_token():
    key = KEY_PATH.read_text()
    now = int(time.time())
    return jwt.encode(
        {"iss": ISSUER_ID, "iat": now, "exp": now + 20 * 60, "aud": "appstoreconnect-v1"},
        key,
        algorithm="ES256",
        headers={"kid": KEY_ID, "typ": "JWT"},
    )


def get(path, params=None):
    r = requests.get(
        BASE + path,
        params=params,
        headers={"Authorization": f"Bearer {make_token()}"},
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code} on {path}: {r.text[:300]}")
    return r.json()


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[™®©]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def write(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is None or content == "":
        path.write_text("")
    else:
        path.write_text(content)


def fetch_app_localizations_for_app(app_id):
    """Returns list of (locale, title, subtitle, privacyPolicyUrl) for an app."""
    out = []
    infos = get(f"/apps/{app_id}/appInfos", {"limit": 10}).get("data", [])
    for info in infos:
        locs = get(
            f"/appInfos/{info['id']}/appInfoLocalizations", {"limit": 50}
        ).get("data", [])
        for loc in locs:
            a = loc["attributes"]
            out.append(
                (
                    a.get("locale"),
                    a.get("name"),
                    a.get("subtitle"),
                    a.get("privacyPolicyUrl"),
                )
            )
    return out


def fetch_version_localizations(version_id):
    """Returns list of (locale, description, keywords, whatsNew, ...) for a version."""
    out = []
    locs = get(
        f"/appStoreVersions/{version_id}/appStoreVersionLocalizations",
        {"limit": 50},
    ).get("data", [])
    for loc in locs:
        a = loc["attributes"]
        out.append(
            (
                a.get("locale"),
                a.get("description") or "",
                a.get("keywords") or "",
                a.get("whatsNew") or "",
                a.get("promotionalText") or "",
                a.get("supportUrl") or "",
                a.get("marketingUrl") or "",
            )
        )
    return out


def fetch_live_version(app_id):
    data = get(
        f"/apps/{app_id}/appStoreVersions",
        {"filter[appStoreState]": "READY_FOR_SALE", "limit": 1},
    ).get("data", [])
    if not data:
        return None
    return data[0]


def fetch_one_app(app):
    a = app["attributes"]
    app_id = app["id"]
    bundle_id = a.get("bundleId", "")
    name = a.get("name", "")
    slug = slugify(name)
    base = OUT / slug

    print(f"\n→ {name} ({bundle_id})")

    write(base / "bundle-id.txt", bundle_id)
    write(base / "app-id.txt", app_id)
    write(base / "name.txt", name)

    ver = fetch_live_version(app_id)
    if not ver:
        print("   · no live version, skipping per-version metadata")
        return

    version_string = ver["attributes"]["versionString"]
    write(base / "live-version.txt", version_string)
    print(f"   · live version: {version_string}")

    version_dir = base / version_string
    write(version_dir / "version-id.txt", ver["id"])

    app_locs = {l[0]: l for l in fetch_app_localizations_for_app(app_id)}
    ver_locs = {l[0]: l for l in fetch_version_localizations(ver["id"])}

    locales = sorted(set(app_locs) | set(ver_locs))
    if not locales:
        print("   · no localizations, skipping per-locale files")
        return

    for locale in locales:
        loc_dir = version_dir / locale
        a_loc = app_locs.get(locale)
        v_loc = ver_locs.get(locale)
        if a_loc:
            _, title, subtitle, privacy = a_loc
            write(loc_dir / "title.txt", title)
            write(loc_dir / "subtitle.txt", subtitle)
            write(loc_dir / "privacy-policy-url.txt", privacy)
        if v_loc:
            _, desc, kw, whats_new, promo, support, marketing = v_loc
            write(loc_dir / "description.txt", desc)
            write(loc_dir / "keywords.txt", kw)
            write(loc_dir / "whats-new.txt", whats_new)
            write(loc_dir / "promotional-text.txt", promo)
            write(loc_dir / "support-url.txt", support)
            write(loc_dir / "marketing-url.txt", marketing)

        present = []
        if a_loc:
            present.append("title")
        if v_loc:
            present.append("description/keywords/whatsNew")
        print(f"   · {locale}: {', '.join(present) or '(empty)'}")


def main():
    OUT.mkdir(exist_ok=True)
    apps = get("/apps", {"limit": 200}).get("data", [])
    print(f"Catalog: {len(apps)} app(s)")
    for app in apps:
        fetch_one_app(app)
    print(f"\nDone. Metadata written under {OUT}/")


if __name__ == "__main__":
    main()