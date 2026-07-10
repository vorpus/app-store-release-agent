# Contributing

Thanks for considering a contribution. This repo is small on purpose:
a few hundred lines of Python, a markdown doc, an example or two. New
contributions are welcome; please read this short guide before opening
a PR.

## What kind of contribution is welcome

| Kind | Examples | Notes |
|---|---|---|
| **Bug fix** in any of the three scripts | typo in error message, off-by-one in pagination, missing `read_text` strip | Plain `git diff` |
| **New endpoint wrapper** | an extra `cmd_*` in `src/patch_metadata.py` for an ASC endpoint we don't yet cover | Stay within what's reachable from the JWT we already sign |
| **Doc improvements** | clearer wording in `README.md`, an extra example in `docs/`, missing context in `SECURITY.md` | No code change |
| **Synthetic example** | a second fictional app under `examples/synthetic-app/`, additional locale files for the existing one | Keep it synthetic |
| **Test coverage** | pytest file covering `_resolve_target_version` or the version-state logic | Mock the ASC client, not the live API |

## What isn't welcome

- **Real app metadata, real `.p8` keys, real audit-trail entries.** See
  [SECURITY.md](SECURITY.md) for why and what to do if it slipped
  into a PR.
- **Generalization-by-feature-flag.** If your change would need a
  `--use-new-thing` flag at runtime, it probably belongs in a fork,
  not here.
- **Dependencies on heavyweight frameworks.** The scripts intentionally
  run on stdlib + `requests` + `PyJWT`. A PR that adds an ORM, an
  HTTP client wrapper, or a CLI framework will be closed with a
  pointer to the existing approach.

## Style

- Python ≥ 3.10, PEP 8-ish, docstrings on every public function.
- Mutating scripts default to **dry-run** and require an explicit
  `--apply` to commit. Don't relax that without a strong reason.
- Long lines are fine — readability matters more than 79-cols here.

## Local testing

```bash
# 1. Get the requirements
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the smoke test (uses your live ASC credentials)
ASC_ISSUER_ID=… ASC_KEY_ID=… ASC_PRIVATE_KEY_PATH=… \
    python3 src/smoke_test.py

# 3. Verify edits on a synthetic example
mkdir -p metadata/fictional-app/1.0/en-US
cp examples/synthetic-app/fictional-app/1.0/en-US/*.txt metadata/fictional-app/1.0/en-US/
ASC_… python3 src/patch_metadata.py \
    --app fictional-app --locale en-US \
    --field keywords --file /tmp/new-keywords.txt \
    --apply    # <-- still don't do this against your live app
```

The `--apply` flag exists so dev iteration is fast; never combine it
with a real `--app` slug in tests that aren't actually running on a
sandbox ASC account.

## How PRs are reviewed

- One maintainer. Reviews usually within a week, often faster.
- If your change touches anything in `src/`, please add or update a
  doc entry under `docs/` explaining the why (one paragraph is plenty).
- If your change adds a new synthetic example, make sure it doesn't
  include anything resembling a real App Store title or keyword — even
  one or two shared words is enough to be misleading.

## Code of conduct

Be polite, assume good faith, and don't surprise people with large
reorganizations of files they don't own. That's all.
