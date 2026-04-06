import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import os
import duckdb

from runner.registry import SQL_REGISTRY, PREPROCESS_REGISTRY, PLOT_REGISTRY, TABLE_REGISTRY
from runner.validate_plan import validate_run_plan
from verify.compute_hashes import compute_run_hashes, write_hash_manifest

def execute_job(con, project_root: Path, run_dir: Path, job: dict, run_id: str | None) -> list[Path]:
    """
    Execute one job through the deterministic pipeline:

      1) resolve SQL template + parameters
      2) run SQL extract once
      3) preprocess once
      4) generate 0..N plots / tables from the same processed dataframe

    Returns
    -------
    list[Path]
        Plot paths created by this job.
    """
    run_id = run_id or "<unknown_run_id>"

    # ------------------------------------------------------------------
    # Resolve job configuration
    # ------------------------------------------------------------------
    job_id = job["job_id"]
    filters = job["filters"]
    preprocess_key = job["preprocess"]
    params = job.get("params", {})       # preprocess params
    outputs = job.get("outputs", {})     # plot/table config

    job_dir = run_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save job spec for traceability
    (job_dir / "job.json").write_text(json.dumps(job, indent=2))

    # ------------------------------------------------------------------
    # Resolve SQL template and parameter values
    # ------------------------------------------------------------------
    sql_template_key = job["sql_template"]
    sql_spec = SQL_REGISTRY[sql_template_key]
    sql_path = sql_spec.path

    # Parse timestamps once so both static and rendered SQL paths use the
    # same canonical values
    start_ts = _parse_ts(filters.get("start_ts"))
    end_ts = _parse_ts(filters.get("end_ts"))

    if getattr(sql_spec, "renderer", None):
        try:
            sql, sql_params = sql_spec.renderer(
                sql_path,
                entity_group=filters.get("entity_group"),
                entity=filters.get("entity"),
                start_ts=start_ts,
                end_ts=end_ts,
            )
        except Exception as e:
            raise RuntimeError(
                f"SQL rendering failed for run_id='{run_id}' job_id='{job_id}' "
                f"sql_template='{sql_template_key}' "
                f"sql_file='{sql_path.name}' "
                f"filters={filters} "
                f"error={type(e).__name__}: {e}"
            ) from e
    else:
        sql = sql_path.read_text()

        value_map = {
            **filters,
            "start_ts": start_ts,
            "end_ts": end_ts,
        }

        try:
            sql_params = [value_map[name] for name in sql_spec.params]
        except KeyError as e:
            missing = str(e).strip("'")
            raise KeyError(
                f"Job '{job_id}' sql_template='{sql_template_key}' "
                f"missing required SQL param '{missing}'. "
                f"SQL signature requires: {list(sql_spec.params)}. "
                f"Filters provided: {list(filters.keys())}"
            ) from e

    # ------------------------------------------------------------------
    # Run SQL extract
    # ------------------------------------------------------------------
    try:
        df = con.execute(sql, sql_params).df()
    except Exception as e:
        raise RuntimeError(
            f"SQL execution failed for run_id='{run_id}' job_id='{job_id}' "
            f"sql_template='{sql_template_key}' "
            f"sql_file='{sql_path.name}' "
            f"param_signature={list(sql_spec.params)} "
            f"param_values={sql_params} "
            f"error={type(e).__name__}: {e}"
        ) from e

    if df.empty:
        raise ValueError(
            f"SQL returned 0 rows for run_id='{run_id}' job_id='{job_id}' "
            f"filters={filters} sql_template='{sql_template_key}'"
        )

    extracted_path = job_dir / "extracted_data.csv"
    df.to_csv(extracted_path, index=False)

    # ------------------------------------------------------------------
    # Run preprocess
    # ------------------------------------------------------------------
    preprocess_fn = PREPROCESS_REGISTRY[preprocess_key]

    try:
        processed_df = preprocess_fn(df, job=job, params=params)
    except Exception as e:
        raise RuntimeError(
            f"Preprocess failed for run_id='{run_id}' job_id='{job_id}' "
            f"preprocess='{preprocess_key}' "
            f"error={type(e).__name__}: {e}"
        ) from e

    if processed_df.empty:
        raise ValueError(
            f"Preprocess returned 0 rows for run_id='{run_id}' job_id='{job_id}' "
            f"preprocess='{preprocess_key}'"
        )

    processed_path = job_dir / "processed_data.csv"
    processed_df.to_csv(processed_path, index=False)

    # ------------------------------------------------------------------
    # Plots (0..N)
    # ------------------------------------------------------------------
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
    
        df_for_plot = _apply_optional_entities(processed_df, plot_params)
        df_for_plot = _apply_optional_time_slice(df_for_plot, plot_params)
        
        plot_fn(
            df_for_plot,
            job=job,
            params=plot_params,
            output_path=plot_path
        )

        plot_paths.append(plot_path)

    # ------------------------------------------------------------------
    # Tables (0..N)
    # ------------------------------------------------------------------
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
        df_for_table = _apply_optional_entities(processed_df, table_params)
        df_for_table = _apply_optional_time_slice(df_for_table, table_params)
        
        # Recommended contract: table function writes output to table_path
        # and may return the DataFrame (useful for notebooks/logging)
        _ = table_fn(
            df_for_table,
            job=job,
            params=table_params,
            output_path=table_path
        )
    
        table_paths.append(table_path)

    return {"plots": plot_paths, "tables": table_paths}

def run_one_run(
    plan: dict,
    project_root: Path,
    *,
    write_hashes: bool = False,
) -> Path:
    # Schema Validation
    validate_run_plan(plan)

    run_timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = project_root / "runs" / run_timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build run.json with reserved metadata block
    job_ids = []
    entities = set()
    entity_groups = set()
    sensors = set()

    for job in plan.get("jobs", []):
        job_id = job.get("job_id")
        if job_id:
            job_ids.append(job_id)

        filters = job.get("filters", {}) or {}

        entity = filters.get("entity")
        if entity:
            entities.add(entity)

        entity_group = filters.get("entity_group")
        if entity_group:
            entity_groups.add(entity_group)

        sensor = filters.get("sensor")
        if sensor:
            sensors.add(sensor)

    run_json = dict(plan)
    run_json["_metadata"] = {
        "timestamp": run_timestamp,
        "job_ids": job_ids,
        "entity_groups": sorted(entity_groups),
        "entities": sorted(entities),
        "sensors": sorted(sensors),
    }

    (run_dir / "run.json").write_text(json.dumps(run_json, indent=2))

    # Conditional path for smoketest vs. actual run
    db_path = os.environ.get("SPC_AGENT_DUCKDB_PATH")
    if db_path is None:
        db_path = str(project_root / "data" / "mfg.duckdb")
    con = duckdb.connect(db_path)

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

    if write_hashes:
        hashes = compute_run_hashes(run_dir)
        write_hash_manifest(run_dir, hashes)

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

def _apply_optional_entities(df, params):
    entities = params.get("entities")
    if not entities:
        return df
    if "entity" not in df.columns:
        return df
    return df[df["entity"].isin(entities)].copy()

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