from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable


_DEFAULT_EXCLUDES = {
    "hashes.json",  # don't hash the hash manifest itself
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 for a file in a streaming way."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(run_dir: Path, excludes: Iterable[str] = _DEFAULT_EXCLUDES) -> Iterable[Path]:
    excludes = set(excludes)
    for p in run_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.name in excludes:
            continue
        yield p


def compute_run_hashes(
    run_dir: Path,
    *,
    excludes: Iterable[str] = _DEFAULT_EXCLUDES,
) -> Dict[str, str]:
    """
    Return a mapping: relative_posix_path -> sha256 hex digest.
    We sort for determinism.
    """
    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"run_dir not found: {run_dir}")

    files = sorted(_iter_files(run_dir, excludes=excludes), key=lambda p: p.as_posix())

    hashes: Dict[str, str] = {}
    for p in files:
        rel = p.relative_to(run_dir).as_posix()
        hashes[rel] = sha256_file(p)

    return hashes


def write_hash_manifest(run_dir: Path, hashes: Dict[str, str], filename: str = "hashes.json") -> Path:
    """Write hashes.json (pretty printed, stable key order)."""
    run_dir = Path(run_dir)
    out_path = run_dir / filename
    out_path.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    return out_path