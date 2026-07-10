# Changelog — Sample Tracker (synthetic example)

Illustrative audit trail. Every entry in this file is fabricated for the
purpose of showing what an audit-trail entry looks like in the agent. No
real ASC ids, no real operations, no real app.

---

## 2026-01-15 — Shipped: sample keyword cleanup (1.0 en-US)

**Author:** agent
**Status:** shipped (visible as part of the synthetic 1.0 release; never
reached any actual App Store)

**Targeted version:** 1.0 (`READ-ONLY-FOR-EXAMPLE`, zero UUID)

### Why

The sample keyword list contained two words that were also in the title
(`Sample`, `Tracker`). Apple's indexer counts title words as keyword
hits for free, so re-listing them in the keyword field wastes slots.

### What changed

| Field | Before | After |
|---|---|---|
| keywords | `sample,tracker,habit,log,time,demo,placeholder,example` | `tracker,habit,log,time,sample,demo,placeholder,example` |

Same length, but `sample` and `tracker` are still in there as
demonstrations of how the agent handles ordering and overlap; they
remain flagged here for the same reason a real entry would flag them.

### How

`PATCH /v1/appStoreVersionLocalizations/<loc-id>` with the new value,
sent by `patch_metadata.py --field keywords --apply`. Local
`metadata/sample-tracker/1.0/en-US/keywords.txt` updated to match.

### Result

Local mirror and ASC state agree on the new value. No user-visible
change (1.0 was already live in this fabricated scenario).

### Notes

This entry exists so a contributor opening `metadata/<app>/changelog.md`
in their own adoption can see the shape. Don't copy it verbatim — your
real entries should reference real ids, real apple-side timestamps, and
real operator decisions.
