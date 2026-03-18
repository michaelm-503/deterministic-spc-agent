from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.run_lookup import RunResolutionError, resolve_run_ref
from spc_agent.agent.planner import generate_plan_from_context, generate_plan_from_prompt
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
    recovery_used: bool = False
    recovery_details: dict[str, Any] | None = None


def _vprint(verbose: bool, *args, **kwargs) -> None:
    if verbose:
        print(*args, **kwargs)


def _resolve_single_run(plan_or_lib: dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan_or_lib.get("runs"), list):
        runs = plan_or_lib["runs"]
        if len(runs) != 1:
            raise ValueError(
                f"Planner returned {len(runs)} runs. ask_agent() expects exactly one run."
            )
        return runs[0]
    return plan_or_lib


def _write_planner_debug_artifacts(
    run_dir: Path,
    *,
    planner_raw_output: str | None,
    plan_to_write: dict[str, Any],
) -> None:
    if planner_raw_output is None:
        return

    (run_dir / "planner_raw.txt").write_text(planner_raw_output)
    (run_dir / "planner_plan.json").write_text(json.dumps(plan_to_write, indent=2))


def _is_recovery_sentinel(plan_obj: dict[str, Any]) -> bool:
    return (
        plan_obj.get("mode") == "replot"
        and plan_obj.get("run_ref") == "latest"
        and "jobs" not in plan_obj
    )


def _latest_run_exists(project_root: Path) -> bool:
    runs_dir = project_root / "runs"
    return runs_dir.exists() and any(p.is_dir() for p in runs_dir.iterdir())


def _is_likely_continuation_prompt(prompt: str) -> bool:
    p = prompt.strip().lower()

    starters = (
        "now ",
        "instead ",
        "change ",
        "modify ",
        "update ",
        "remake ",
        "replot ",
        "zoom ",
        "add ",
        "remove ",
        "show me ",
    )
    substrings = (
        " last plot",
        " previous",
        " that plot",
        " that run",
        " instead",
    )

    return p.startswith(starters) or any(s in p for s in substrings)


def _load_latest_run_context(project_root: Path) -> tuple[Path, str]:
    run_dir = resolve_run_ref("latest", project_root)
    run_json_path = run_dir / "run.json"
    if not run_json_path.exists():
        raise FileNotFoundError(f"Previous run.json not found: {run_json_path}")
    return run_dir, run_json_path.read_text()


def _select_prior_job_json(run_dir: Path) -> str | None:
    run_json = json.loads((run_dir / "run.json").read_text())
    jobs = run_json.get("jobs", []) or []
    if len(jobs) == 1:
        return json.dumps(jobs[0], indent=2)
    return None


def _handle_unsupported_plan(
    *,
    prompt: str,
    plan_obj: dict[str, Any],
    planner_backend: str,
    planner_context: str,
    planner_raw_output: str | None,
    recovery_used: bool,
    recovery_details: dict[str, Any] | None,
    verbose: bool,
) -> AgentRunResult:
    reason = str(plan_obj.get("reason", "unsupported_request"))

    _vprint(verbose, "=== unsupported request ===")
    _vprint(verbose, f"reason: {reason}")
    _vprint(verbose)

    return AgentRunResult(
        prompt=prompt,
        plan=plan_obj,
        run_dir=None,
        run_summary_path=None,
        verification_ok=False,
        verification_summary="Unsupported request. No execution performed.",
        planner_backend=planner_backend,
        planner_context=planner_context,
        planner_raw_output=planner_raw_output,
        unsupported_request=True,
        unsupported_reason=reason,
        recovery_used=recovery_used,
        recovery_details=recovery_details,
    )


