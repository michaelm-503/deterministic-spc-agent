from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _project_root(project_root: str | None) -> Path:
    return Path(project_root).resolve() if project_root else Path.cwd().resolve()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _is_plan_library(plan: dict) -> bool:
    return isinstance(plan.get("runs"), list)


def cmd_setup(args: argparse.Namespace) -> int:
    root = _project_root(args.project_root)

    subprocess.run(
        [sys.executable, "scripts/setup_data.py", "--project-root", str(root)],
        check=True,
        cwd=str(root),
    )
    subprocess.run(
        [sys.executable, "scripts/build_planner_catalog.py", "--project-root", str(root)],
        check=True,
        cwd=str(root),
    )

    print("✅ Setup complete")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from spc_agent.agent.agent_runner import ask_agent

    root = _project_root(args.project_root)
    planner_config = {
        "model": args.model,
        "temperature": args.temperature,
    }

    result = ask_agent(
        prompt=args.prompt,
        project_root=root,
        planner_backend=args.planner_backend,
        planner_file=args.planner_file,
        planner_config=planner_config,
        show_json=args.show_json,
        verbose=args.verbose,
    )

    if result.run_summary_path is not None:
        print(f"✅ Summary: {result.run_summary_path}")
    elif result.run_dir is not None:
        print(f"✅ Artifacts: {result.run_dir}")
    else:
        print(result.verification_summary)

    return 0 if result.verification_ok or result.unsupported_request else 2


def cmd_validate(args: argparse.Namespace) -> int:
    from runner.validate_plan import (
        validate_plan_library,
        validate_replot_plan,
        validate_run_plan,
    )

    plan = _load_json(Path(args.plan_json))

    if plan.get("mode") == "replot":
        validate_replot_plan(plan)
        print("✅ Replot plan validation passed")
    elif _is_plan_library(plan):
        validate_plan_library(plan)
        print("✅ Plan library validation passed")
    else:
        validate_run_plan(plan)
        print("✅ Run plan validation passed")

    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from runner.run_one_run import run_one_run

    root = _project_root(args.project_root)
    plan_or_lib = _load_json(Path(args.plan_json))

    if _is_plan_library(plan_or_lib):
        if args.run_index is None:
            raise ValueError("Plan library requires --run-index")
        run_plan = plan_or_lib["runs"][args.run_index]
    else:
        run_plan = plan_or_lib

    run_dir = run_one_run(run_plan, root, write_hashes=True)
    print(f"✅ Run executed: {run_dir}")
    return 0


def cmd_replot(args: argparse.Namespace) -> int:
    from runner.replot_run import replot_from_plan

    root = _project_root(args.project_root)
    plan_or_lib = _load_json(Path(args.plan_json))

    if _is_plan_library(plan_or_lib):
        if args.run_index is None:
            raise ValueError("Plan library requires --run-index")
        plan = plan_or_lib["runs"][args.run_index]
    else:
        plan = plan_or_lib

    out = replot_from_plan(plan, root, override_run_dir=args.run_dir)

    if isinstance(out, list):
        for p in out:
            print(f"✅ Replot created: {p}")
    else:
        print(f"✅ Replot created: {out}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from verify.verify_hashes import format_verification_result, verify_run_hashes

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    result = verify_run_hashes(run_dir)
    print(format_verification_result(result))
    return 0 if result.ok else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spc_agent",
        description="Deterministic SPC Agent CLI",
    )
    p.add_argument(
        "--project-root",
        default=None,
        help="Path to repo root (defaults to current working directory).",
    )

    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("setup", help="Initialize DuckDB and planner catalog.")
    ps.set_defaults(func=cmd_setup)

    pa = sub.add_parser("ask", help="Run the natural-language planner/executor flow.")
    pa.add_argument("prompt", help="Natural-language request.")
    pa.add_argument("--planner-backend", default="auto", choices=["auto", "llm", "curated"])
    pa.add_argument("--planner-file", default="planner/demo_gallery.json")
    pa.add_argument("--model", default="gpt-4.1")
    pa.add_argument("--temperature", type=float, default=0.0)
    pa.add_argument("--show-json", action="store_true")
    pa.add_argument("--verbose", action="store_true")
    pa.set_defaults(func=cmd_ask)

    pv = sub.add_parser("validate", help="Validate a plan library, run plan, or replot plan.")
    pv.add_argument("plan_json", help="Path to plan JSON.")
    pv.set_defaults(func=cmd_validate)

    pr = sub.add_parser("run", help="Execute one run from a plan library or a single run JSON.")
    pr.add_argument("plan_json", help="Path to plan JSON (library or single run).")
    pr.add_argument("--run-index", type=int, default=None, help="Index into runs[] when plan_json is a library.")
    pr.set_defaults(func=cmd_run)

    pp = sub.add_parser("replot", help="Replot from an existing run plan JSON (no SQL/preprocess).")
    pp.add_argument("plan_json", help="Path to replot JSON.")
    pp.add_argument("--run-index", type=int, default=None, help="Index into runs[] when plan_json is a library.")
    pp.add_argument("--run-dir", default=None, help="Override run_dir from the JSON.")
    pp.set_defaults(func=cmd_replot)

    pf = sub.add_parser("verify", help="Verify artifacts from a run directory.")
    pf.add_argument("run_dir", help="Path to run directory.")
    pf.set_defaults(func=cmd_verify)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())