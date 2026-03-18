from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import pandas as pd


@dataclass(frozen=True)
class ReportArtifacts:
    plot_paths: list[Path]
    table_paths: list[Path]


def _rel(base: Path, target: Path) -> str:
    try:
        return target.relative_to(base).as_posix()
    except ValueError:
        return target.as_posix()


def _collect_declared_plot_paths(run_dir: Path, plan: dict) -> list[Path]:
    paths: list[Path] = []
    for job in plan.get("jobs", []):
        job_id = job.get("job_id")
        if not job_id:
            continue
        job_dir = run_dir / job_id
        for plot_spec in job.get("outputs", {}).get("plots", []):
            plot_name = plot_spec.get("plot_name")
            if plot_name:
                p = job_dir / plot_name
                if p.exists():
                    paths.append(p)
    return sorted(paths)


def _collect_declared_table_paths(run_dir: Path, plan: dict) -> list[Path]:
    paths: list[Path] = []
    for job in plan.get("jobs", []):
        job_id = job.get("job_id")
        if not job_id:
            continue
        job_dir = run_dir / job_id
        for table_spec in job.get("outputs", {}).get("tables", []):
            table_name = table_spec.get("table_name")
            if table_name:
                p = job_dir / table_name
                if p.exists():
                    paths.append(p)
    return sorted(paths)


def _render_table_markdown(csv_path: Path) -> str:
    df = pd.read_csv(csv_path)
    if df.empty:
        return "_Empty table_"
    return df.to_markdown(index=False)


def build_run_summary_markdown(
    *,
    prompt: str,
    plan: dict,
    run_dir: Path,
    verification_summary: str,
    planner_source: str | None = None,
    matched_request_text: str | None = None,
    recovery_used: bool = False,
    recovery_details: dict[str, Any] | None = None,
    show_json: bool = False,
) -> str:
    run_dir = Path(run_dir)

    plot_paths = _collect_declared_plot_paths(run_dir, plan)
    table_paths = _collect_declared_table_paths(run_dir, plan)

    lines: List[str] = []
    lines.append("# Run Summary")
    lines.append("")

    lines.append("## Prompt")
    lines.append("")
    lines.append(prompt)
    lines.append("")

    if matched_request_text and matched_request_text != prompt:
        lines.append("## Matched Supported Prompt")
        lines.append("")
        lines.append(matched_request_text)
        lines.append("")

    if planner_source:
        lines.append("## Planner Source")
        lines.append("")
        lines.append(f"`{planner_source}`")
        lines.append("")

    if recovery_used:
        lines.append("## Recovery")
        lines.append("")
        lines.append("A second planning pass was required using context from the previous run.")
        if recovery_details and recovery_details.get("routing_reason"):
            lines.append(f"- Routing reason: `{recovery_details['routing_reason']}`")
        if recovery_details and recovery_details.get("recovered_run_dir"):
            lines.append(f"- Prior run used for recovery: `{recovery_details['recovered_run_dir']}`")
        if recovery_details and "prior_job_context_used" in recovery_details:
            lines.append(f"- Prior job context used: `{recovery_details['prior_job_context_used']}`")
        lines.append("")

    lines.append("## Run Directory")
    lines.append("")
    lines.append(f"`{run_dir}`")
    lines.append("")

    lines.append("## Verification")
    lines.append("")
    lines.append("```")
    lines.append(verification_summary.strip())
    lines.append("```")
    lines.append("")

    if show_json:
        lines.append("## Executed Plan")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(plan, indent=2))
        lines.append("```")
        lines.append("")

    lines.append("## Plots")
    lines.append("")
    if plot_paths:
        for p in plot_paths:
            rel = _rel(run_dir, p)
            lines.append(f"### `{rel}`")
            lines.append("")
            lines.append(f"Direct path: `{p}`")
            lines.append("")
            lines.append(f"![{rel}]({rel})")
            lines.append("")
    else:
        lines.append("_No declared plot artifacts found._")
        lines.append("")

    lines.append("## Output Tables")
    lines.append("")
    if table_paths:
        for p in table_paths:
            rel = _rel(run_dir, p)
            lines.append(f"### `{rel}`")
            lines.append("")
            lines.append(f"Direct path: `{p}`")
            lines.append("")
            try:
                lines.append(_render_table_markdown(p))
            except Exception as e:
                lines.append(f"_Failed to render table: {e}_")
            lines.append("")
    else:
        lines.append("_No declared output tables found._")
        lines.append("")

    return "\\n".join(lines)


def write_run_summary(
    *,
    prompt: str,
    plan: dict,
    run_dir: Path,
    verification_summary: str,
    planner_source: str | None = None,
    matched_request_text: str | None = None,
    recovery_used: bool = False,
    recovery_details: dict[str, Any] | None = None,
    filename: str = "run_summary.md",
    show_json: bool = False,
) -> Path:
    run_dir = Path(run_dir)
    md = build_run_summary_markdown(
        prompt=prompt,
        plan=plan,
        run_dir=run_dir,
        verification_summary=verification_summary,
        planner_source=planner_source,
        matched_request_text=matched_request_text,
        recovery_used=recovery_used,
        recovery_details=recovery_details,
        show_json=show_json,
    )
    out_path = run_dir / filename
    out_path.write_text(md)
    return out_path