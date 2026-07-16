"""Reject operational data and credential-shaped files from the public tree."""
from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


ROOT = PurePosixPath(".")
FORBIDDEN_NAMES = {
    ".env",
    "identifiers.txt",
    "applyra.json",
    "applyra_app_id.txt",
}
FORBIDDEN_SUFFIXES = {".p8", ".pem", ".key", ".p12", ".pfx"}


def tracked_files() -> list[PurePosixPath]:
    """Return paths tracked by Git, so ignored local runtime data is irrelevant."""
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [PurePosixPath(item) for item in output.decode().split("\0") if item]


def is_forbidden(path: PurePosixPath) -> str | None:
    """Return the policy violation for a path, if any."""
    parts = path.parts
    if parts and parts[0] == "metadata":
        return "runtime metadata must live in ASC_WORKSPACE_DIR, not this repository"
    if path.name in FORBIDDEN_NAMES or path.name.startswith(".env."):
        return "credential or provider-runtime file"
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return "private-key or certificate file"
    if "applyra_history" in parts:
        return "provider ranking history is operational data"
    return None


def main() -> int:
    """Print all violations and return a nonzero status when any are found."""
    violations = [
        f"{path}: {reason}"
        for path in tracked_files()
        if (reason := is_forbidden(path))
    ]
    if violations:
        print("Public-tree policy violations:", file=sys.stderr)
        print("\n".join(f"  - {item}" for item in violations), file=sys.stderr)
        return 1
    print("Public-tree policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
