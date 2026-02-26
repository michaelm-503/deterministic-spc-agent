from __future__ import annotations

from typing import Any

from runner.registry import SQL_REGISTRY, PREPROCESS_REGISTRY, PLOT_REGISTRY, TABLE_REGISTRY


class PlanValidationError(ValueError):
    """Raised when a plan fails lightweight schema/registry validation."""


def _require(d: dict, key: str, path: str):
    if key not in d:
        raise PlanValidationError(
            f"Missing required key '{key}' at {path}. "
            f"Object keys present: {sorted(d.keys())}. "
            f"This key is required by the v0.2.0 schema."
        )


def _require_type(val: Any, expected_type: type, path: str):
    if not isinstance(val, expected_type):
        raise PlanValidationError(f"Expected {path} to be {expected_type.__name__}, got {type(val).__name__}")


def validate_run_plan(run_plan: dict) -> None:
    """
    Validate one run object (not the entire library).
    Expected shape:
      { "run_id": str, "request_text": str, "jobs": [ ... ] }
    """
    _require_type(run_plan, dict, "run")

    _require(run_plan, "run_id", "run")
    _require(run_plan, "request_text", "run")
    _require(run_plan, "jobs", "run")

    _require_type(run_plan["jobs"], list, "run.jobs")
    if len(run_plan["jobs"]) == 0:
        raise PlanValidationError("run.jobs must contain at least one job")

    for i, job in enumerate(run_plan["jobs"]):
        validate_job(job, path=f"run.jobs[{i}]")


def validate_job(job: dict, path: str = "job") -> None:
    _require_type(job, dict, path)

    # Required keys
    for k in ["job_id", "sql_template", "preprocess", "filters"]:
        _require(job, k, path)

    # Registry checks
    sql_key = job["sql_template"]
    if sql_key not in SQL_REGISTRY:
        raise PlanValidationError(
            f"{path}.sql_template='{sql_key}' not in SQL_REGISTRY. "
            f"Valid: {sorted(SQL_REGISTRY.keys())}"
    )
    
    preprocess_key = job["preprocess"]
    if preprocess_key not in PREPROCESS_REGISTRY:
        raise PlanValidationError(
            f"{path}.preprocess='{preprocess_key}' not in PREPROCESS_REGISTRY. "
            f"Valid: {sorted(PREPROCESS_REGISTRY.keys())}"
    )


    # Filters: required container; content varies by job type
    _require_type(job["filters"], dict, f"{path}.filters")

    # Outputs are optional
    outputs = job.get("outputs", {})
    if outputs is None:
        outputs = {}
    _require_type(outputs, dict, f"{path}.outputs")

    # Validate plots
    plots = outputs.get("plots", [])
    if plots is None:
        plots = []
    _require_type(plots, list, f"{path}.outputs.plots")

    for j, plot_spec in enumerate(plots):
        validate_plot_spec(plot_spec, path=f"{path}.outputs.plots[{j}]")

    # Validate tables (if present)
    tables = outputs.get("tables", [])
    if tables is None:
        tables = []
    _require_type(tables, list, f"{path}.outputs.tables")

    for j, table_spec in enumerate(tables):
        validate_table_spec(table_spec, path=f"{path}.outputs.tables[{j}]")


def validate_plot_spec(plot_spec: dict, path: str) -> None:
    _require_type(plot_spec, dict, path)
    _require(plot_spec, "plot", path)

    if "plot_name" not in plot_spec:
        raise PlanValidationError(
            f"{path} is missing required key 'plot_name'. "
            f"Each plot must define a deterministic output filename. "
            f"Example:\n"
            f'  {{ "plot": "spc_time_series", "plot_name": "example.png" }}'
        )

    plot_key = plot_spec["plot"]
    if plot_key not in PLOT_REGISTRY:
        raise PlanValidationError(
            f"{path}.plot='{plot_key}' not in PLOT_REGISTRY. "
            f"Valid: {sorted(PLOT_REGISTRY.keys())}"
    )

    # params optional
    params = plot_spec.get("params", {})
    if params is None:
        params = {}
    _require_type(params, dict, f"{path}.params")


def validate_table_spec(table_spec: dict, path: str) -> None:
    _require_type(table_spec, dict, path)
    _require(table_spec, "table", path)
    
    if "table_name" not in table_spec:
        raise PlanValidationError(
            f"{path} is missing required key 'table_name'. "
            f"Each table must define a deterministic output filename. "
            f"Example:\n"
            f'  {{ "table": "fleet_ooc_summary", "table_name": "summary.csv" }}'
        )

    table_key = table_spec["table"]
    if table_key not in TABLE_REGISTRY:
        raise PlanValidationError(
            f"{path}.table='{table_key}' not in TABLE_REGISTRY. "
            f"Valid: {sorted(TABLE_REGISTRY.keys())}"
    )

    
    params = table_spec.get("params", {})
    if params is None:
        params = {}
    _require_type(params, dict, f"{path}.params")

def validate_plan_library(plan_lib: dict) -> None:
    _require_type(plan_lib, dict, "plan_lib")
    _require(plan_lib, "runs", "plan_lib")
    _require_type(plan_lib["runs"], list, "plan_lib.runs")
    for i, run in enumerate(plan_lib["runs"]):
        validate_run_plan(run)