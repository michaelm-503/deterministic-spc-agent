from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e


def _project_root(explicit_root: str | None) -> Path:
    # If caller passes --project-root use it; else assume CLI is run from repo root.
    return Path(explicit_root).resolve() if explicit_root else Path.cwd().resolve()


def _is_plan_library(obj: dict[str, Any]) -> bool:
    return isinstance(obj.get("runs"), list)


def _resolve_run(plan_or_lib: dict[str, Any], run_index: int | None) -> dict[str, Any]:
    """
    Accepts either:
      - a plan library: {"runs":[...]}
      - a single run: {"run_id":..., "jobs":[...]}
    """
    if _is_plan_library(plan_or_lib):
        runs = plan_or_lib["runs"]
        if not runs:
            raise ValueError("Plan library has no runs: runs[] is empty")

        idx = 0 if run_index is None else run_index
        if idx < 0 or idx >= len(runs):
            raise IndexError(f"--run-index {idx} out of range (0..{len(runs)-1})")
        return runs[idx]

    # single run
    if run_index is not None:
        raise ValueError("Input JSON is a single run (no runs[]). Remove --run-index.")
    return plan_or_lib


def cmd_validate(args: argparse.Namespace) -> int:
    from runner.validate_plan import validate_plan_library, validate_run_plan

    root = _project_root(args.project_root)
    plan = _load_json(Path(args.plan_json))

    # Validate plan lib vs single run
    if _is_plan_library(plan):
        validate_plan_library(plan)
        print("✅ Plan library validation passed")
    else:
        validate_run_plan(plan)
        print("✅ Run plan validation passed")

    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from runner.validate_plan import validate_run_plan
    from runner.run_one_run import run_one_run

    root = _project_root(args.project_root)
    plan_or_lib = _load_json(Path(args.plan_json))
    run_plan = _resolve_run(plan_or_lib, args.run_index)

    # Validate one run before execution
    validate_run_plan(run_plan)

    run_dir = run_one_run(run_plan, root)
    print(f"✅ Run executed: {run_dir}")
    return 0


def cmd_replot(args: argparse.Namespace) -> int:
    """
    Replot can accept:
      - a single run plan (recommended)
      - or a plan library + --run-index (we'll replot just that run)
    """
    from runner.replot_run import replot_from_plan

    root = _project_root(args.project_root)
    plan_or_lib = _load_json(Path(args.plan_json))
    run_plan = _resolve_run(plan_or_lib, args.run_index)

    out = replot_from_plan(run_plan, root)

    # replot_from_plan may return Path or list[Path]; normalize for printing
    if isinstance(out, list):
        for p in out:
            print(f"✅ Replot created: {p}")
    else:
        print(f"✅ Replot created: {out}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spc_agent",
        description="Deterministic SPC Agent CLI (Phase 3)",
    )
    p.add_argument(
        "--project-root",
        default=None,
        help="Path to repo root (defaults to current working directory).",
    )

    sub = p.add_subparsers(dest="command", required=True)

    # validate
    pv = sub.add_parser("validate", help="Validate a plan library or a single run JSON.")
    pv.add_argument("plan_json", help="Path to plan JSON (library or single run).")
    pv.set_defaults(func=cmd_validate)

    # run
    pr = sub.add_parser("run", help="Execute one run from a plan library or a single run JSON.")
    pr.add_argument("plan_json", help="Path to plan JSON (library or single run).")
    pr.add_argument("--run-index", type=int, default=None, help="Index into runs[] when plan_json is a library.")
    pr.set_defaults(func=cmd_run)

    # replot
    pp = sub.add_parser("replot", help="Replot from an existing run plan JSON (no SQL/preprocess).")
    pp.add_argument("plan_json", help="Path to run JSON (or plan library).")
    pp.add_argument("--run-index", type=int, default=None, help="Index into runs[] when plan_json is a library.")
    pp.set_defaults(func=cmd_replot)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())