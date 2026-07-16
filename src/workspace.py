"""Private runtime workspace helpers.

Production ASC mirrors and ASO-provider caches must never be stored in the
public source checkout. Commands that need such data require ASC_WORKSPACE_DIR.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent.parent


def workspace_dir(create: bool = False) -> Path:
    """Return the external runtime workspace, rejecting the source checkout."""
    raw = os.environ.get("ASC_WORKSPACE_DIR")
    if not raw:
        sys.exit(
            "ASC_WORKSPACE_DIR is required for runtime metadata. Set it to a "
            "private directory outside this public source checkout."
        )
    path = Path(raw).expanduser().resolve()
    if path == SOURCE_ROOT or SOURCE_ROOT in path.parents:
        sys.exit("ASC_WORKSPACE_DIR must be outside the public source checkout.")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
