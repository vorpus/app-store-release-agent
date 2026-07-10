# Security

This document covers two things that are easy to confuse:

1. **What this repo guarantees** about credential hygiene.
2. **What to do** if you find a credential leak — yours, this project's,
   or a contributor's.

---

## What this repo guarantees

- **No App Store Connect credentials are committed.** The `.gitignore`
  excludes `*.p8`, `AuthKey_*.p8`, `identifiers.txt`, `.env*`, `*.pem`,
  `*.key`, `*.p12`, and `secrets/`. The wrapper scripts read
  credentials from environment variables (`ASC_ISSUER_ID`,
  `ASC_KEY_ID`, `ASC_PRIVATE_KEY_PATH`) — there are no real ids or
  paths hardcoded anywhere in `src/`.
- **No real app metadata is committed.** The only metadata in this
  repo lives under `examples/synthetic-app/`, where every app name,
  bundle id, app id, and version is fictional. Production metadata
  belongs in your own private mirror, not here.
- **No real audit-trail content is committed.** The
  `templates/changelog.example.md` file shows the entry *structure*
  with placeholders. Real `changelog.md` files from a live portfolio
  would include specific version ids, build uuids, and submission ids
  that are operationally sensitive — those belong in private forks.

If a future PR appears to violate any of these guarantees, do not
file a public issue. See the next section.

---

## How the scripts use credentials

The wrapper scripts use the App Store Connect JWT flow:

1. Read `ASC_PRIVATE_KEY_PATH` (the path to your `.p8` file).
2. Read `ASC_ISSUER_ID` and `ASC_KEY_ID` from the environment.
3. Sign an ES256 JWT with those claims and a 20-minute expiry.
4. Send `Authorization: Bearer <jwt>` on every API call.

The `.p8` is **never** read by anything except the JWT signer. It is
**never** uploaded, echoed back, or written to disk by these scripts.

Practical recommendations for users:

- Store your `.p8` outside the repo (the recommended default above is
  `~/.asc/AuthKey_<KEY_ID>.p8`, with 600 permissions).
- The `.p8` file gives full App Store Connect API access to your team.
  Treat it like a private SSH key.
- Rotate keys annually; the API allows multiple active keys so you can
  cut over without downtime.
- For local convenience only, you can put env vars in a gitignored
  `.env` file. The scripts **do not** read it for you — you wire that
  with `direnv`, `dotenv`, or a shell wrapper.

---

## If you find a credential leak

### In this repo, a PR, an issue, or anywhere in this org

**Do not file a public issue. Do not open a public PR.**

Email the maintainer at the address listed on their GitHub profile
(`dragosroua`) with a subject line that includes the word `SECURITY`
and a brief description. Expect an acknowledgement within 72 hours.

If you don't have email access (or want a backup channel), use GitHub's
private vulnerability reporting:
**https://github.com/dragosroua/app-store-release-agent/security/advisories/new**

### In your own clone or work environment

If your own `.p8` or `identifiers.txt` ends up in a commit:

1. **Revoke the key immediately** in App Store Connect → Users and
   Access → Keys. Delete the leaked key. Treat it as compromised.
2. **Generate a new key** with the same role (App Manager or Admin) and
   update `ASC_KEY_ID` / `ASC_PRIVATE_KEY_PATH` to point at the new
   `.p8`.
3. **Rotate affected credentials** — any project that depended on the
   leaked key has had it revoked. Coordinate the cutover with anyone
   else who uses your ASC account.
4. **Audit recent API activity** in App Store Connect → Activity for
   the leaked key id. Look for unknown submissions or metadata edits.
5. **Clean the git history** with `git-filter-repo` or BFG before the
   repo is shared again. Removing the file in a later commit is not
   enough — the blob is still in earlier history until rewritten.

### Reporting a vulnerability in the scripts themselves

If you find a code-level issue (e.g. the JWT signer accepts a key from
an env var that an attacker can control via a side channel), please
follow the same private-report path above. Don't include proof-of-
concept details in a public issue.
