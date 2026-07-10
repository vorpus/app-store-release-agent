# Audit trail pattern

Every change the agent makes to App Store Connect — and every change
the operator makes that bypasses the agent — gets appended to a
per-app `changelog.md`. This document captures the why and the how.

---

## Why a local audit trail at all

ASC's UI shows a basic activity log, but it doesn't survive into your
local codebase, it isn't easy to grep across apps, and it doesn't
explain *why* a change was made. The audit-trail pattern complements
the API:

| Layer | What it answers | Authoritative for |
|---|---|---|
| App Store Connect UI | "What did Apple see I do?" | A low-resolution timeline of API activity. |
| `git log` of `metadata/` | "What changed on disk in this repo?" | The disk mirror's history. |
| `metadata/<app>/changelog.md` | "What did the agent or operator do, and why?" | Decisions, intentions, dead-ends. |
| App Store Connect itself | "What is the live state right now?" | Live canonical truth. |

The changelog is the only one of these that explains *intent*. That's
the gap it fills.

## When to write an entry

Write a changelog entry every time any of the following happens for an
app:

- A metadata field is PATCHed (keywords, what's-new, promotional text,
  title, subtitle, description, support/marketing url, privacy URL).
- A build is attached to a version.
- A version is submitted for review (whether via the agent or via the
  web UI after a manual Age Rating fix).
- The agent's API call to a mutating endpoint fails after retries
  (record the failure as a `Blocked` entry — that is mandatory under
  the operating principle *"no silent failures"*).
- The Apple App Review response arrives (acceptance, rejection with
  reason, request for more information).
- The version transitions from `WAITING_FOR_REVIEW` to
  `IN_REVIEW` to `COMPLETED` (one entry can cover the whole arc if
  they happen close together; otherwise split).
- A workaround is applied (manual Age Rating change, manual screenshot
  re-upload, etc., that bypasses the agent).

Do **not** write entries for:

- Reads (`fetch`, smoke test, version lookups).
- A dry-run that wasn't followed by an apply.
- A duplicate-apply where the no-op guard correctly short-circuited.

## Entry structure

Use [templates/changelog.example.md](../templates/changelog.example.md)
verbatim. The short version:

```markdown
## DATE — Short, imperative title

**Author:** operator | agent
**Status:** shipped | shipped (visible when X ships) | blocked | replaced
**Target version:** <version-string> (`<state>`)
**Build:** `<build-uuid>` — omit if not relevant

### Why
(one short paragraph: the problem this is solving)

### What changed
(tables for "X dropped, X added", or before/after values)

### How
(the endpoint or operation used; quote the exact PATCH/POST body
where a future run needs to reproduce it; reference the script mode
like `--field keywords`, `--attach-build`, `--submit-for-review`)

### Result
(the new state; was the API call successful; is the change
user-visible now)

### What's next
(pointer to the next operator or agent action, so the trail stays
grep-friendly)

### Notes
(anything that didn't fit above, including things that *didn't* work)
```

## Why each field exists

- **Date:** lets you grep by recency and order entries. Use ISO
  `YYYY-MM-DD` for stable alphabetical sort.
- **Title (after the date):** imperative, short. Future you scanning
  the log file is looking for keywords more often than for full
  sentences.
- **Author:** humans and the agent both write entries. Knowing which
  one did it changes what you trust in the entry.
- **Status:** a coarse mode flag. We use:
  - `shipped` — applied and live.
  - `shipped (visible when X ships)` — applied but not yet visible to
    end users (e.g. metadata on a `WAITING_FOR_REVIEW` version).
  - `blocked` — an operation that should have succeeded but didn't
    and needs operator intervention. Pair with a `### Why` that
    names the cause.
  - `replaced` — superseded by a later entry (e.g., a `Blocked` entry
    whose underlying issue was fixed). Keep the old entry; mark it
    `replaced` rather than deleting it.
- **Target version:** the version this entry operates on. Quote the
  state if it's interesting (a `PREPARE_FOR_SUBMISSION` operation
  implies in-flight work; a `READY_FOR_SALE` operation implies
  reading, not editing).
- **Build:** the build uuid + CFBundleVersion + processing state at
  the time of the entry. Optional but extremely valuable when a
  rejection references a specific build.

## Things to *not* put in the changelog

- The contents of your `.p8` key. Never. Not even a fingerprint.
- Bundle ids for other apps in your portfolio, unless the entry is
  about cross-promo and they're operationally involved.
- Personal data of any user. The changelog should be safe to read
  with a coworker standing behind you.
- Long stack traces. Link to a log file instead.

## Replaced vs. deleted

Don't delete old entries. `changelog.md` is append-only, by design.
When you fix a `Blocked` entry, write a new entry that fixes the
underlying issue; mark the old entry's status as `replaced` and
reference the new entry's date and title.

```
## DATE — Blocked: original problem (HTTP 403, was: insufficient perms)
...
**Status:** replaced — see entry on 2026-MM-DD below

## DATE — Shipped: original problem (real resolution; correct key has
               the right role)
...
```

This preserves the audit trail of *what was tried*. Future you
debugging a similar issue benefits from knowing what didn't work last
time.

## Bulk import from Apple App Review responses

If you receive an App Review rejection by email and fix it manually in
the App Store Connect UI, write a `Blocked` entry that quotes the
relevant excerpt of the rejection message (a paragraph, not the whole
email — trim to the actionable bits), and a follow-up `Shipped` entry
that records how you fixed it. The agent doesn't run on App Review
rejections, but the audit trail still needs to.