def _handle_execution_plan(
    *,
    prompt: str,
    plan_obj: dict[str, Any],
    planner_backend: str,
    planner_context: str,
    planner_raw_output: str | None,
    project_root: Path,
    show_json: bool,
    recovery_used: bool,
    recovery_details: dict[str, Any] | None,
    verbose: bool,
) -> AgentRunResult:
    from runner.run_one_run import run_one_run
    from runner.validate_plan import validate_run_plan
    from verify.compute_hashes import compute_run_hashes, write_hash_manifest
    from verify.verify_hashes import verify_run_hashes, format_verification_result
    
    run_plan = _resolve_single_run(plan_obj)

    _vprint(verbose, "=== resolved run plan ===")
    _vprint(verbose, json.dumps(run_plan, indent=2))
    _vprint(verbose)

    validate_run_plan(run_plan)

    _vprint(verbose, "=== validation ===")
    _vprint(verbose, "Run plan validation passed")
    _vprint(verbose)

    run_dir = run_one_run(run_plan, project_root)
    
    _vprint(verbose, "=== execution ===")
    _vprint(verbose, f"run_dir: {run_dir}")
    _vprint(verbose)
    
    run_summary_path = write_run_summary(
        prompt=prompt,
        plan=run_plan,
        run_dir=run_dir,
        planner_source=planner_backend,
        matched_request_text=planner_context,
        recovery_used=recovery_used,
        recovery_details=recovery_details,
        show_json=show_json,
    )
    
    _vprint(verbose, "=== report ===")
    _vprint(verbose, f"run_summary_path: {run_summary_path}")
    _vprint(verbose)
    
    _write_planner_debug_artifacts(
        run_dir,
        planner_raw_output=planner_raw_output,
        plan_to_write=run_plan,
    )
    
    hashes = compute_run_hashes(run_dir)
    write_hash_manifest(run_dir, hashes)
    
    verification_result = verify_run_hashes(run_dir)
    verification_summary = format_verification_result(verification_result)
    
    _vprint(verbose, "=== verification ===")
    _vprint(verbose, verification_summary)
    _vprint(verbose)

    return AgentRunResult(
        prompt=prompt,
        plan=run_plan,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        verification_ok=verification_result.ok,
        verification_summary=verification_summary,
        planner_backend=planner_backend,
        planner_context=planner_context,
        planner_raw_output=planner_raw_output,
        unsupported_request=False,
        unsupported_reason=None,
        recovery_used=recovery_used,
        recovery_details=recovery_details,
    )


def _handle_replot_plan(
    *,
    prompt: str,
    plan_obj: dict[str, Any],
    planner_backend: str,
    planner_context: str,
    planner_raw_output: str | None,
    project_root: Path,
    recovery_used: bool,
    recovery_details: dict[str, Any] | None,
    verbose: bool,
) -> AgentRunResult:
    from runner.replot_run import replot_from_plan
    from runner.validate_plan import validate_replot_plan

    _vprint(verbose, "=== resolved replot plan ===")
    _vprint(verbose, json.dumps(plan_obj, indent=2))
    _vprint(verbose)

    validate_replot_plan(plan_obj)

    _vprint(verbose, "=== validation ===")
    _vprint(verbose, "Replot plan validation passed")
    _vprint(verbose)

    replot_dirs = replot_from_plan(plan_obj, project_root)

    _vprint(verbose, "=== replot execution ===")
    _vprint(verbose, f"replot_dirs: {replot_dirs}")
    _vprint(verbose)

    if not replot_dirs:
        return AgentRunResult(
            prompt=prompt,
            plan=plan_obj,
            run_dir=None,
            run_summary_path=None,
            verification_ok=False,
            verification_summary="Replot did not produce any output directories.",
            planner_backend=planner_backend,
            planner_context=planner_context,
            planner_raw_output=planner_raw_output,
            unsupported_request=False,
            unsupported_reason=None,
            recovery_used=recovery_used,
            recovery_details=recovery_details,
        )

    return AgentRunResult(
        prompt=prompt,
        plan=plan_obj,
        run_dir=replot_dirs[0],
        run_summary_path=None,
        verification_ok=True,
        verification_summary="Replot completed.",
        planner_backend=planner_backend,
        planner_context=planner_context,
        planner_raw_output=planner_raw_output,
        unsupported_request=False,
        unsupported_reason=None,
        recovery_used=recovery_used,
        recovery_details=recovery_details,
    )


