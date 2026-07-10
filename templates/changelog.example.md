# Changelog — <App Name>

Append-only audit trail for every state change this app goes through
under the agent: keyword swaps, build attachments, submission actions,
review verdicts, manual fixes, anything that touches the on-disk mirror
or the App Store Connect API.

One entry per logical event. Use the structure below as a template; copy
it, fill it in, prepend to this file.

---

## DATE — Short, imperative title

**Author:** operator | agent
**Status:** shipped | shipped (visible when X ships) | blocked | replaced
**Target version:** <version-string> (`<state>`, `<version-uuid>` if known)
**Build:** `<build-uuid>` (`CFBundleVersion <n>`, uploaded DATE,
`processingState: VALID`) — omit if not relevant to the entry

### Why

One short paragraph: what problem this entry is solving and what was
mistaken about the prior state.

### What changed

Tables for things like "5 dropped, 5 added" or "before/after field
values" — anything where the change has a clean diff shape.

### How

The endpoint or operation used. Quote the exact PATCH body or POST
body where a future run needs to reproduce it. Reference the script
mode used (`--field keywords`, `--attach-build`, `--submit-for-review`).

### Result

The new state. Was the API call successful? Did the on-disk mirror
update? Is the change user-visible now, or only after a future
transition?

### What's next

If this entry is not a complete loop, point at the next operator or
agent action so the trail stays grep-friendly.

### Notes

Anything that didn't fit the above. Including things that *didn't*
work — the audit-trail principle in `prompts/prompt.md` says "no silent
failures", and a failed attempt with a clear writeup is more useful than
no record at all.
