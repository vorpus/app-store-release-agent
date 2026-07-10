# Architecture

A short read for contributors who want to understand *why* the agent is
shaped the way it is before changing it. Most decisions are reversible
in a single PR; a few aren't, and they're flagged below.

---

## Top-level shape

Three CLI scripts, one shared on-disk mirror, one shared API client:

```
                    ┌─────────────────────────────┐
                    │  App Store Connect REST API │
                    └──────────────┬──────────────┘
                                   │ JWT-signed requests
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
       ┌──────▼─────┐       ┌───────▼──────┐    ┌───────▼──────┐
       │ smoke_test │       │fetch_metadata│    │patch_metadata│
       └────────────┘       └───────┬──────┘    └───────┬──────┘
                                   │                    │
                                   └────────┬───────────┘
                                            ▼
                                  ┌──────────────────┐
                                  │ metadata/ mirror │
                                  │ + changelog.md   │
                                  └──────────────────┘
```

- `smoke_test.py` is read-only. It proves connectivity and lists apps
  + live versions. Run it first after credential setup.
- `fetch_metadata.py` is read-only. It populates the `metadata/`
  mirror from ASC.
- `patch_metadata.py` is the only mutating script. It has three modes
  (metadata PATCH, build attachment, submit-for-review), each dry-run
  by default with `--apply` to commit.

The mirror is canonical for *new metadata about to be uploaded*; the
API is canonical for *live state*. The mirror is updated to match the
API after every successful mutation.

## Why three scripts, not one

Each script has a single responsibility, a single set of dependencies,
and a single set of failure modes:

- `smoke_test.py` is the smallest possible read-only probe. Five
  functions, no I/O beyond the JWT-signed GET.
- `fetch_metadata.py` is the only script that writes the on-disk
  mirror in bulk. It uses a higher request rate and tolerates partial
  failures (an app with no live versions is skipped, not crashed on).
- `patch_metadata.py` is the only script that mutates. Its CLI is
  shaped so that *every* call has a dry-run form. The default is
  dry-run; `--apply` is required to send anything.

Splitting them keeps each script's blast radius small and makes the
surface area easier to audit (this matters because of [SECURITY.md](../SECURITY.md)).

## Why a local mirror at all

Several reasons, in order of importance:

1. **Diffs.** Without a mirror you can do a PATCH and see the live
   result, but you can't review the change before sending it. The
   mirror is what `git diff` operates on.
2. **Apple's metadata lock.** When a version becomes `READY_FOR_SALE`,
   the metadata fields on that version become read-only from a
   developer-experience standpoint (they still appear in the API, but
   you can't PATCH them). New edits go to the *in-flight* version
   (`PREPARE_FOR_SUBMISSION`, etc.). The mirror remembers which
   version an edit was for, so a subsequent run knows.
3. **Offline drafts.** Marketing copy can be drafted and reviewed
   without holding an ASC connection open.
4. **Cross-script continuity.** `fetch` and `patch` use the same
   directory layout, so the output of one is the input of the other.

## Version state machine

This is the piece that surprises new users most. App Store Connect
models a version's lifecycle as a state machine, and which state a
version is in determines whether its metadata is editable.

| State | Editable fields? | Submittable? | Notes |
|---|---|---|---|
| `PREPARE_FOR_SUBMISSION` | yes | yes | New metadata belongs here. |
| `PENDING_RELEASE` | yes | already submitted | Apple has the version, awaiting release scheduling. |
| `WAITING_FOR_REVIEW` | mixed | already submitted | Output of `PATCH submitted:true`. |
| `IN_REVIEW` | limited | already submitted | A human reviewer is active. |
| `REJECTED` (technically `UNRESOLVED_ISSUES` on the submission) | yes | resubmit after fixing | |
| `READY_FOR_SALE` | read-only | n/a | Live. |

The agent resolves "which version do I edit?" by walking these states
in order — see the `_resolve_target_version` helper in
`src/patch_metadata.py`. The renamed `IN_FLIGHT_STATES` tuple in
`patch_metadata.py` lists exactly which states are considered
in-flight.

A version-only read of `metadata/<app>/<version>/version-id.txt` is
not enough to know whether the version is editable; the script
fetches the live state on every mutating call.

## Why `--submit-for-review` looks the way it does

See [review-submissions.md](review-submissions.md) for the full
explanation. Short version: App Store Connect has a legacy
`/v1/appStoreVersionSubmissions` endpoint that returns 403 for keys
provisioned after the migration to the modern reviewSubmissions model,
and a modern 3-step flow against `/v1/reviewSubmissions` +
`/v1/reviewSubmissionItems`. The legacy helper is preserved in
`patch_metadata.py` as a `NotImplementedError` so a future edit can't
accidentally rewire to it. Don't remove that guard.

## Auth model

A single App Store Connect API key signs every request. The key's
permission set determines what the agent can do:

- **App Manager or Admin:** full read/write on apps, builds, versions,
  submissions — everything the agent needs.
- **Developer / Marketing:** read + PATCH on metadata fields only;
  no submit-for-review; no build attachment.

The agent doesn't have a way to verify its own permission scope at
runtime — it just gets 403s. If you see "Allowed operation is:
DELETE" on a benign verb like GET, suspect either (a) a misconfigured
key, or (b) you're hitting the legacy endpoint and need to use the
modern one.

## What "audit trail" means here

See [audit-trail.md](audit-trail.md) for the structural details. The
short version: every change goes through the agent, and every change
gets appended to `metadata/<app>/changelog.md` as a structured entry.
The audit trail is local, never sent anywhere, and is grep-friendly.

The audit trail is *not* authoritative for live state — that's the
API. It is authoritative for *what the agent did and why*.
