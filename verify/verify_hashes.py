from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from verify.compute_hashes import compute_run_hashes


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    missing_files: List[str]
    extra_files: List[str]
    mismatched: Dict[str, Dict[str, str]]  # path -> {"expected":..., "actual":...}


@dataclass(frozen=True)
class RunVerificationResult:
    ok: bool
    base: VerificationResult
    replot_results: Dict[str, VerificationResult]  # replot_dir -> result


def load_hash_manifest(run_dir: Path, filename: str = "hashes.json") -> Dict[str, str]:
    run_dir = Path(run_dir)
    manifest_path = run_dir / filename
    if not manifest_path.exists():
        raise FileNotFoundError(f"hash manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text())


def _is_replot_path(rel_path: str) -> bool:
    # manifest keys are relative paths like "JOB/replots/<ts>/file.png"
    parts = Path(rel_path).parts
    return "replots" in parts


def verify_dir_hashes(
    dir_path: Path,
    *,
    manifest_filename: str = "hashes.json",
    ignore_replots: bool = False,
) -> VerificationResult:
    """
    Verify a single directory against its hashes.json.
    If ignore_replots=True, any files under */replots/** are excluded from actual scan
    and thus won't be flagged as extras.
    """
    expected = load_hash_manifest(dir_path, filename=manifest_filename)
    actual = compute_run_hashes(dir_path)

    if ignore_replots:
        actual = {k: v for k, v in actual.items() if not _is_replot_path(k)}
        expected = {k: v for k, v in expected.items() if not _is_replot_path(k)}

    expected_keys = set(expected.keys())
    actual_keys = set(actual.keys())

    missing = sorted(expected_keys - actual_keys)
    extra = sorted(actual_keys - expected_keys)

    mismatched: Dict[str, Dict[str, str]] = {}
    for k in sorted(expected_keys & actual_keys):
        if expected[k] != actual[k]:
            mismatched[k] = {"expected": expected[k], "actual": actual[k]}

    ok = (len(missing) == 0) and (len(extra) == 0) and (len(mismatched) == 0)
    return VerificationResult(ok=ok, missing_files=missing, extra_files=extra, mismatched=mismatched)


def verify_run_hashes(
    run_dir: Path,
    *,
    manifest_filename: str = "hashes.json",
    verify_replots: bool = True,
) -> RunVerificationResult:
    """
    Verify:
      1) base run_dir against run_dir/hashes.json, ignoring any replot folders
      2) (optional) each replot directory containing its own hashes.json

    Replots are expected at:
      runs/<ts>/<job_id>/replots/<replot_ts>/hashes.json
    """
    run_dir = Path(run_dir)

    # Base verification ignores replots so replot doesn't invalidate the base run
    base_result = verify_dir_hashes(
        run_dir,
        manifest_filename=manifest_filename,
        ignore_replots=True,
    )

    replot_results: Dict[str, VerificationResult] = {}

    if verify_replots:
        # Find all replot manifests under the run directory
        for manifest_path in run_dir.glob("**/replots/**/hashes.json"):
            replot_dir = manifest_path.parent
            # Verify replot dir strictly (no ignore) against its own manifest
            try:
                r = verify_dir_hashes(replot_dir, manifest_filename="hashes.json", ignore_replots=False)
            except Exception as e:
                # Treat exceptions as a failed verification with a readable “missing/mismatch”
                # (keeps output predictable)
                r = VerificationResult(
                    ok=False,
                    missing_files=[f"<error> {type(e).__name__}: {e}"],
                    extra_files=[],
                    mismatched={},
                )
            replot_results[str(replot_dir)] = r

    ok = base_result.ok and all(r.ok for r in replot_results.values())
    return RunVerificationResult(ok=ok, base=base_result, replot_results=replot_results)


def format_verification_result(result: RunVerificationResult) -> str:
    lines: List[str] = []

    if result.ok:
        lines.append("✅ All artifacts verified (base + replots).")
        return "\n".join(lines)

    lines.append("❌ Verification failed.")

    # ---- Base ----
    if not result.base.ok:
        lines.append("\nBase run verification failed:")
        lines.extend(_format_single_result(result.base))

    # ---- Replots ----
    if result.replot_results:
        bad = {k: v for k, v in result.replot_results.items() if not v.ok}
        if bad:
            lines.append("\nReplot verification failed:")
            for replot_dir, r in bad.items():
                lines.append(f"\n- Replot dir: {replot_dir}")
                lines.extend(["  " + s for s in _format_single_result(r)])

    return "\n".join(lines)


def _format_single_result(r: VerificationResult) -> List[str]:
    out: List[str] = []
    if r.missing_files:
        out.append("Missing files (in manifest, not on disk):")
        out.extend([f"  - {p}" for p in r.missing_files])

    if r.extra_files:
        out.append("Extra files (on disk, not in manifest):")
        out.extend([f"  - {p}" for p in r.extra_files])

    if r.mismatched:
        out.append("Mismatched hashes:")
        for p, d in r.mismatched.items():
            out.append(f"  - {p}")
            out.append(f"      expected: {d['expected']}")
            out.append(f"      actual:   {d['actual']}")
    return out