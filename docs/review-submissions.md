# App Review submission — the modern 3-step flow

The most common mistake when scripting App Store Connect submissions is
to use the legacy `POST /v1/appStoreVersionSubmissions` endpoint. As of
2024-2025, App Store Connect keys provisioned with the modern scope set
get **HTTP 403** on that endpoint — not for permission reasons, but
because Apple has migrated submission tracking to a different resource
model.

This document captures the path the agent actually uses, which works.

---

## Why the legacy endpoint 403s

```
$ POST https://api.appstoreconnect.apple.com/v1/appStoreVersionSubmissions
HTTP/1.1 403 Forbidden

{
  "errors": [{
    "status": "403",
    "code": "FORBIDDEN_ERROR",
    "title": "The given operation is not allowed",
    "detail": "The resource 'appStoreVersionSubmissions' does not allow 'CREATE'.
              Allowed operation is: DELETE"
  }]
}
```

The "Allowed operation is: DELETE" wording is misleading. What it's
telling you is that the *resource type* `appStoreVersionSubmissions`
still exists for backwards compatibility, but POSTs against it are no
longer accepted for keys that don't pre-date the migration. The key in
your local `identifiers.txt` may be App Manager tier all it likes —
this endpoint is closed at the resource layer.

The correct workflow is the modern reviewSubmissions model below.

---

## Step 1 of 3 — `POST /v1/reviewSubmissions`

Create a *submission shell*. The shell belongs to the app and has the
platform hardcoded (you can also create a separate shell for macOS,
tvOS, etc.):

```
POST /v1/reviewSubmissions

{
  "data": {
    "type": "reviewSubmissions",
    "attributes": { "platform": "IOS" },
    "relationships": {
      "app": { "data": { "type": "apps", "id": "<your-app-uuid>" } }
    }
  }
}
```

Response: an object with a submission `id`, an initial `state` of
`READY_FOR_REVIEW`, and `submittedDate: null`. Keep the id.

Notes:
- A submission shell contains *zero or more items*, each linking a
  version. You can put multiple items in one submission if you're
  shipping more than one version at a time.
- The endpoint requires `filter[app]` for *listings*, but not for
  creates. (You'll use `GET /v1/reviewSubmissions?filter[app]=<id>`
  later to find this submission.)

---

## Step 2 of 3 — `POST /v1/reviewSubmissionItems`

Attach the version to the submission. Each item is one version-localization
pair (technically: one app-store-version + the localizations that go
with it). For a single-locale release, you attach one item:

```
POST /v1/reviewSubmissionItems

{
  "data": {
    "type": "reviewSubmissionItems",
    "relationships": {
      "reviewSubmission": {
        "data": { "type": "reviewSubmissions", "id": "<submission-id>" }
      },
      "appStoreVersion": {
        "data": { "type": "appStoreVersions", "id": "<version-id>" }
      }
    }
  }
}
```

Notes:
- The relationship is `appStoreVersion` (singular), not
  `appStoreVersions`. Apple is consistent on this.
- The version must have a `VALID` build attached, or Apple rejects the
  PATCH with 422. The agent's `cmd_submit_for_review` checks
  `processingState: VALID` explicitly before this step.
- If you skip Step 2 and try Step 3, Apple returns **HTTP 409
  STATE_ERROR.ENTITY_STATE_INVALID** with the message "does not have
  any items." That's the safe-ish guardrail.

---

## Step 3 of 3 — `PATCH /v1/reviewSubmissions/{id}`

Commit the submission. This is the point of no return — the submission
leaves `READY_FOR_REVIEW`, sets `submittedDate`, and the version moves
to `WAITING_FOR_REVIEW`:

```
PATCH /v1/reviewSubmissions/<submission-id>

{
  "data": {
    "type": "reviewSubmissions",
    "id": "<submission-id>",
    "attributes": { "submitted": true }
  }
}
```

Notes:
- After this returns `200 OK`, you cannot undo it through the same
  submission. Apple offers a separate `cancel` action against
  *individual items* if you need to recall something specific (e.g.,
  via `POST /v1/reviewSubmissionItems/{item-id}/actions` with a
  cancel body), but the agent does not auto-cancel — that's an
  operator decision.
- The corresponding `appStoreVersion` state on the version resource
  itself changes from `PREPARE_FOR_SUBMISSION` to `WAITING_FOR_REVIEW`
  shortly after this call. See
  [architecture.md](architecture.md#version-state-machine) for the
  full state machine.

---

## Expected state progression after a clean submit

```
WAITING_FOR_REVIEW  →  IN_REVIEW  →  COMPLETED     (approved; version goes READY_FOR_SALE)
                                →  UNRESOLVED_ISSUES  (rejected; iterate and re-submit)
```

The agent currently does not poll for these transitions. A future
"watch and report" mode is reasonable, but the simplest workflow is to
re-fetch the version after some delay:

```bash
GET /v1/appStoreVersions/<version-id>
```

`appStoreState == "READY_FOR_SALE"` is the canonical "live now" signal.

---

## Implementation in `patch_metadata.py`

`cmd_submit_for_review` performs all three steps under one CLI
invocation:

```bash
python3 src/patch_metadata.py --app <slug> --submit-for-review --apply
```

Dry-run is the default and prints the exact body of each step. The
script is idempotent: if a `READY_FOR_REVIEW` submission already exists
for the app and already has the target version attached, it is reused,
and only Step 3 is needed. If the version is already in
`WAITING_FOR_REVIEW` / `IN_REVIEW` / `COMPLETED`, the script
short-circuits with a clean message pointing at how to look up the
existing submission.
