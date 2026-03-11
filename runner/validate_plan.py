from __future__ import annotations

from typing import Any

from runner.registry import SQL_REGISTRY, PREPROCESS_REGISTRY, PLOT_REGISTRY, TABLE_REGISTRY


class PlanValidationError(ValueError):
    """Raised when a plan fails lightweight schema/registry validation."""


def _require(d: dict, key: str, path: str):
    if key not in d:
        raise PlanValidationError(f"Missing required key '{key}' at {path}.")


def _require_type(val: Any, expected_type: type, path: str):
    if not isinstance(val, expected_type):
        raise PlanValidationError(
            f"Expected {path} to be {expected_type.__name__}, got {type(val).__name__}."
        )


def validate_run_plan(run_plan: dict) -> None:
    _require_type(run_plan, dict, "run")
    _require(run_plan, "run_id", "run")
    _require(run_plan, "request_text", "run")
    _require(run_plan, "jobs", "run")

    _require_type(run_plan["jobs"], list, "run.jobs")
    if len(run_plan["jobs"]) == 0:
        raise PlanValidationError("run.jobs must contain at least one job.")

    for i, job in enumerate(run_plan["jobs"]):
        validate_job(job, path=f"run.jobs[{i}]")


def validate_job(job: dict, path: str = "job") -> None:
    _require_type(job, dict, path)

    for k in ["job_id", "sql_template", "preprocess", "filters"]:
        _require(job, k, path)

    sql_key = job["sql_template"]
    if sql_key not in SQL_REGISTRY:
        raise PlanValidationError(f"{path}.sql_template='{sql_key}' not in SQL_REGISTRY.")

    preprocess_key = job["preprocess"]
    if preprocess_key not in PREPROCESS_REGISTRY:
        raise PlanValidationError(f"{path}.preprocess='{preprocess_key}' not in PREPROCESS_REGISTRY.")

    _require_type(job["filters"], dict, f"{path}.filters")

    outputs = job.get("outputs", {}) or {}
    _require_type(outputs, dict, f"{path}.outputs")

    plots = outputs.get("plots", []) or []
    _require_type(plots, list, f"{path}.outputs.plots")

    tables = outputs.get("tables", []) or []
    _require_type(tables, list, f"{path}.outputs.tables")

    if len(plots) + len(tables) == 0:
        raise PlanValidationError(
            f"{path} must declare at least one visible output artifact in outputs.plots or outputs.tables."
        )

    for j, plot_spec in enumerate(plots):
        validate_plot_spec(plot_spec, path=f"{path}.outputs.plots[{j}]")

    for j, table_spec in enumerate(tables):
        validate_table_spec(table_spec, path=f"{path}.outputs.tables[{j}]")


def validate_plot_spec(plot_spec: dict, path: str) -> None:
    _require_type(plot_spec, dict, path)
    _require(plot_spec, "plot", path)
    _require(plot_spec, "plot_name", path)

    plot_key = plot_spec["plot"]
    if plot_key not in PLOT_REGISTRY:
        raise PlanValidationError(f"{path}.plot='{plot_key}' not in PLOT_REGISTRY.")

    params = plot_spec.get("params", {}) or {}
    _require_type(params, dict, f"{path}.params")


def validate_table_spec(table_spec: dict, path: str) -> None:
    _require_type(table_spec, dict, path)
    _require(table_spec, "table", path)
    _require(table_spec, "table_name", path)

    table_key = table_spec["table"]
    if table_key not in TABLE_REGISTRY:
        raise PlanValidationError(f"{path}.table='{table_key}' not in TABLE_REGISTRY.")

    params = table_spec.get("params", {}) or {}
    _require_type(params, dict, f"{path}.params")


def validate_plan_library(plan_lib: dict) -> None:
    _require_type(plan_lib, dict, "plan_lib")
    _require(plan_lib, "runs", "plan_lib")
    _require_type(plan_lib["runs"], list, "plan_lib.runs")
    for run in plan_lib["runs"]:
        validate_run_plan(run)