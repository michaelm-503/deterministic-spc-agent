
from __future__ import annotations
from textwrap import dedent
from pathlib import Path

def build_planner_system_prompt(
    *,
    sql_keys: list[str],
    preprocess_keys: list[str],
    plot_keys: list[str],
    table_keys: list[str],
    entity_group_keys: list[str],
    entity_keys: list[str],
    sensor_keys: list[str],
    project_root: Path | str,
) -> str:

    schema_text = Path(project_root / "spc_agent/agent/planner_schema.txt").read_text()
    
    return dedent(
        f"""
You are a manufacturing analytics planner.

Your task:
- convert a user prompt into a deterministic execution plan
- output JSON only
- do not include prose or markdown
- use only allowed registry keys
- prefer defaults

Rules:
- Output JSON only
- do not write SQL
- do not write Python
- only include parameters when required
- use null for unspecified time bounds
- entity_group must be equal to entity.str[:3]
- use 2024-01-15 as the current date if relative time references are provided in the prompt

Allowed sql_template values:
{sql_keys}

Allowed preprocess values:
{preprocess_keys}

Allowed plot values:
{plot_keys}

Allowed table values:
{table_keys}

Named entities - entity_group:
{entity_group_keys}

Named entities - entity:
{entity_keys}

Named entities - sensor:
{sensor_keys}

Schema:
{schema_text}

"""
    ).strip()


def build_replot_repair_prompt(
    *,
    user_prompt: str,
    prior_run_json: str,
    project_root: Path | str,
) -> str:

    schema_text = Path(project_root / "spc_agent/agent/planner_schema.txt").read_text()
    
    return f"""
The user wants to modify a previous result.

User request:
{user_prompt}

Below is the JSON for the previous run:
{prior_run_json}

Generate a valid replot plan.

Rules:
- Output JSON only.
- mode must equal "replot".
- Reuse existing job_id values from the previous run JSON.
- Do not invent job_ids.
- Do not include sql_template.
- Do not include preprocess.
- Do not include filters.
- Only modify outputs.
- Add new outputs if requested.
- If a prior job does not need any changes, it may be omitted.
- Generate at least one visible output.
- If the run JSON includes _metadata.timestamp, use that timestamp to form run_dir.
- Never invent timestamps.
- use 2024-01-15 as the current date if relative time references are provided in the prompt

Schema:
{schema_text}

""".strip()