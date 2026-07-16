# Optional Applyra provider

`src/applyra.py` is a read-only ranking provider. It never sends App Store
Connect mutation requests and it is not run by the ASC scripts automatically.

Set the following values in your shell, never in tracked files:

```bash
export ASC_WORKSPACE_DIR="$HOME/.asc/workspaces/my-portfolio"
export APPLYRA_API_KEY="..."
```

For each app, create `$ASC_WORKSPACE_DIR/<app-slug>/applyra_app_id.txt` with
the provider-assigned app ID. Then use:

```bash
python src/applyra.py --app fictional-app --fetch --country US
python src/applyra.py --app fictional-app --report
python src/applyra.py --app fictional-app --audit --version 1.0 --locale en-US
```

`--fetch` writes `applyra.json`; `--history` additionally writes dated
snapshots. Both remain in the external private workspace. The client uses a
fixed HTTPS provider host, bounded retries for transient failures, and never
logs provider response bodies or credentials.
