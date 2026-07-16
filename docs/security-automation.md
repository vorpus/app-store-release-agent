# Security automation

The repository uses three overlapping controls:

1. GitHub secret scanning and push protection detect supported credentials at
   the hosting boundary.
2. The `Security checks` workflow runs Gitleaks over the complete Git history
   on pull requests, pushes to `main`, a weekly schedule, and manual dispatch.
3. `scripts/verify_public_tree.py` rejects production runtime metadata and
   provider caches. Secret scanners cannot reliably recognize these as secrets,
   but they are still sensitive business data.

Before the first protected release, enable GitHub secret scanning and push
protection in the repository settings, run the workflow manually, and triage
every historical finding. Require both security workflow jobs in branch
protection.

For a fast local check, run:

```bash
python scripts/verify_public_tree.py
gitleaks git --redact --config .gitleaks.toml
```

Contributors can also install the pre-push-adjacent local hook with
`pre-commit install`. The hook catches ordinary staged changes; CI remains the
authoritative full-history check.

The source checkout is deliberately not the runtime workspace. Set
`ASC_WORKSPACE_DIR` to a directory outside this repository before fetching ASC
metadata or using the Applyra provider. Keep that directory private and out of
Git.
