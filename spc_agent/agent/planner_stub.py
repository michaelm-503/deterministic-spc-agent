
from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlannerResult:
    prompt: str
    plan: dict[str, Any]
    planner_backend: str
    planner_context: str
    raw_output: str | None = None


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _iter_candidate_runs(plan_obj: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(plan_obj.get("runs"), list):
        return list(plan_obj["runs"])
    if "jobs" in plan_obj:
        return [plan_obj]
    return []


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Planner file not found: {path}")
    return json.loads(path.read_text())


def _best_run_match(prompt: str, runs: list[dict[str, Any]], *, threshold: float = 0.4) -> dict[str, Any]:
    prompt_n = _normalize(prompt)

    for run in runs:
        req = run.get("request_text")
        if isinstance(req, str) and _normalize(req) == prompt_n:
            return run

    scored: list[tuple[float, dict[str, Any]]] = []
    for run in runs:
        req = run.get("request_text", "")
        if not isinstance(req, str):
            continue
        score = SequenceMatcher(None, prompt_n, _normalize(req)).ratio()
        scored.append((score, run))

    if not scored:
        raise ValueError("No candidate runs found in planner source.")

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_run = scored[0]

    if best_score < threshold:
        supported = [
            r.get("request_text", "<missing request_text>")
            for r in runs
            if isinstance(r.get("request_text"), str)
        ]
        raise ValueError(
            "Prompt did not match a supported prompt pattern closely enough. "
            f"Supported prompts include: {supported[:10]}"
        )

    return best_run


def generate_plan_from_prompt_stub(
    prompt: str,
    project_root: Path | str,
    *,
    planner_file: str = "planner/demo_gallery.json",
    threshold: float = 0.4,
) -> PlannerResult:

    project_root = Path(project_root)
    planner_path = project_root / planner_file
    plan_obj = _load_json(planner_path)
    runs = _iter_candidate_runs(plan_obj)

    if not runs:
        raise ValueError(f"No runs found in planner source: {planner_path}")

    matched_run = _best_run_match(prompt, runs, threshold=threshold)

    return PlannerResult(
        prompt=prompt,
        plan=matched_run,
        planner_backend="stub",
        planner_context=matched_run.get("request_text", "<missing request_text>"),
        raw_output=None,
    )
