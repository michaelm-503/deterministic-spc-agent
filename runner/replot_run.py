"""
runner/replot_run.py

Replot (and regenerate tables) from an existing run folder WITHOUT re-querying SQL.

Design goals:
- Deterministic: uses existing artifacts (processed_data.csv) as the source of truth
- Guardrailed: does not touch the database
- Flexible: supports plot/table overrides (e.g., zoom window, legend=False)
- Traceable: writes a replot_plan.json under a timestamped replots/ folder

Expected folder layout (per job):
runs/<run_id>/<job_id>/
  processed_data.csv
  job.json
  (previous plots/tables...)

Replot outputs:
runs/<run_id>/<job_id>/replots/<timestamp>/
  replot_plan.json
  created_artifacts.json
  <plot/table artifacts...>
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from runner.registry import PLOT_REGISTRY, TABLE_REGISTRY
from verify.compute_hashes import compute_run_hashes, write_hash_manifest
from runner.run_lookup import resolve_run_ref

def _apply_optional_time_slice(df: pd.DataFrame, params: dict | None) -> pd.DataFrame:
    """
    Optional time slicing based on params (only when explicitly provided).
    Supports:
      - start_ts (datetime string)
      - end_ts   (datetime string)
      - window_days (int): last N days relative to df['ts'].max()
    """
    params = params or {}
    out = df.copy()

    if "ts" not in out.columns:
        return out

    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    out = out.dropna(subset=["ts"])

    start_ts = params.get("start_ts")
    end_ts = params.get("end_ts")
    window_days = params.get("window_days")

    if start_ts:
        out = out[out["ts"] >= pd.to_datetime(start_ts)]
    if end_ts:
        out = out[out["ts"] <= pd.to_datetime(end_ts)]

    if window_days and not start_ts:
        end_time = out["ts"].max()
        start_time = end_time - timedelta(days=int(window_days))
        out = out[out["ts"] >= start_time]

    return out

def _apply_optional_entities(df, params):
    entities = params.get("entities")
    if not entities:
        return df
    if "entity" not in df.columns:
        return df
    return df[df["entity"].isin(entities)].copy()

def _dedupe_name(name: str, used: set[str]) -> str:
    """If name already used, append _#, preserving extension."""
    candidate = name
    counter = 1
    while candidate in used:
        stem = Path(name).stem
        suffix = Path(name).suffix
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    used.add(candidate)
    return candidate


def _require_columns(
    df: pd.DataFrame,
    required_cols: list[str],
    *,
    run_dir: Path,
    job_id: str,
    stage: str,
    component: str,
) -> None:
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Replot failed for job_id='{job_id}' stage={stage} component='{component}'. "
            f"Missing required columns: {missing}. "
            f"Available columns: {sorted(df.columns)}. "
            f"(run_dir='{run_dir}')"
        )

def _resolve_run_dir(plan: dict, project_root: Path, override_run_dir: str | None) -> Path:
    """
    Resolution order:
      1. explicit CLI override --run-dir
      2. plan.run_dir (backward compatibility)
      3. plan.run_ref (preferred semantic reference)
    """
    if override_run_dir:
        run_dir = Path(override_run_dir)
        if not run_dir.is_absolute():
            run_dir = (project_root / run_dir).resolve()
        return run_dir

    # backward-compatible direct path
    run_dir_str = plan.get("run_dir")
    if run_dir_str:
        run_dir = Path(run_dir_str)
        if not run_dir.is_absolute():
            run_dir = (project_root / run_dir).resolve()
        return run_dir

    # preferred semantic reference
    run_ref = plan.get("run_ref")
    if run_ref is not None:
        return resolve_run_ref(run_ref, project_root).resolve()

    raise ValueError(
        "Replot plan must include one of: 'run_dir' or 'run_ref'. "
        "You may also pass --run-dir to override."
    )

    # fallback to plan value
    run_dir_str = plan.get("run_dir")
    if not run_dir_str:
        raise ValueError(
            "Replot plan missing required key 'run_dir'. "
            "Provide it in JSON or pass --run-dir to override."
        )

    run_dir = Path(run_dir_str)
    if not run_dir.is_absolute():
        run_dir = (project_root / run_dir).resolve()
    return run_dir

def _validate_job_exists(run_dir: Path, job_id: str) -> None:
    """
    Ensure a job_id exists inside the referenced run before attempting replot.
    Provides a clean error instead of a deep FileNotFoundError.

    Tip: run_ref="latest" selects the newest run. 
    Use run_ref={"type":"latest_job_id","job_id":"<job_id>"} to target a specific workflow.
    """
    run_json_path = run_dir / "run.json"

    if not run_json_path.exists():
        raise RuntimeError(f"run.json not found in run directory: {run_dir}")

    run_json = json.loads(run_json_path.read_text())

    metadata = run_json.get("_metadata", {}) or {}
    available_jobs = metadata.get("job_ids", [])

    if job_id not in available_jobs:
        raise RuntimeError(
            f"Replot failed: job_id '{job_id}' was not found in the referenced run.\n"
            f"Available job_ids: {available_jobs}\n"
            f"Resolved run directory: {run_dir}"
        )

