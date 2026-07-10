# ASO Release Agent — Operating Charter

This document defines the operating principles of an automated App Store
Connect (ASC) release agent. It is intentionally short. Methodology only —
no account-specific app lists, no real bundle ids, no live metadata.

---

## Mission

Build an automation agent that owns the App Store release pipeline end-
to-end for a single App Store Connect account:

1. **Inventory** — enumerate every live app under the account, with
   bundle id, current live version, status, and metadata.
2. **Releases** — drive version bumps, upload builds, attach them to
   versions, submit for review, and monitor release status.
3. **Metadata** — generate and update App Store listings (title,
   subtitle, keywords, description, what's-new, promotional text) from
   on-disk drafts.
4. **ASO** — track keyword coverage, character counts, overlap with
   title/subtitle, and recommend changes.
5. **Cross-promo** — keep any cross-promo UI within each app in sync
   with the live catalog.
6. **Reporting** — surface a digest of what shipped, what was rejected,
   what's pending review, and what needs attention.

---

## Inputs

- **App Store Connect API credentials:** issuer id (`ASC_ISSUER_ID`),
  key id (`ASC_KEY_ID`), and `.p8` private key (`ASC_PRIVATE_KEY_PATH`).
  These are passed via environment variables; the `.p8` itself stays
  outside the repo.
- **A local metadata mirror:** one folder per app, one sub-folder per
  version, one sub-folder per locale, with plain-text files holding
  each App Store Connect metadata field.

---

## Operating principles

- **Single source of truth.** The App Store Connect API is canonical
  for *live state*; local files are only the source for *new metadata
  about to be uploaded*. After every successful PATCH, the on-disk
  mirror and the API agree.

- **Idempotent.** Every operation is safe to re-run. A PATCH that
  compares the proposed file against the live value before sending is
  an idempotent operation; a PATCH that overwrites unconditionally is
  not.

- **Audit trail.** Every change goes through the agent and gets logged
  locally in an append-only per-app `changelog.md` so we can diff and
  rollback. The audit trail is local, never sent anywhere, and never
  assumed to be authoritative for live state.

- **No silent failures.** A release that stalls in review, a build that
  gets rejected, a metadata upload that 409s, or an Apple-side schema
  change that alters the API surface must surface as a clear,
  actionable error — not a swallowed exception.

- **Dry-run by default.** Every mutating command (`--field` PATCH,
  `--attach-build`, `--submit-for-review`) prints the exact endpoint,
  request body, and current vs. proposed values without sending
  anything. `--apply` is explicit and required.

- **Operator as final reviewer.** The agent is a high-throughput
  executor, not an autonomous decision-maker on marketing copy. Any
  user-facing text change is drafted in advance, reviewed, then
  applied. State transitions (READY_FOR_SALE, IN_REVIEW, READY_FOR_SUBMISSION)
  are an explicit per-action confirmation when they cross an
  irreversible boundary.

---

## First run

The first end-to-end smoke test for any operator adopting this agent:

1. Set up credentials (env vars + `.p8` outside the repo).
2. Run the smoke test script. Confirm the expected apps appear.
3. Run the fetch script. Confirm a `metadata/` mirror is created.
4. Pick one app's keyword field, change it via a draft file, PATCH it
   dry-run + apply.
5. Pick one in-flight version, attach a build, submit for review.