def ask_agent(
    prompt: str,
    project_root: Path | str,
    *,
    planner_backend: str = "auto",
    planner_file: str = "planner/demo_gallery.json",
    planner_config: dict[str, Any] | None = None,
    show_json: bool = False,
    verbose: bool = False,
) -> AgentRunResult:
    project_root = Path(project_root)
    planner_config = planner_config or {}

    _vprint(verbose, "=== ask_agent: prompt ===")
    _vprint(verbose, prompt)
    _vprint(verbose)

    _vprint(verbose, "=== planner configuration ===")
    _vprint(verbose, f"planner_backend: {planner_backend}")
    _vprint(verbose, f"planner_file: {planner_file}")
    _vprint(verbose, f"planner_config: {planner_config}")
    _vprint(verbose)

    recovery_used = False
    recovery_details: dict[str, Any] | None = None

    # Deterministic routing hint for likely conversational continuation prompts
    if planner_backend in {"auto", "llm"} and _latest_run_exists(project_root) and _is_likely_continuation_prompt(prompt):
        recovery_used = True
        _vprint(verbose, "=== routing layer ===")
        _vprint(verbose, "Likely continuation prompt detected. Bypassing first-pass planner and using context recovery.")
        _vprint(verbose)

        try:
            recovered_run_dir, prior_run_json_text = _load_latest_run_context(project_root)
            prior_job_json_text = _select_prior_job_json(recovered_run_dir)
        except RunResolutionError as e:
            raise RuntimeError(f"Recovery failed while resolving prior run context: {e}") from e

        recovery_details = {
            "routing_reason": "continuation_prompt_bias",
            "recovered_run_dir": str(recovered_run_dir),
            "prior_job_context_used": prior_job_json_text is not None,
        }

        planner_result = generate_plan_from_context(
            user_prompt=prompt,
            project_root=project_root,
            prior_run_json_text=prior_run_json_text,
            prior_job_json_text=prior_job_json_text,
            planner_config=planner_config,
        )
    else:
        planner_result = generate_plan_from_prompt(
            prompt=prompt,
            project_root=project_root,
            planner_backend=planner_backend,
            planner_file=planner_file,
            planner_config=planner_config,
        )

    _vprint(verbose, "=== planner result summary ===")
    _vprint(verbose, f"planner_backend: {planner_result.planner_backend}")
    _vprint(verbose, f"planner_context: {planner_result.planner_context}")
    _vprint(verbose)

    if planner_result.raw_output is not None:
        _vprint(verbose, "=== planner raw output ===")
        _vprint(verbose, planner_result.raw_output)
        _vprint(verbose)

    _vprint(verbose, "=== parsed planner plan ===")
    _vprint(verbose, json.dumps(planner_result.plan, indent=2))
    _vprint(verbose)

    plan_obj = planner_result.plan

    if _is_recovery_sentinel(plan_obj):
        recovery_used = True

        _vprint(verbose, "=== recovery sentinel detected ===")
        _vprint(verbose, "Planner requested previous-run context for a second planning pass.")
        _vprint(verbose)

        try:
            recovered_run_dir, prior_run_json_text = _load_latest_run_context(project_root)
            prior_job_json_text = _select_prior_job_json(recovered_run_dir)
        except RunResolutionError as e:
            raise RuntimeError(f"Recovery failed while resolving prior run context: {e}") from e

        recovery_details = {
            "routing_reason": "planner_recovery_sentinel",
            "initial_plan": plan_obj,
            "recovered_run_dir": str(recovered_run_dir),
            "prior_job_context_used": prior_job_json_text is not None,
        }

        recovery_result = generate_plan_from_context(
            user_prompt=prompt,
            project_root=project_root,
            prior_run_json_text=prior_run_json_text,
            prior_job_json_text=prior_job_json_text,
            planner_config=planner_config,
        )

        _vprint(verbose, "=== recovery planner raw output ===")
        if recovery_result.raw_output is not None:
            _vprint(verbose, recovery_result.raw_output)
            _vprint(verbose)

        _vprint(verbose, "=== recovered planner plan ===")
        _vprint(verbose, json.dumps(recovery_result.plan, indent=2))
        _vprint(verbose)

        _vprint(verbose, "=== recovery traceability ===")
        _vprint(verbose, f"recovery_used: {recovery_used}")
        _vprint(verbose, json.dumps(recovery_details, indent=2))
        _vprint(verbose)

        planner_result = recovery_result
        plan_obj = planner_result.plan

    if plan_obj.get("unsupported_request") is True:
        return _handle_unsupported_plan(
            prompt=prompt,
            plan_obj=plan_obj,
            planner_backend=planner_result.planner_backend,
            planner_context=planner_result.planner_context,
            planner_raw_output=planner_result.raw_output,
            recovery_used=recovery_used,
            recovery_details=recovery_details,
            verbose=verbose,
        )

    if plan_obj.get("mode") == "replot":
        return _handle_replot_plan(
            prompt=prompt,
            plan_obj=plan_obj,
            planner_backend=planner_result.planner_backend,
            planner_context=planner_result.planner_context,
            planner_raw_output=planner_result.raw_output,
            project_root=project_root,
            recovery_used=recovery_used,
            recovery_details=recovery_details,
            verbose=verbose,
        )

    return _handle_execution_plan(
        prompt=prompt,
        plan_obj=plan_obj,
        planner_backend=planner_result.planner_backend,
        planner_context=planner_result.planner_context,
        planner_raw_output=planner_result.raw_output,
        project_root=project_root,
        show_json=show_json,
        recovery_used=recovery_used,
        recovery_details=recovery_details,
        verbose=verbose,
    )