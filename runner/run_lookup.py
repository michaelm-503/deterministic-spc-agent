from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunResolutionError(RuntimeError):
    """Raised when a semantic run reference cannot be resolved."""


def _load_run_json(run_dir: Path) -> dict[str, Any]:
    run_json_path = run_dir / "run.json"
    if not run_json_path.exists():
        raise RunResolutionError(f"run.json not found in run directory: {run_dir}")
    return json.loads(run_json_path.read_text())


def _list_run_dirs(project_root: Path) -> list[Path]:
    runs_root = project_root / "runs"
    if not runs_root.exists():
        return []

    run_dirs = [p for p in runs_root.iterdir() if p.is_dir()]
    run_dirs.sort(key=lambda p: p.name, reverse=True)
    return run_dirs


def resolve_run_ref(run_ref: str | dict[str, Any], project_root: Path) -> Path:
    """
    Resolve a semantic run reference into a concrete runs/<timestamp> directory.

    Supported forms:
      - "latest"
      - {"type": "latest_job_id", "job_id": "<job_id>"}
    """
    run_dirs = _list_run_dirs(project_root)
    if not run_dirs:
        raise RunResolutionError(
            f"No prior runs found under: {project_root / 'runs'}"
        )

    if run_ref == "latest":
        return run_dirs[0]

    if isinstance(run_ref, dict):
        ref_type = run_ref.get("type")

        if ref_type == "latest_job_id":
            job_id = run_ref.get("job_id")
            if not job_id:
                raise RunResolutionError(
                    "run_ref.type='latest_job_id' requires key 'job_id'."
                )

            for run_dir in run_dirs:
                run_json = _load_run_json(run_dir)
                metadata = run_json.get("_metadata", {}) or {}
                job_ids = metadata.get("job_ids", []) or []
                if job_id in job_ids:
                    return run_dir

            raise RunResolutionError(
                f"No prior run found containing job_id='{job_id}'."
            )

        raise RunResolutionError(
            f"Unsupported run_ref.type='{ref_type}'. "
            "Supported types: 'latest_job_id'."
        )

    raise RunResolutionError(
        "Unsupported run_ref. Expected 'latest' or "
        "{'type': 'latest_job_id', 'job_id': '<job_id>'}."
    )