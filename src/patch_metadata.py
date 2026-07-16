"""
ASO release toolkit — patch App Store Connect metadata, attach a build, or
submit for App Review, for one app.

Four operating modes (mutually exclusive):

  1. Metadata PATCH  (--locale --field --file)
     PATCH keywords/whats-new/title/subtitle/etc on a version localization.

  2. Build attachment  (--attach-build BUILD_ID)
     PATCH a build id onto the version's `relationships/build`.

  3. Submit for review  (--submit-for-review)
     The modern 3-step /v1/reviewSubmissions flow: create a submission
     shell, attach the in-flight version as an item, then PATCH
     `submitted:true` to commit. The legacy /v1/appStoreVersionSubmissions
     endpoint is deprecated and returns 403 for keys with the modern
    permission set — do not use it.

  4. Upload screenshots  (--upload-screenshots DIR)
     Upload validated PNGs to an editable version. Existing screenshots are
     refused unless --append-screenshots is explicitly supplied.

All three modes default to dry-run. Pass --apply to actually mutate the
App Store Connect API.

Required environment variables:
    ASC_ISSUER_ID
    ASC_KEY_ID
    ASC_PRIVATE_KEY_PATH
    ASC_WORKSPACE_DIR
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import jwt
import requests
from workspace import workspace_dir

ROOT = Path(__file__).parent
META = workspace_dir()
BASE = "https://api.appstoreconnect.apple.com/v1"


def _required_env(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Required environment variable {name} is not set; see README.md.")
    return val


ISSUER_ID = _required_env("ASC_ISSUER_ID")
KEY_ID = _required_env("ASC_KEY_ID")
KEY_PATH = Path(_required_env("ASC_PRIVATE_KEY_PATH"))

# Fields that live on AppInfoLocalizations (name = title, subtitle, privacy)
APP_INFO_FIELDS = {"title", "subtitle", "privacy-policy-url"}
# Fields that live on AppStoreVersionLocalizations
VERSION_FIELDS = {
    "description",
    "keywords",
    "whats-new",
    "promotional-text",
    "support-url",
    "marketing-url",
}
# Map our CLI field names to the JSON attribute names Apple expects
FIELD_TO_ATTR = {
    "title": "name",
    "subtitle": "subtitle",
    "privacy-policy-url": "privacyPolicyUrl",
    "description": "description",
    "keywords": "keywords",
    "whats-new": "whatsNew",
    "promotional-text": "promotionalText",
    "support-url": "supportUrl",
    "marketing-url": "marketingUrl",
}


def make_token():
    key = KEY_PATH.read_text()
    now = int(time.time())
    return jwt.encode(
        {"iss": ISSUER_ID, "iat": now, "exp": now + 20 * 60, "aud": "appstoreconnect-v1"},
        key,
        algorithm="ES256",
        headers={"kid": KEY_ID, "typ": "JWT"},
    )


def auth_headers():
    return {"Authorization": f"Bearer {make_token()}"}


def get(path, params=None):
    r = requests.get(
        BASE + path,
        params=params,
        headers=auth_headers(),
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code} on GET {path}: {r.text[:300]}")
    return r.json()


def patch(path, body):
    r = requests.patch(
        BASE + path,
        json=body,
        headers={**auth_headers(), "Content-Type": "application/json"},
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code} on PATCH {path}: {r.text[:500]}")
    return r.json()


def post(path, body):
    r = requests.post(
        BASE + path,
        json=body,
        headers={**auth_headers(), "Content-Type": "application/json"},
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code} on POST {path}: {r.text[:500]}")
    return r.json() if r.text else {}


def submit_version_for_review(version_id: str):
    """[Legacy endpoint — kept only as a named call site so we don't get
    back into the same endpoint later; do not call.] Old flow used
    POST /v1/appStoreVersionSubmissions, which is no longer the canonical
    submission endpoint for App Store Connect keys provisioned after the
    migration to the review-submissions model. The current flow lives in
    cmd_submit_for_review and uses three steps against /v1/reviewSubmissions
    plus /v1/reviewSubmissionItems."""
    raise NotImplementedError(
        "Legacy /v1/appStoreVersionSubmissions endpoint is deprecated; "
        "use --submit-for-review (uses the current 3-step reviewSubmissions flow)."
    )


def list_open_review_submissions(app_id: str):
    """Returns reviewSubmissions in any open state (READY_FOR_REVIEW,
    WAITING_FOR_REVIEW, IN_REVIEW) for the given app. Apple requires
    filter[app] on this collection — without it the response is HTTP 400."""
    r = get("/reviewSubmissions", {"filter[app]": app_id, "limit": 50})
    return r.get("data", [])


def get_review_submission_state(submission_id: str):
    """Returns the state string for a submission, e.g. 'READY_FOR_REVIEW'."""
    r = get(f"/reviewSubmissions/{submission_id}")
    return r["data"]["attributes"].get("state")


def create_review_submission(app_id: str):
    """POST /v1/reviewSubmissions — step 1 of the modern flow. Returns
    the full response; the new submission id is in response['data']['id']."""
    body = {
        "data": {
            "type": "reviewSubmissions",
            "attributes": {"platform": "IOS"},
            "relationships": {
                "app": {"data": {"type": "apps", "id": app_id}},
            },
        }
    }
    return post("/reviewSubmissions", body)


def attach_version_to_submission(submission_id: str, version_id: str):
    """POST /v1/reviewSubmissionItems — step 2. Adds the version as an
    item on the submission. Returns the new item resource."""
    body = {
        "data": {
            "type": "reviewSubmissionItems",
            "relationships": {
                "reviewSubmission": {
                    "data": {
                        "type": "reviewSubmissions",
                        "id": submission_id,
                    }
                },
                "appStoreVersion": {
                    "data": {
                        "type": "appStoreVersions",
                        "id": version_id,
                    }
                },
            },
        }
    }
    return post("/reviewSubmissionItems", body)


def commit_review_submission(submission_id: str):
    """PATCH /v1/reviewSubmissions/{id} with submitted:true — step 3 and
    the point of no return. Apple rejects with HTTP 409
    STATE_ERROR.ENTITY_STATE_INVALID if step 2 was skipped; reflects back
    the new state and submittedDate."""
    body = {
        "data": {
            "type": "reviewSubmissions",
            "id": submission_id,
            "attributes": {"submitted": True},
        }
    }
    return patch(f"/reviewSubmissions/{submission_id}", body)


def find_screenshot_set(localization_id: str, display_type: str):
    """Return an existing screenshot set and its asset count, if present."""
    sets = get(
        f"/appStoreVersionLocalizations/{localization_id}/appScreenshotSets",
        {"limit": 50},
    ).get("data", [])
    for screenshot_set in sets:
        if screenshot_set["attributes"].get("screenshotDisplayType") == display_type:
            assets = get(
                f"/appScreenshotSets/{screenshot_set['id']}/appScreenshots",
                {"limit": 50},
            ).get("data", [])
            return screenshot_set["id"], len(assets)
    return None, 0


def create_screenshot_set(localization_id: str, display_type: str) -> str:
    """Create the set for one localization/display-type pair."""
    body = {
        "data": {
            "type": "appScreenshotSets",
            "attributes": {"screenshotDisplayType": display_type},
            "relationships": {
                "appStoreVersionLocalization": {
                    "data": {"type": "appStoreVersionLocalizations", "id": localization_id}
                }
            },
        }
    }
    return post("/appScreenshotSets", body)["data"]["id"]


def validate_png(path: Path) -> tuple[bytes, int, int]:
    """Read one regular, bounded PNG and return its bytes and IHDR dimensions."""
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"screenshot must be a regular file, not a symlink: {path}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_SCREENSHOT_BYTES:
        raise SystemExit(f"screenshot size must be 1..{MAX_SCREENSHOT_BYTES} bytes: {path.name}")
    data = path.read_bytes()
    if data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR" or len(data) < 24:
        raise SystemExit(f"not a valid PNG with an IHDR header: {path.name}")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if not width or not height:
        raise SystemExit(f"PNG dimensions must be nonzero: {path.name}")
    return data, width, height


def upload_one_screenshot(set_id: str, path: Path) -> str:
    """Reserve, securely upload, and commit one validated screenshot asset."""
    data, _, _ = validate_png(path)
    reservation = post(
        "/appScreenshots",
        {
            "data": {
                "type": "appScreenshots",
                "attributes": {"fileName": path.name, "fileSize": len(data)},
                "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": set_id}}},
            }
        },
    )
    screenshot_id = reservation["data"]["id"]
    operations = reservation["data"]["attributes"].get("uploadOperations", [])
    if not operations:
        raise SystemExit(f"Apple returned no upload operations for {path.name}")
    covered = 0
    for operation in operations:
        offset, length = operation.get("offset"), operation.get("length")
        if not isinstance(offset, int) or not isinstance(length, int) or offset != covered or length <= 0:
            raise SystemExit(f"Apple returned invalid upload operations for {path.name}")
        url = operation.get("url", "")
        if urlparse(url).scheme != "https":
            raise SystemExit("refusing a non-HTTPS presigned upload URL")
        chunk = data[offset:offset + length]
        if len(chunk) != length:
            raise SystemExit(f"upload operation exceeds file length for {path.name}")
        headers = {item["name"]: item["value"] for item in operation.get("requestHeaders", [])}
        response = requests.put(url, data=chunk, headers=headers, timeout=180, allow_redirects=False)
        response.raise_for_status()
        covered += length
    if covered != len(data):
        raise SystemExit(f"upload operations do not cover all bytes for {path.name}")
    final = patch(
        f"/appScreenshots/{screenshot_id}",
        {"data": {"type": "appScreenshots", "id": screenshot_id, "attributes": {"uploaded": True}}},
    )
    state = final["data"]["attributes"].get("assetDeliveryState", {}).get("state")
    if state not in {"UPLOAD_COMPLETE", "COMPLETE"}:
        raise SystemExit(f"upload did not commit for {path.name} (state: {state!r})")
    return screenshot_id


# Apple version states, ordered by "in-flight-ness" (most preferred first).
# PREPARE_FOR_SUBMISSION is where new metadata belongs. After a submit lands,
# the version moves through PENDING_RELEASE / WAITING_FOR_REVIEW / IN_REVIEW
# before finally reaching READY_FOR_SALE. Once a version is in any of these
# in-flight states, that is the version subsequent operations should target
# (not the live version, which is read-only).
IN_FLIGHT_STATES = (
    "PREPARE_FOR_SUBMISSION",
    "PENDING_RELEASE",
    "WAITING_FOR_REVIEW",
    "IN_REVIEW",
)


# Backwards-compatible alias — older code paths refer to EDITABLE_STATES.
EDITABLE_STATES = IN_FLIGHT_STATES

DISPLAY_TYPES = (
    "APP_IPHONE_67",
    "APP_IPHONE_65",
    "APP_IPHONE_55",
    "APP_IPAD_PRO_3GEN_129",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_SCREENSHOTS = 10
MAX_SCREENSHOT_BYTES = 20 * 1024 * 1024


def load_app_meta(slug: str):
    """Pulls app-id, the editable version (or live if none), and version-id."""
    base = META / slug
    if not base.is_dir():
        raise SystemExit(f"App folder not found: {base}")
    app_id = (base / "app-id.txt").read_text().strip()
    live_version_path = base / "live-version.txt"
    live_version = live_version_path.read_text().strip() if live_version_path.exists() else ""

    # Always target the editable in-flight version. Falls back to live only
    # if no in-flight version exists.
    target_version, target_id, state, _ = _resolve_target_version(app_id, live_version)

    return app_id, target_version, target_id, state, live_version


def _resolve_target_version(app_id: str, live_version: str):
    """Returns (version_string, version_id, state, live_version)."""
    versions = get(f"/apps/{app_id}/appStoreVersions", {"limit": 50}).get(
        "data", []
    )
    for state in EDITABLE_STATES:
        for v in versions:
            if v["attributes"].get("appStoreState") == state:
                return (
                    v["attributes"]["versionString"],
                    v["id"],
                    state,
                    live_version,
                )
    # No in-flight version — fall back to live. The PATCH will likely 409;
    # surface a clear message instead of a generic error.
    for v in versions:
        if v["attributes"]["versionString"] == live_version:
            return live_version, v["id"], "READY_FOR_SALE", live_version
    raise SystemExit(f"No live version {live_version!r} found for app {app_id}")


def find_version_localization_id(version_id: str, locale: str) -> str:
    data = get(
        f"/appStoreVersions/{version_id}/appStoreVersionLocalizations",
        {"limit": 50},
    ).get("data", [])
    for loc in data:
        if loc["attributes"].get("locale") == locale:
            return loc["id"]
    raise SystemExit(f"No version localization for locale {locale!r}")


def find_app_info_localization_id(app_id: str, locale: str) -> str:
    infos = get(f"/apps/{app_id}/appInfos", {"limit": 10}).get("data", [])
    for info in infos:
        locs = get(
            f"/appInfos/{info['id']}/appInfoLocalizations", {"limit": 50}
        ).get("data", [])
        for loc in locs:
            if loc["attributes"].get("locale") == locale:
                return loc["id"]
    raise SystemExit(f"No app-info localization for locale {locale!r}")


def fetch_current_version_value(version_id, locale, attr):
    data = get(
        f"/appStoreVersions/{version_id}/appStoreVersionLocalizations",
        {"limit": 50},
    ).get("data", [])
    for loc in data:
        if loc["attributes"].get("locale") == locale:
            return loc["attributes"].get(attr) or ""
    return ""


def fetch_current_app_info_value(app_id, locale, attr):
    infos = get(f"/apps/{app_id}/appInfos", {"limit": 10}).get("data", [])
    for info in infos:
        locs = get(
            f"/appInfos/{info['id']}/appInfoLocalizations", {"limit": 50}
        ).get("data", [])
        for loc in locs:
            if loc["attributes"].get("locale") == locale:
                return loc["attributes"].get(attr) or ""
    return ""


def validate_field(field: str, value: str):
    if field == "keywords":
        if len(value) > 100:
            raise SystemExit(
                f"keywords field is {len(value)} chars, max is 100"
            )
        # No spaces after commas, per Apple convention
        if ", " in value:
            raise SystemExit(
                "keywords field contains ', ' (comma+space); Apple indexes "
                "the spaces as part of the keyword and wastes slots"
            )


def attach_build_to_version(version_id: str, build_id: str):
    """PATCH /appStoreVersions/{id} with a build relationship in the body."""
    path = f"/appStoreVersions/{version_id}"
    body = {
        "data": {
            "type": "appStoreVersions",
            "id": version_id,
            "relationships": {
                "build": {"data": {"type": "builds", "id": build_id}}
            },
        }
    }
    r = requests.patch(
        BASE + path,
        json=body,
        headers={**auth_headers(), "Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code == 204:
        return  # success, no content
    if not r.ok:
        raise SystemExit(
            f"HTTP {r.status_code} on PATCH {path}: {r.text[:500]}"
        )
    return r.json()


def fetch_attached_build_id(version_id: str):
    """Returns the build id attached to a version, or None."""
    r = get(f"/appStoreVersions/{version_id}/build")
    data = r.get("data")
    return data["id"] if data else None


def fetch_build_meta(build_id: str):
    """Returns (version_string, uploaded_date, processing_state) for a build."""
    r = get(f"/builds/{build_id}")
    a = r["data"]["attributes"]
    return (
        a.get("version"),
        (a.get("uploadedDate") or "")[:10],
        a.get("processingState"),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--app", required=True, help="app slug, e.g. my-cool-app")
    p.add_argument(
        "--attach-build",
        metavar="BUILD_ID",
        help="attach a build to the editable in-flight version (mutually "
             "exclusive with --field/--file/--locale/--submit-for-review)",
    )
    p.add_argument(
        "--submit-for-review",
        action="store_true",
        help="submit the editable in-flight version for App Review "
             "(mutually exclusive with --field/--file/--locale/--attach-build)",
    )
    p.add_argument("--upload-screenshots", type=Path, metavar="DIR")
    p.add_argument("--display-type", choices=DISPLAY_TYPES, default="APP_IPHONE_67")
    p.add_argument(
        "--append-screenshots",
        action="store_true",
        help="explicitly append to an existing screenshot set; otherwise the upload refuses it",
    )
    p.add_argument("--locale", help="locale, e.g. en-US (metadata PATCH mode)")
    p.add_argument(
        "--field",
        choices=sorted(APP_INFO_FIELDS | VERSION_FIELDS),
        help="field to PATCH (metadata PATCH mode)",
    )
    p.add_argument(
        "--file",
        type=Path,
        help="path to file holding the proposed value (metadata PATCH mode)",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="actually mutate the API; without this, dry-run only",
    )
    args = p.parse_args()

    if args.append_screenshots and not args.upload_screenshots:
        p.error("--append-screenshots requires --upload-screenshots")

    # Mode dispatch — attach-build, submit-for-review, screenshot upload, and metadata PATCH
    # are mutually exclusive.
    if args.attach_build:
        if args.field or args.file or args.locale or args.submit_for_review or args.upload_screenshots:
            p.error(
                "--attach-build is mutually exclusive with "
                "--field/--file/--locale/--submit-for-review/--upload-screenshots"
            )
        cmd_attach_build(args)
        return
    if args.submit_for_review:
        if args.field or args.file or args.locale or args.attach_build or args.upload_screenshots:
            p.error(
                "--submit-for-review is mutually exclusive with "
                "--field/--file/--locale/--attach-build/--upload-screenshots"
            )
        cmd_submit_for_review(args)
        return
    if args.upload_screenshots:
        if args.field or args.file or args.attach_build:
            p.error("--upload-screenshots is mutually exclusive with --field/--file/--attach-build/--submit-for-review")
        cmd_upload_screenshots(args)
        return

    # Default: metadata PATCH
    if not (args.locale and args.field and args.file):
        p.error("metadata PATCH mode requires --locale, --field, and --file")
    cmd_patch_field(args)


def cmd_attach_build(args):
    app_id, target_version, version_id, state, live_version = load_app_meta(args.app)
    build_id = args.attach_build

    print(f"App:           {args.app}  (id {app_id})")
    print(f"Live version:  {live_version}")
    print(f"Target:        {target_version}  (state={state}, id {version_id})")
    if target_version != live_version:
        print(
            f"               ^ not the live version; the build ships live when "
            f"{target_version} releases"
        )
    if state == "READY_FOR_SALE":
        print(
            "\nWARNING: targeting a READY_FOR_SALE version. Build attachment is "
            "usually only meaningful for editable in-flight versions."
        )

    print(f"Build id:      {build_id}")
    bver, uploaded, bstate = fetch_build_meta(build_id)
    print(f"  version:     {bver}")
    print(f"  uploaded:    {uploaded}")
    print(f"  state:       {bstate}")
    if bstate != "VALID":
        print(
            f"\nWARNING: build state is {bstate!r}, not 'VALID'. "
            f"Apple will reject the attachment."
        )

    current_build = fetch_attached_build_id(version_id)
    if current_build:
        current_ver = None
        try:
            current_ver, _, _ = fetch_build_meta(current_build)
        except SystemExit:
            pass
        print(
            f"\nCurrently attached: build {current_build}"
            + (f" (v{current_ver})" if current_ver else "")
        )
        if current_build == build_id:
            print("No-op: this build is already attached.")
            sys.exit(0)
    else:
        print("\nCurrently attached: (none)")

    body = {
        "data": {
            "type": "appStoreVersions",
            "id": version_id,
            "relationships": {
                "build": {"data": {"type": "builds", "id": build_id}}
            },
        }
    }
    print(f"\nEndpoint:        PATCH /appStoreVersions/{version_id}")
    print(f"Request body:    {body}")

    if not args.apply:
        print("\n--dry-run: pass --apply to PATCH the live API.")
        sys.exit(0)

    print("\nPATCHing…")
    attach_build_to_version(version_id, build_id)
    print("Attached.")

    # Persist a record of the attached build id alongside the version dir.
    attachment_file = META / args.app / target_version / "attached-build-id.txt"
    attachment_file.parent.mkdir(parents=True, exist_ok=True)
    attachment_file.write_text(build_id + "\n")
    print(f"Recorded on-disk: {attachment_file}")


def cmd_submit_for_review(args):
    """Modern 3-step /v1/reviewSubmissions flow: create shell, attach the
    version as an item, then PATCH submitted:true. Idempotent against an
    existing open submission: if a READY_FOR_REVIEW submission that already
    has this version attached exists, it is reused; if one exists without
    the version, the version is attached; only if none exists is a new
    shell created."""
    app_id, target_version, version_id, state, live_version = load_app_meta(args.app)

    print(f"App:           {args.app}  (id {app_id})")
    print(f"Live version:  {live_version}")
    print(f"Target:        {target_version}  (version state={state}, id {version_id})")
    if target_version != live_version:
        print(
            f"               ^ not the live version; submission moves "
            f"{target_version} into the WAITING_FOR_REVIEW / IN_REVIEW "
            f"queue and eventually to READY_FOR_SALE."
        )

    # Version-state guard — never submit something already live.
    if state == "READY_FOR_SALE":
        print(
            "\nERROR: this version is already live (READY_FOR_SALE); nothing to submit."
        )
        sys.exit(1)
    if state in ("WAITING_FOR_REVIEW", "IN_REVIEW"):
        print(
            f"\nNo-op: this version is already in state {state!r} — "
            f"it has been submitted for App Review. To find the open "
            f"submission(s), query "
            f"GET /v1/reviewSubmissions?filter[app]={app_id}."
        )
        sys.exit(0)

    # Build-attachment guard — Apple rejects submissions without a VALID build.
    build_id = fetch_attached_build_id(version_id)
    if not build_id:
        print(
            "\nERROR: no build attached. Apple rejects submissions without a "
            "VALID build; first run --attach-build BUILD_ID."
        )
        sys.exit(1)
    bver, uploaded, bstate = fetch_build_meta(build_id)
    print(
        f"\nAttached build: {build_id} (v{bver}, uploaded {uploaded}, state={bstate})"
    )
    if bstate != "VALID":
        print(
            f"\nERROR: attached build state is {bstate!r}, not 'VALID'. "
            f"Apple will reject the submission."
        )
        sys.exit(1)

    # Idempotency: look for an open submission this version is already on, or any open one.
    existing_target = None  # open submission already containing this version as an item
    existing_open = None    # any open submission, in case we need to attach to one
    open_states = ("READY_FOR_REVIEW", "WAITING_FOR_REVIEW", "IN_REVIEW")
    for sub in list_open_review_submissions(app_id):
        s_state = sub["attributes"].get("state")
        if s_state not in open_states:
            continue
        existing_open = sub["id"]
        items = get(f"/reviewSubmissions/{sub['id']}/items").get("data", [])
        if any(
            it.get("relationships", {}).get("appStoreVersion", {}).get("data", {}).get("id")
            == version_id
            for it in items
        ):
            existing_target = sub["id"]
            break

    print(f"\nOpen reviewSubmissions for this app: "
          f"{[s for s in (existing_target, existing_open) if s] or '(none)'}")
    print(f"Submission with this version attached: {existing_target or '(none)'}")

    target_sub_id = existing_target or existing_open

    # Decide what work needs doing.
    needs_create = existing_open is None
    # A new shell also needs its version attached before it can be committed.
    needs_attach = existing_target is None

    if not (needs_create or needs_attach):
        # Reusable submission that already has this version attached.
        cur = get_review_submission_state(target_sub_id)
        print(f"\nReusing submission {target_sub_id} (state={cur}). No create / no attach needed.")

    if needs_create:
        body1 = {
            "data": {
                "type": "reviewSubmissions",
                "attributes": {"platform": "IOS"},
                "relationships": {"app": {"data": {"type": "apps", "id": app_id}}},
            }
        }
        print(f"\nStep 1: POST /reviewSubmissions (create shell)")
        print(f"  body: {body1}")
        if not args.apply:
            print("\n--dry-run: pass --apply to POST.")
            sys.exit(0)
        r = create_review_submission(app_id)
        target_sub_id = r["data"]["id"]
        print(f"  → submission id: {target_sub_id}")
        print(f"  → state: {r['data']['attributes'].get('state')}")

    if needs_attach:
        body2 = {
            "data": {
                "type": "reviewSubmissionItems",
                "relationships": {
                    "reviewSubmission": {
                        "data": {"type": "reviewSubmissions", "id": target_sub_id}
                    },
                    "appStoreVersion": {
                        "data": {"type": "appStoreVersions", "id": version_id}
                    },
                },
            }
        }
        print(f"\nStep 2: POST /reviewSubmissionItems (attach {target_version} → {target_sub_id})")
        print(f"  body: {body2}")
        if not args.apply:
            print("\n--dry-run: pass --apply to POST.")
            sys.exit(0)
        r = attach_version_to_submission(target_sub_id, version_id)
        print(f"  → item id: {r['data']['id']}")
        print(f"  → item state: {r['data']['attributes'].get('state')}")

    # Inspect current submission state — short-circuit if already past READY_FOR_REVIEW.
    cur = get_review_submission_state(target_sub_id)
    if cur in ("WAITING_FOR_REVIEW", "IN_REVIEW", "UNRESOLVED_ISSUES"):
        print(
            f"\nNo-op: submission {target_sub_id} is in state {cur!r}; "
            f"already past READY_FOR_REVIEW."
        )
        sys.exit(0)
    if cur == "COMPLETED":
        print(
            f"\nNo-op: submission {target_sub_id} is already COMPLETED."
        )
        sys.exit(0)
    if cur != "READY_FOR_REVIEW":
        print(
            f"\nERROR: submission {target_sub_id} in unexpected state {cur!r}; bailing."
        )
        sys.exit(1)

    # Step 3: commit (point of no return).
    body3 = {
        "data": {
            "type": "reviewSubmissions",
            "id": target_sub_id,
            "attributes": {"submitted": True},
        }
    }
    print(f"\nStep 3: PATCH /reviewSubmissions/{target_sub_id} (commit submitted=true)")
    print(f"  body: {body3}")
    if not args.apply:
        print("\n--dry-run: pass --apply to PATCH.")
        sys.exit(0)

    print("\nCommitting…")
    r = commit_review_submission(target_sub_id)
    attrs = r["data"]["attributes"]
    print(f"  state:          {attrs.get('state')}")
    print(f"  submittedDate:  {attrs.get('submittedDate')}")


def cmd_upload_screenshots(args):
    """Dry-run or upload a bounded, validated ordered PNG set."""
    source = args.upload_screenshots
    if not source.is_dir():
        raise SystemExit(f"not a screenshot directory: {source}")
    files = sorted(path for path in source.iterdir() if path.suffix.lower() == ".png")
    if not files:
        raise SystemExit(f"no PNG files found in {source}")
    if len(files) > MAX_SCREENSHOTS:
        raise SystemExit(f"at most {MAX_SCREENSHOTS} screenshots may be uploaded at once")
    details = [(path, *validate_png(path)[1:]) for path in files]
    app_id, target_version, version_id, state, _ = load_app_meta(args.app)
    if state == "READY_FOR_SALE":
        raise SystemExit("refusing screenshots for a live version; choose an editable in-flight version")
    locale = args.locale or "en-US"
    localization_id = find_version_localization_id(version_id, locale)
    set_id, existing_count = find_screenshot_set(localization_id, args.display_type)
    print(f"App: {args.app} ({app_id})")
    print(f"Target version: {target_version} ({state}); locale: {locale}; type: {args.display_type}")
    print("Upload order:")
    for path, width, height in details:
        print(f"- {path.name}: {width}x{height}, {path.stat().st_size} bytes")
    if set_id:
        print(f"Existing screenshot set {set_id} has {existing_count} asset(s).")
        if not args.append_screenshots:
            raise SystemExit(
                "refusing to append to an existing set; inspect/delete it in App Store Connect "
                "or re-run with --append-screenshots"
            )
        if existing_count + len(files) > MAX_SCREENSHOTS:
            raise SystemExit(f"append would exceed the {MAX_SCREENSHOTS}-screenshot limit")
    if not args.apply:
        print("--dry-run: pass --apply to create/upload the screenshot set.")
        return
    if set_id is None:
        set_id = create_screenshot_set(localization_id, args.display_type)
        print(f"Created screenshot set {set_id}.")
    for path, _, _ in details:
        print(f"Uploaded {path.name}: {upload_one_screenshot(set_id, path)}")


def cmd_patch_field(args):
    new_value = args.file.read_text().rstrip("\n")
    validate_field(args.field, new_value)

    app_id, target_version, version_id, state, live_version = load_app_meta(args.app)
    print(f"App:           {args.app}  (id {app_id})")
    print(f"Live version:  {live_version}")
    print(f"Target:        {target_version}  (state={state}, id {version_id})")
    if target_version != live_version:
        print(
            f"               ^ not the live version; the change goes live when "
            f"{target_version} ships"
        )
    print(f"Locale:        {args.locale}")
    print(f"Field:         {args.field}")
    print(f"Proposed:      {new_value!r}  ({len(new_value)} chars)")

    attr = FIELD_TO_ATTR[args.field]

    if args.field in APP_INFO_FIELDS:
        loc_id = find_app_info_localization_id(app_id, args.locale)
        current = fetch_current_app_info_value(app_id, args.locale, attr)
        endpoint = f"/appInfoLocalizations/{loc_id}"
    else:
        loc_id = find_version_localization_id(version_id, args.locale)
        current = fetch_current_version_value(version_id, args.locale, attr)
        endpoint = f"/appStoreVersionLocalizations/{loc_id}"

    print(f"\nLocalization id: {loc_id}")
    print(f"Endpoint:        PATCH {endpoint}")
    print(f"Current:         {current!r}  ({len(current)} chars)")

    if current == new_value:
        print("\nNo-op: proposed value equals current value, nothing to PATCH.")
        sys.exit(0)

    body = {"data": {"type": endpoint.split("/")[1], "id": loc_id, "attributes": {attr: new_value}}}
    print(f"\nRequest body: {body}")

    if not args.apply:
        print("\n--dry-run: pass --apply to PATCH the live API.")
        sys.exit(0)

    print("\nPATCHing…")
    resp = patch(endpoint, body)
    print(f"Response: {resp.get('data', {}).get('id', '(no id)')}")

    # Update on-disk keywords.txt (canonical) to match the new state.
    # Only writes to the in-flight version's folder (which is what we just
    # PATCHed); the live version's keywords.txt is unchanged on disk
    # because Apple's live version is read-only.
    if args.field == "keywords":
        canonical = (
            META / args.app / target_version / args.locale / "keywords.txt"
        )
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(new_value + "\n")
        print(f"Updated on-disk canonical: {canonical}")


if __name__ == "__main__":
    main()
