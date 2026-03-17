from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runner.registry import SQL_REGISTRY, PREPROCESS_REGISTRY, PLOT_REGISTRY, TABLE_REGISTRY
from spc_agent.agent.planner_llm import call_llm_planner
from spc_agent.agent.planner_parser import parse_planner_output
from spc_agent.agent.planner_prompt import (
    build_context_recovery_prompt,
    build_planner_system_prompt,
)
from spc_agent.agent.planner_stub import PlannerResult, generate_plan_from_prompt_stub


def get_registry_allowlists() -> dict[str, list[str]]:
    return {
        "sql_templates": sorted(SQL_REGISTRY.keys()),
        "preprocess": sorted(PREPROCESS_REGISTRY.keys()),
        "plots": sorted(PLOT_REGISTRY.keys()),
        "tables": sorted(TABLE_REGISTRY.keys()),
    }


def load_planner_catalog(
    project_root: Path | str,
    *,
    catalog_rel: str = "planner/metadata/catalog.json",
) -> dict[str, Any]:
    project_root = Path(project_root)
    catalog_path = project_root / catalog_rel
    if not catalog_path.exists():
        raise FileNotFoundError(
            f"Planner catalog not found: {catalog_path}. "
            "Run setup_data.py and build_planner_catalog.py first."
        )
    return json.loads(catalog_path.read_text())


def _build_base_system_prompt(project_root: Path | str) -> str:
    allowlists = get_registry_allowlists()
    catalog = load_planner_catalog(project_root)

    return build_planner_system_prompt(
        sql_keys=allowlists["sql_templates"],
        preprocess_keys=allowlists["preprocess"],
        plot_keys=allowlists["plots"],
        table_keys=allowlists["tables"],
        entity_group_keys=catalog["entity_groups"],
        entity_keys=catalog["entities"],
        sensor_keys=catalog["sensors"],
        project_root=project_root,
    )


def generate_plan_from_prompt(
    prompt: str,
    project_root: Path | str,
    *,
    planner_backend: str = "stub",
    planner_file: str = "planner/demo_gallery.json",
    planner_config: dict[str, Any] | None = None,
) -> PlannerResult:
    project_root = Path(project_root)
    planner_config = planner_config or {}

    if planner_backend == "stub":
        return generate_plan_from_prompt_stub(
            prompt=prompt,
            project_root=project_root,
            planner_file=planner_file,
            threshold=float(planner_config.get("threshold", 0.4)),
        )

    if planner_backend == "llm":
        system_prompt = _build_base_system_prompt(project_root)

        raw_text = call_llm_planner(
            prompt=prompt,
            system_prompt=system_prompt,
            model=str(planner_config.get("model", "gpt-4.1")),
            temperature=float(planner_config.get("temperature", 0.0)),
        )

        plan = parse_planner_output(raw_text)

        return PlannerResult(
            prompt=prompt,
            plan=plan,
            planner_backend="llm",
            planner_context="llm_generated_plan",
            raw_output=raw_text,
        )

    raise ValueError(f"Unsupported planner_backend: {planner_backend}")


def generate_plan_from_context(
    *,
    user_prompt: str,
    project_root: Path | str,
    prior_run_json_text: str,
    prior_job_json_text: str | None = None,
    planner_config: dict[str, Any] | None = None,
) -> PlannerResult:
    """
    Second-pass recovery planner.

    Uses the full planner system prompt plus previous run/job context.
    May return:
      - execution plan
      - replot plan
      - unsupported_request
    """
    planner_config = planner_config or {}

    base_system_prompt = _build_base_system_prompt(project_root)
    recovery_block = build_context_recovery_prompt(
        user_prompt=user_prompt,
        prior_run_json=prior_run_json_text,
        prior_job_json=prior_job_json_text,
    )

    system_prompt = f"{base_system_prompt}\n\n{recovery_block}"

    raw_text = call_llm_planner(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=str(planner_config.get("model", "gpt-4.1")),
        temperature=float(planner_config.get("temperature", 0.0)),
    )

    plan = parse_planner_output(raw_text)

    return PlannerResult(
        prompt=user_prompt,
        plan=plan,
        planner_backend="llm",
        planner_context="context_recovery_plan",
        raw_output=raw_text,
    )