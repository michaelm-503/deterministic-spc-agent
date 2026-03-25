"""
tests/smoke_test.py

Minimal smoke test for Deterministic SPC Agent (Phase 2).

What it checks:
- demo_gallery.json loads
- plan library validates (light validation)
- one run executes end-to-end test of the backend (JSON in, plots out)
- expected artifacts exist per job:
    extracted_data.csv
    processed_data.csv
    job.json
    at least one .png if outputs.plots exists

Run:
  python tests/smoke_test.py

Optional:
  RUN_INDEX=0 python tests/smoke_test.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import duckdb

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from runner.run_one_run import run_one_run
from runner.validate_plan import validate_plan_library


def _assert_exists(path: Path, msg: str):
    if not path.exists():
        raise AssertionError(f"{msg}: expected to exist -> {path}")


def _assert_any_glob(dir_path: Path, pattern: str, msg: str):
    matches = list(dir_path.glob(pattern))
    if not matches:
        raise AssertionError(f"{msg}: expected at least one match for '{pattern}' in {dir_path}")
    return matches


def main():
    project_root = Path(__file__).resolve().parents[1]

    plan_path = project_root / "planner" / "demo_gallery.json"
    _assert_exists(plan_path, "Missing plan library file")

    plan_lib = json.loads(plan_path.read_text())

    # 1) Validate plan library (light validation)
    validate_plan_library(plan_lib)
    print("✅ Plan library validation passed")

    runs = plan_lib.get("runs", [])
    if not isinstance(runs, list) or len(runs) == 0:
        raise AssertionError("demo_gallery.json must contain a non-empty 'runs' list")

    run_index = int(os.environ.get("RUN_INDEX", "0"))
    if run_index < 0 or run_index >= len(runs):
        raise AssertionError(f"RUN_INDEX out of range: {run_index}. runs available: {len(runs)}")

    run_plan = runs[run_index]
    print(f"▶ Running smoke test: run_index={run_index}, run_id={run_plan.get('run_id')}")

    # 2) Check for duckdb
    FIXTURES = project_root / "tests" / "fixtures"
    tmp_db = project_root / "tests" / "_tmp_mfg.duckdb"
    
    # (re)create
    if tmp_db.exists():
        tmp_db.unlink()
    
    con = duckdb.connect(str(tmp_db))
    
    con.execute("""
    CREATE TABLE sensor_data AS
    SELECT * FROM read_csv_auto(?, header=true);
    """, [str(FIXTURES / "sensor_long_min.csv")])
    
    con.execute("""
    CREATE TABLE sensor_spc_limits AS
    SELECT * FROM read_csv_auto(?, header=true);
    """, [str(FIXTURES / "spc_limits_min.csv")])
    
    con.close()
    
    os.environ["SPC_AGENT_DUCKDB_PATH"] = str(tmp_db)

    # 3) Execute one run
    run_dir = run_one_run(run_plan, project_root, write_hashes=True)
    _assert_exists(run_dir, "run_one_run returned run_dir that does not exist")
    _assert_exists(run_dir / "hashes.json", "Missing hashes.json")
    
    print(f"✅ Run executed. run_dir={run_dir}")

    # 4) Artifact checks (per job)
    jobs = run_plan.get("jobs", [])
    if not isinstance(jobs, list) or len(jobs) == 0:
        raise AssertionError("Run must contain a non-empty 'jobs' list")

    for job in jobs:
        job_id = job.get("job_id")
        if not job_id:
            raise AssertionError("Each job must have a non-empty job_id")

        job_dir = run_dir / job_id
        _assert_exists(job_dir, f"Missing job directory for job_id={job_id}")

        _assert_exists(job_dir / "job.json", f"Missing job.json for job_id={job_id}")
        _assert_exists(job_dir / "extracted_data.csv", f"Missing extracted_data.csv for job_id={job_id}")
        _assert_exists(job_dir / "processed_data.csv", f"Missing processed_data.csv for job_id={job_id}")

        outputs = job.get("outputs", {}) or {}
        plots = outputs.get("plots", []) or []
        if plots:
            # if plots are requested, ensure at least one PNG exists in the job folder
            _assert_any_glob(job_dir, "*.png", f"Missing plot PNG(s) for job_id={job_id}")

        tables = outputs.get("tables", []) or []
        if tables:
            # if tables are requested, ensure at least one CSV exists in the job folder
            _assert_any_glob(job_dir, "*.csv", f"Missing table CSV(s) for job_id={job_id}")

        print(f"✅ Artifacts OK for job_id={job_id}")

    print("🎉 Smoke test passed")


if __name__ == "__main__":
    main()