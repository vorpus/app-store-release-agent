# Metadata Mirror Layout

The agent reads and writes a per-app mirror under `metadata/`. This file
defines the exact directory and file shape, so a contributor can extend
it (add a locale, add a new metadata field, etc.) without breaking the
agent's assumptions.

---

## Top level: one folder per app

```
metadata/
  <app-slug>/                # apps/your-app-name, slugified
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
    changelog.md             # append-only audit trail
```

`<app-slug>` is derived from the app name via this slugification (see
`fetch_metadata.py:slugify`):

- Lowercase
- Strip `™`, `®`, `©`
- Replace non-alphanumeric runs with `-`
- Trim leading and trailing `-`

For example, "Stoic & Zen: 999 Wise Quotes" → `stoic-zen-999-wise-quotes`.

## What each file holds

| File | Source on ASC | Notes |
|---|---|---|
| `bundle-id.txt` | `apps[].attributes.bundleId` | Reverse-DNS, doesn't change. |
| `app-id.txt` | `apps[].id` | ASC app UUID, stable. |
| `live-version.txt` | apps' `READY_FOR_SALE` version | Refreshed by `fetch_metadata.py`. |
| `<version>/version-id.txt` | `appStoreVersions[].id` | ASC version UUID. |
| `<version>/attached-build-id.txt` | `appStoreVersions[].relationships.build` | Recorded after a successful `--attach-build`. |
| `<locale>/title.txt` | `appInfoLocalizations[].attributes.name` | App Store title (max ~30 chars). |
| `<locale>/subtitle.txt` | same, `.subtitle` | Max 30 chars. |
| `<locale>/description.txt` | `appStoreVersionLocalizations[].attributes.description` | Max 4000 chars. |
| `<locale>/keywords.txt` | same, `.keywords` | Comma-separated, no spaces after commas, max 100 chars. |
| `<locale>/whats-new.txt` | same, `.whatsNew` | Shown on the Updates tab. |
| `<locale>/promotional-text.txt` | same, `.promotionalText` | Max 170 chars, editable on the fly. |
| `<locale>/support-url.txt` | same, `.supportUrl` | |
| `<locale>/marketing-url.txt` | same, `.marketingUrl` | |
| `<locale>/privacy-policy-url.txt` | `appInfoLocalizations[].attributes.privacyPolicyUrl` | |

## Locale codes

Used verbatim from Apple's list. Most common: `en-US`, `en-GB`, `fr-FR`,
`fr-CA`, `de-DE`, `es-ES`, `ja`, `ko`, `zh-Hans`, `zh-Hant`, `vi`, `pt-BR`,
`pt-PT`, `ro`, `ru`, `it`, `nl`.

A locale folder is created for every locale present on either the app's
`appInfoLocalizations` row or the version's `appStoreVersionLocalizations`
row, regardless of which one contributed the field. Empty `.txt` files
for fields that don't exist at one layer (e.g. `appInfoLocalizations` has
no `description`) are written as empty by `fetch_metadata.py` so that a
diff against the live state is straightforward.

## Adding a new field

To add a new metadata field (e.g. `appStoreVersionLocalizations` adds a
new `releaseNotes` field in a future iOS release):

1. Add to `VERSION_FIELDS` in `src/patch_metadata.py`.
2. Add the JSON attribute name to `FIELD_TO_ATTR`.
3. Add a `release-notes.txt` (or whatever the `slug_name` should be)
   line to `fetch_metadata.py`'s write loop.
4. Update [templates/metadata_layout.example.md](metadata_layout.example.md)
   (this file).
5. Add a changelog entry to the affected app explaining the addition.

That's it. The agent doesn't have a registry elsewhere.
