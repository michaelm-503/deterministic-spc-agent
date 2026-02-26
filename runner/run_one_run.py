import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

import duckdb

from runner.registry import SQL_REGISTRY, PREPROCESS_REGISTRY, PLOT_REGISTRY, TABLE_REGISTRY
from runner.validate_plan import validate_run_plan

def execute_job(con, project_root: Path, run_dir: Path, job: dict, run_id: str | None) -> list[Path]:
    """
    Executes one job:
      1) SQL extract (once)
      2) preprocess (once)
      3) generate 0..N plots (and later tables) from same processed df

    Returns: list of plot Paths created
    """
    
    # ---- Resolve SQL spec + build params (signature-driven) ----
    run_id = run_id or "<unknown_run_id>"
    
    sql_spec = SQL_REGISTRY[job["sql_template"]]
    sql_path = sql_spec.path
    sql = sql_path.read_text()
    
    filters = job["filters"]
    
    # Parse timestamps from filters (often null)
    start_ts = _parse_ts(filters.get("start_ts"))
    end_ts = _parse_ts(filters.get("end_ts"))
    
    # Build a value map for signature resolution
    value_map = {
        **filters,
        "start_ts": start_ts,
        "end_ts": end_ts,
    }
    
    # Build params in the declared order
    try:
        sql_params = [value_map[name] for name in sql_spec.params]
    except KeyError as e:
        missing = str(e).strip("'")
        raise KeyError(
            f"Job '{job.get('job_id')}' sql_template='{job['sql_template']}' "
            f"missing required SQL param '{missing}'. "
            f"SQL signature requires: {list(sql_spec.params)}. "
            f"Filters provided: {list(filters.keys())}"
        )

    preprocess_fn = PREPROCESS_REGISTRY[job["preprocess"]]
    params = job.get("params", {})       # preprocess params (e.g., ewma_alpha)
    outputs = job.get("outputs", {})     # outputs config
    
    job_dir = run_dir / job["job_id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save job spec for traceability
    (job_dir / "job.json").write_text(json.dumps(job, indent=2))
    
    # ---- SQL extract ----
    try:
        df = con.execute(sql, sql_params).df()
    except Exception as e:
        raise RuntimeError(
            f"SQL execution failed for run_id='{run_id}' job_id='{job.get('job_id')}' "
            f"sql_template='{job['sql_template']}' "
            f"sql_file='{sql_path.name}' "
            f"param_signature={list(sql_spec.params)} "
            f"param_values={sql_params} "
            f"error={type(e).__name__}: {e}"
        ) from e
    
    if df.empty:
        raise ValueError(
            f"SQL returned 0 rows for run_id='{run_id}' job_id='{job['job_id']}' "
            f"filters={filters} sql_template={job['sql_template']}"
        )
    
    df.to_csv(job_dir / "extracted_data.csv", index=False)

    # ---- Preprocess ----
    processed_df = preprocess_fn(df, job=job, params=params)
    if processed_df.empty:
        raise ValueError(
            f"Preprocess returned 0 rows for job_id={job['job_id']} "
            f"preprocess={job['preprocess']}"
        )
    processed_df.to_csv(job_dir / "processed_data.csv", index=False)

    # ---- Plots (0..N) ----
    plot_paths: list[Path] = []
    plot_specs = outputs.get("plots", [])
    existing_names = set()
    
    for plot_spec in plot_specs:
        plot_key = plot_spec["plot"]
        plot_fn = PLOT_REGISTRY[plot_key]
    
        plot_params = plot_spec.get("params", {}) or {}
        base_name = plot_spec.get("plot_name", f"{job['job_id']}_{plot_key}.png")
    
        # Handle filename collisions
        plot_name = base_name
        counter = 1
        while plot_name in existing_names:
            stem = Path(base_name).stem
            suffix = Path(base_name).suffix
            plot_name = f"{stem}_{counter}{suffix}"
            counter += 1
    
        existing_names.add(plot_name)
        plot_path = job_dir / plot_name
    
        df_for_plot = _apply_optional_time_slice(processed_df, plot_params)

        # Basic universal requirements for all plots
        _require_columns(
            df_for_plot,
            required_cols=["ts"],
            run_id=run_id,
            job_id=job["job_id"],
            stage="plot",
            component=plot_key
        )
        
        plot_fn(
            df_for_plot,
            job=job,
            params=plot_params,
            output_path=plot_path
        )

        plot_paths.append(plot_path)

    # ---- Tables (0..N) ----
    table_specs = outputs.get("tables", [])
    table_paths: list[Path] = []
    
    existing_table_names = set()
    
    for table_spec in table_specs:
        table_key = table_spec["table"]  # e.g. "fleet_ooc_summary"
        table_fn = TABLE_REGISTRY[table_key]
    
        table_params = table_spec.get("params", {}) or {}
        base_name = table_spec.get("table_name", f"{job['job_id']}_{table_key}.csv")
    
        # Handle filename collisions
        table_name = base_name
        counter = 1
        while table_name in existing_table_names:
            stem = Path(base_name).stem
            suffix = Path(base_name).suffix
            table_name = f"{stem}_{counter}{suffix}"
            counter += 1
    
        existing_table_names.add(table_name)
        table_path = job_dir / table_name
    
        # Optional time slice only if explicitly requested in table params
        df_for_table = _apply_optional_time_slice(processed_df, table_params)

        _require_columns(
            df_for_table,
            required_cols=["entity", "value"],
            run_id=run_id,
            job_id=job["job_id"],
            stage="table",
            component=table_key
        )
        
        # Recommended contract: table function writes output to table_path
        # and may return the DataFrame (useful for notebooks/logging)
        _ = table_fn(
            df_for_table,
            job=job,
            params=table_params,
            output_path=table_path
        )
    
        table_paths.append(table_path)

    # ---- Verification/hashes (optional in this phase) ----
    # call your verify module here later

    return {"plots": plot_paths, "tables": table_paths}

def run_one_run(plan: dict, project_root: Path) -> Path:
    # Schema Validation
    validate_run_plan(plan)

    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = project_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "run.json").write_text(json.dumps(plan, indent=2))

    con = duckdb.connect(project_root / "data" / "mfg.duckdb")
    try:
        for idx, job in enumerate(plan["jobs"]):
            try:
                execute_job(con, project_root, run_dir, job, run_id=plan.get("run_id"))
            except Exception as e:
                job_id = job.get("job_id", f"<missing job_id at jobs[{idx}]>")
                raise RuntimeError(
                    f"Run failed: run_id={plan.get('run_id')} job_id={job_id} "
                    f"(jobs[{idx}]) error={type(e).__name__}: {e}"
                ) from e
    finally:
        con.close()

    return run_dir

def _parse_ts(ts):
    """Accept None, datetime, or ISO string; return python datetime or None."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    # assume string
    return pd.to_datetime(ts).to_pydatetime()

def _apply_optional_time_slice(df, plot_params):
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"])

    start_ts = plot_params.get("start_ts")
    end_ts = plot_params.get("end_ts")
    window_days = plot_params.get("window_days")

    if start_ts:
        df = df[df["ts"] >= pd.to_datetime(start_ts)]
    if end_ts:
        df = df[df["ts"] <= pd.to_datetime(end_ts)]

    if window_days and not start_ts:
        end_time = df["ts"].max()
        start_time = end_time - timedelta(days=int(window_days))
        df = df[df["ts"] >= start_time]

    return df

def _require_columns(df, required_cols, *, run_id, job_id, stage, component):
    """
    Ensure required columns exist before passing df to plot/table modules.

    stage: "plot" or "table"
    component: plot/table registry key (e.g., "spc_time_series")
    """
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        raise ValueError(
            f"Run '{run_id}' Job '{job_id}' failed during {stage}='{component}'. "
            f"Missing required columns: {missing}. "
            f"Available columns: {sorted(df.columns)}."
        )