def replot_job(
    run_dir: Path | str,
    job_id: str,
    outputs: dict,
    *,
    processed_filename: str = "processed_data.csv",
) -> Path:
    """
    Re-render plots/tables for a single job using existing processed_data.csv.

    Parameters
    ----------
    run_dir : Path | str
        Path to a run directory, e.g. runs/2024-01-15T12-05-11
    job_id : str
        Job id folder name under run_dir
    outputs : dict
        outputs spec shaped like:
        {
          "plots": [
            {"plot": "spc_time_series", "plot_name": "zoom.png", "params": {...}},
            ...
          ],
          "tables": [
            {"table": "fleet_ooc_summary", "table_name": "ooc.csv", "params": {...}},
            ...
          ]
        }
    processed_filename : str
        Name of processed CSV artifact to load from job folder

    Returns
    -------
    Path
        Directory containing the newly generated replot artifacts.
    """
    run_dir = Path(run_dir)
    job_dir = run_dir / job_id

    if not job_dir.exists():
        raise FileNotFoundError(
            f"Job directory not found: '{job_dir}'. "
            f"Expected layout: runs/<run_id>/<job_id>/ (run_dir='{run_dir}', job_id='{job_id}')."
        )

    processed_path = job_dir / processed_filename
    if not processed_path.exists():
        raise FileNotFoundError(
            f"Processed data not found: '{processed_path}'. "
            f"Replot requires a completed job with '{processed_filename}'. "
            f"Expected layout: runs/<run_id>/<job_id>/{processed_filename}."
        )

    job_json_path = job_dir / "job.json"
    if not job_json_path.exists():
        raise FileNotFoundError(
            f"job.json not found: '{job_json_path}'. "
            f"Replot needs job context (filters/sensor/entity) for plotting/table logic. "
            f"Expected layout: runs/<run_id>/<job_id>/job.json."
        )

    job = json.loads(job_json_path.read_text())
    processed_df = pd.read_csv(processed_path)

    if processed_df.empty:
        raise ValueError(
            f"Processed data is empty: '{processed_path}'. "
            f"Cannot replot with 0 rows. (job_id='{job_id}', run_dir='{run_dir}')"
        )

    # Create output folder
    replot_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    out_dir = job_dir / "replots" / replot_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save the replot plan for traceability
    replot_plan = {
        "mode": "replot",
        "run_dir": str(run_dir),
        "job_id": job_id,
        "source_processed_csv": str(processed_path),
        "outputs": outputs,
        "created_at": replot_id,
    }
    (out_dir / "replot_plan.json").write_text(json.dumps(replot_plan, indent=2))

    created: dict[str, list[str]] = {"plots": [], "tables": []}
    used_names: set[str] = set()

    # ---- Plots ----
    for i, plot_spec in enumerate(outputs.get("plots", []) or []):
        if not isinstance(plot_spec, dict):
            raise ValueError(
                f"Invalid plot spec at outputs.plots[{i}]: expected object, got {type(plot_spec).__name__}."
            )

        plot_key = plot_spec.get("plot")
        if not plot_key:
            raise ValueError(f"Missing required key 'plot' at outputs.plots[{i}] (job_id='{job_id}').")

        if plot_key not in PLOT_REGISTRY:
            raise KeyError(
                f"Unknown plot '{plot_key}' at outputs.plots[{i}]. "
                f"Valid plots: {sorted(PLOT_REGISTRY.keys())}"
            )

        plot_fn = PLOT_REGISTRY[plot_key]
        plot_params = plot_spec.get("params", {}) or {}

        base_name = plot_spec.get("plot_name")
        if not base_name:
            raise ValueError(
                f"Missing required key 'plot_name' at outputs.plots[{i}]. "
                f"Each plot must define a deterministic output filename."
            )

        plot_name = _dedupe_name(base_name, used_names)
        plot_path = out_dir / plot_name

        df_for_plot = _apply_optional_entities(processed_df, plot_params)
        df_for_plot = _apply_optional_time_slice(df_for_plot, plot_params)
        
        # Universal plot requirement: ts must exist for time-based rendering
        _require_columns(
            df_for_plot,
            ["ts"],
            run_dir=run_dir,
            job_id=job_id,
            stage="plot",
            component=plot_key,
        )

        try:
            plot_fn(
                df_for_plot,
                job=job,
                params=plot_params,
                output_path=plot_path,
            )
        except Exception as e:
            raise RuntimeError(
                f"Replot plot failed: job_id='{job_id}' plot='{plot_key}' "
                f"plot_name='{plot_name}' error={type(e).__name__}: {e}"
            ) from e

        created["plots"].append(str(plot_path))

    # ---- Tables ----
    for i, table_spec in enumerate(outputs.get("tables", []) or []):
        if not isinstance(table_spec, dict):
            raise ValueError(
                f"Invalid table spec at outputs.tables[{i}]: expected object, got {type(table_spec).__name__}."
            )

        table_key = table_spec.get("table")
        if not table_key:
            raise ValueError(f"Missing required key 'table' at outputs.tables[{i}] (job_id='{job_id}').")

        if table_key not in TABLE_REGISTRY:
            raise KeyError(
                f"Unknown table '{table_key}' at outputs.tables[{i}]. "
                f"Valid tables: {sorted(TABLE_REGISTRY.keys())}"
            )

        table_fn = TABLE_REGISTRY[table_key]
        table_params = table_spec.get("params", {}) or {}

        base_name = table_spec.get("table_name")
        if not base_name:
            raise ValueError(
                f"Missing required key 'table_name' at outputs.tables[{i}]. "
                f"Each table must define a deterministic output filename."
            )

        table_name = _dedupe_name(base_name, used_names)
        table_path = out_dir / table_name

        df_for_table = _apply_optional_entities(processed_df, table_params)
        df_for_table = _apply_optional_time_slice(df_for_table, table_params)

        # Most tables at least need entity, and for OOC summary we need value.
        # Keep universal requirement minimal: entity is common for grouping.
        _require_columns(
            df_for_table,
            ["entity"],
            run_dir=run_dir,
            job_id=job_id,
            stage="table",
            component=table_key,
        )

        try:
            _ = table_fn(
                df_for_table,
                job=job,
                params=table_params,
                output_path=table_path,
            )
        except Exception as e:
            raise RuntimeError(
                f"Replot table failed: job_id='{job_id}' table='{table_key}' "
                f"table_name='{table_name}' error={type(e).__name__}: {e}"
            ) from e

        created["tables"].append(str(table_path))

    (out_dir / "created_artifacts.json").write_text(json.dumps(created, indent=2))
    
    # Create hashes
    hashes = compute_run_hashes(out_dir)
    write_hash_manifest(out_dir, hashes)
    
    return out_dir


