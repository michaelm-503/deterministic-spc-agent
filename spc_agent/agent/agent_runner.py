from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spc_agent.agent.planner import generate_plan_from_prompt
from spc_agent.agent.report_writer import write_run_summary


@dataclass(frozen=True)
class AgentRunResult:
    prompt: str
    plan: dict[str, Any] | None
    run_dir: Path | None
    run_summary_path: Path | None
    verification_ok: bool
    verification_summary: str
    planner_backend: str
    planner_context: str
    planner_raw_output: str | None = None
    unsupported_request: bool = False
    unsupported_reason: str | None = None


def _resolve_single_run(plan_or_lib: dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan_or_lib.get("runs"), list):
        runs = plan_or_lib["runs"]
        if len(runs) != 1:
            raise ValueError(
                f"Planner returned {len(runs)} runs. ask_agent() expects exactly one run."
            )
        return runs[0]
    return plan_or_lib


def ask_agent(
    prompt: str,
    project_root: Path | str,
    *,
    planner_backend: str = "stub",
    planner_file: str = "planner/demo_gallery.json",
    planner_config: dict[str, Any] | None = None,
    show_json: bool = False,
) -> AgentRunResult:
    from runner.run_one_run import run_one_run
    from runner.validate_plan import validate_run_plan
    from verify.verify_hashes import verify_run_hashes, format_verification_result

    project_root = Path(project_root)

    planner_result = generate_plan_from_prompt(
        prompt=prompt,
        project_root=project_root,
        planner_backend=planner_backend,
        planner_file=planner_file,
        planner_config=planner_config,
    )

    plan_obj = planner_result.plan

    if plan_obj.get("unsupported_request") is True:
        reason = str(plan_obj.get("reason", "unsupported_request"))
        return AgentRunResult(
            prompt=prompt,
            plan=plan_obj,
            run_dir=None,
            run_summary_path=None,
            verification_ok=False,
            verification_summary="Unsupported request. No execution performed.",
            planner_backend=planner_result.planner_backend,
            planner_context=planner_result.planner_context,
            planner_raw_output=planner_result.raw_output,
            unsupported_request=True,
            unsupported_reason=reason,
        )

    run_plan = _resolve_single_run(plan_obj)
    validate_run_plan(run_plan)
    run_dir = run_one_run(run_plan, project_root)

    verification_result = verify_run_hashes(run_dir)
    verification_summary = format_verification_result(verification_result)

    run_summary_path = write_run_summary(
        prompt=prompt,
        plan=run_plan,
        run_dir=run_dir,
        verification_summary=verification_summary,
        planner_source=planner_result.planner_backend,
        matched_request_text=planner_result.planner_context,
        show_json=show_json,
    )

    if planner_result.raw_output is not None:
        (run_dir / "planner_raw.txt").write_text(planner_result.raw_output)
        (run_dir / "planner_plan.json").write_text(json.dumps(run_plan, indent=2))

    return AgentRunResult(
        prompt=prompt,
        plan=run_plan,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        verification_ok=verification_result.ok,
        verification_summary=verification_summary,
        planner_backend=planner_result.planner_backend,
        planner_context=planner_result.planner_context,
        planner_raw_output=planner_result.raw_output,
        unsupported_request=False,
        unsupported_reason=None,
    )