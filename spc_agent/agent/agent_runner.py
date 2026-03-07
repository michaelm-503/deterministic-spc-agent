from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spc_agent.agent.planner_llm import generate_plan_from_prompt
from spc_agent.agent.report_writer import write_run_summary


@dataclass(frozen=True)
class AgentRunResult:
    prompt: str
    plan: dict[str, Any]
    run_dir: Path
    run_summary_path: Path
    verification_ok: bool
    verification_summary: str
    planner_source: str
    matched_request_text: str


def ask_agent(
    prompt: str,
    project_root: Path | str,
    *,
    planner_file: str = "planner/demo_gallery.json",
) -> AgentRunResult:
    """
    Phase 4A orchestration backend.

    Flow:
      1) prompt -> supported plan match
      2) validate plan
      3) execute deterministic run
      4) verify artifacts
      5) write run_summary.md
      6) return structured result object
    """
    from runner.run_one_run import run_one_run
    from runner.validate_plan import validate_run_plan
    from verify.verify_hashes import verify_run_hashes, format_verification_result

    project_root = Path(project_root)

    planner_result = generate_plan_from_prompt(
        prompt=prompt,
        project_root=project_root,
        planner_file=planner_file,
    )
    print(f"Matched planner prompt: {planner_result.matched_request_text}")
    
    run_plan = planner_result.plan

    validate_run_plan(run_plan)
    run_dir = run_one_run(run_plan, project_root)

    verification_result = verify_run_hashes(run_dir)
    verification_summary = format_verification_result(verification_result)

    run_summary_path = write_run_summary(
        prompt=prompt,
        plan=run_plan,
        run_dir=run_dir,
        verification_summary=verification_summary,
        planner_source=planner_result.source_path,
        matched_request_text=planner_result.matched_request_text,
        show_json=True,
    )

    return AgentRunResult(
        prompt=prompt,
        plan=run_plan,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        verification_ok=verification_result.ok,
        verification_summary=verification_summary,
        planner_source=planner_result.source_path,
        matched_request_text=planner_result.matched_request_text,
    )
