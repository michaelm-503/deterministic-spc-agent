from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runner.registry import SQL_REGISTRY, PREPROCESS_REGISTRY, PLOT_REGISTRY, TABLE_REGISTRY
from spc_agent.agent.planner_llm import call_llm_planner
from spc_agent.agent.planner_parser import parse_planner_output
from spc_agent.agent.planner_prompt import (
    build_context_recovery_prompt,
    build_planner_system_prompt,
)
from spc_agent.agent.planner_curated import PlannerResult, generate_plan_from_prompt_curated


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


def _normalize_prompt(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\\s]", " ", text)
    text = re.sub(r"\\s+", " ", text)
    return text


def _load_plan_library(planner_file: Path) -> dict[str, Any]:
    return json.loads(planner_file.read_text())


def _match_demo_run(
    prompt: str,
    planner_file: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    if not planner_file.exists():
        return None, None

    plan_lib = _load_plan_library(planner_file)
    runs = plan_lib.get("runs", []) or []

    exact_prompt = prompt.strip()
    norm_prompt = _normalize_prompt(prompt)

    for run in runs:
        request_text = str(run.get("request_text", "")).strip()
        if request_text == exact_prompt:
            return run, "exact_demo_match"

    for run in runs:
        request_text = str(run.get("request_text", "")).strip()
        if _normalize_prompt(request_text) == norm_prompt:
            return run, "normalized_demo_match"

    return None, None


def generate_plan_from_prompt(
    prompt: str,
    project_root: Path | str,
    *,
    planner_backend: str = "curated",
    planner_file: str = "planner/demo_gallery.json",
    planner_config: dict[str, Any] | None = None,
) -> PlannerResult:
    project_root = Path(project_root)
    planner_config = planner_config or {}
    planner_file_path = (project_root / planner_file).resolve() if not Path(planner_file).is_absolute() else Path(planner_file)

    if planner_backend == "auto":
        matched_run, match_context = _match_demo_run(prompt, planner_file_path)
        if matched_run is not None:
            return PlannerResult(
                prompt=prompt,
                plan=matched_run,
                planner_backend="curated",
                planner_context=str(match_context),
                raw_output=json.dumps(matched_run, indent=2),
            )
        planner_backend = "llm"

    if planner_backend == "curated":
        return generate_plan_from_prompt_curated(
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
    planner_config = planner_config or {}

    base_system_prompt = _build_base_system_prompt(project_root)
    recovery_block = build_context_recovery_prompt(
        user_prompt=user_prompt,
        prior_run_json=prior_run_json_text,
        prior_job_json=prior_job_json_text,
    )

    system_prompt = f"{base_system_prompt}\\n\\n{recovery_block}"

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