# app-store-release-agent

A small Python toolkit that automates part of the App Store Connect (ASC)
workflow: pull live metadata, mutate it (with a dry-run default), attach
builds to in-flight versions, and submit versions for App Review.

This repo is a **generalized version** of the operator scripts behind a
real release pipeline. No real App Store credentials, real app metadata,
or real audit trail from a live portfolio are in this repo. See
[SECURITY.md](SECURITY.md) for what is and isn't here.

## What this is

- A read-and-write client for the [App Store Connect REST API](https://developer.apple.com/documentation/appstoreconnectapi).
- Three CLI scripts (`fetch`, `patch`, `smoke`) that operate over a
  local `metadata/` mirror of your live catalog.
- A reusable audit-trail template and a couple of synthetic examples so
  the workflow is visible without revealing any specific app's strategy.

## What this isn't

- **Not a managed service.** You bring your own App Store Connect
  account, your own API key (`.p8`), and your own apps.
- **Not a turnkey ASO tool.** The point isn't to write copy for you;
  it's to ship the changes you (or another agent) already drafted.
- **Not a substitute for the App Store Connect UI.** Anything that
  isn't reachable via the REST API isn't in scope here.

## Quick start

```bash
# 1. Get the requirements
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure credentials (paths only; the .p8 stays outside the repo)
#    Get these from App Store Connect → Users and Access → Keys.
export ASC_ISSUER_ID="<your-issuer-uuid>"
export ASC_KEY_ID="<your-10-char-key-id>"
export ASC_PRIVATE_KEY_PATH="$HOME/.asc/AuthKey_<your-key-id>.p8"

# 3. Sanity check connectivity
python3 src/smoke_test.py

# 4. Pull your live catalog to ./metadata/
python3 src/fetch_metadata.py

# 5. Mutate, with dry-run first
python3 src/patch_metadata.py --app <slug> --locale en-US \
    --field keywords --file path/to/new-keywords.txt
python3 src/patch_metadata.py --app <slug> --locale en-US \
    --field keywords --file path/to/new-keywords.txt --apply
```

## Scripts

| Script | Purpose |
|---|---|
| `src/smoke_test.py` | Connect to ASC and list every app + its current live version. Best first run after credential setup. |
| `src/fetch_metadata.py` | Pull every live app's localized metadata (titles, subtitles, keywords, descriptions, what's-new, promo text, URLs) into `./metadata/<app-slug>/<version>/<locale>/`. |
| `src/patch_metadata.py` | Mutate one localization field, attach a build, or submit a version for review. Defaults to dry-run. |

## On-disk layout (the mirror)

```
metadata/
  <app-slug>/
    bundle-id.txt
    app-id.txt
    live-version.txt
    <version>/
      version-id.txt
      attached-build-id.txt
      <locale>/
        title.txt
        subtitle.txt
        description.txt
        keywords.txt
        whats-new.txt
        promotional-text.txt
        support-url.txt
        marketing-url.txt
        privacy-policy-url.txt
    changelog.md            # append-only audit trail
```

The mirror is what lets the agent treat ASC as a single source of truth
while still being able to operate offline (drafting, reviewing diffs,
preparing promotions).

## Documentation

- [docs/architecture.md](docs/architecture.md) — how the agent is
  structured and why.
- [docs/review-submissions.md](docs/review-submissions.md) — the modern
  3-step App Store review submission flow (and the legacy endpoint
  tripwires to avoid).
- [docs/audit-trail.md](docs/audit-trail.md) — what goes in
  `changelog.md` and why.

## Templates

- [templates/changelog.example.md](templates/changelog.example.md) —
  the audit-trail entry structure, populated with placeholders.
- [templates/metadata_layout.example.md](templates/metadata_layout.example.md) —
  the per-app, per-version, per-locale directory shape.

## Examples

- [examples/synthetic-app/](examples/synthetic-app/) — a fictional app
  used to show what populated metadata files look like. Nothing in here
  is real.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pull requests for bug fixes,
additional ASC endpoint wrappers, and synthetic examples are welcome.
Real app data is not — see SECURITY.md for why.

## Security

See [SECURITY.md](SECURITY.md). **Do not file public issues about
credentials.** Use the contact at the bottom of that document.

## License

Apache 2.0. See [LICENSE](LICENSE).