def replot_from_plan(plan: dict, project_root: Path | str, *, override_run_dir: str | None = None) -> list[Path]:
    """
    Convenience: replot based on a plan object.

    Supported shapes:

    1. Backward-compatible direct path:
    {
      "mode": "replot",
      "run_dir": "runs/<timestamp>",
      "jobs": [...]
    }

    2. Preferred semantic reference:
    {
      "mode": "replot",
      "run_ref": "latest",
      "jobs": [...]
    }

    or:
    {
      "mode": "replot",
      "run_ref": {
        "type": "latest_job_id",
        "job_id": "arm_vibration_7d"
      },
      "jobs": [...]
    }
    """
    
    if plan.get("mode") != "replot":
        raise ValueError("plan.mode must be 'replot'")

    if ("run_dir" not in plan) and ("run_ref" not in plan) and (override_run_dir is None):
        raise ValueError("Replot plan must include 'run_dir' or 'run_ref'.")

    project_root = Path(project_root)
    
    try:
        run_dir = _resolve_run_dir(plan, project_root, override_run_dir)
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        print(f"❌ Replot aborted: {e}")
        return []
    
    if not run_dir.exists():
        print(
            f"❌ Replot aborted: Run directory not found: '{run_dir}'. "
            f"Expected something like 'runs/2024-01-15T12-05-11'."
        )
        return []

    out_dirs: list[Path] = []
    jobs = plan.get("jobs", []) or []
    if not isinstance(jobs, list) or len(jobs) == 0:
        raise ValueError("replot plan.jobs must be a non-empty list")

    for i, job_spec in enumerate(plan["jobs"]):
    
        if "job_id" not in job_spec:
            raise ValueError(f"Missing required key 'job_id' at plan.jobs[{i}]")
    
        job_id = job_spec["job_id"]
    
        try:
            _validate_job_exists(run_dir, job_id)
    
            outputs = job_spec.get("outputs", {}) or {}
    
            out_dirs.append(
                replot_job(run_dir, job_id, outputs)
            )
    
        except RuntimeError as e:
            print(f"❌ Replot aborted: {e}")
            return []
    
    return out_dirs