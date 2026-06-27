"""Locate repo ``data/`` from playsim runs (local repo root or Docker mount)."""

from __future__ import annotations

import os
from pathlib import Path


def find_data_root(explicit: str | Path | None = None) -> Path:
    """Return directory containing ``players.json`` (usually repo root)."""
    if explicit:
        root = Path(explicit).resolve()
        if (root / "data" / "players.json").is_file():
            return root
        if (root / "players.json").is_file():
            return root.parent if root.name == "data" else root
        raise FileNotFoundError(f"no players.json under {root}")

    env = os.environ.get("PLAYSIM_DATA_ROOT")
    if env:
        return find_data_root(env)

    here = Path(__file__).resolve()
    candidates = [Path.cwd(), *here.parents, *here.parent.parent.parents]
    seen: set[Path] = set()
    for base in candidates:
        base = base.resolve()
        if base in seen:
            continue
        seen.add(base)
        if (base / "data" / "players.json").is_file():
            return base
    raise FileNotFoundError(
        "could not find data/players.json — set PLAYSIM_DATA_ROOT or pass --data-root"
    )


def data_dir(root: str | Path | None = None) -> Path:
    root = find_data_root(root) if root is not None else find_data_root()
    d = root / "data"
    if d.is_dir():
        return d
    if (root / "players.json").is_file():
        return root
    raise FileNotFoundError(f"no data/ under {root}")
