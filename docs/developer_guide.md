# Developer Guide

This document explains how the Deterministic SPC Agent works internally and how developers can extend or modify the system.

The system is organized around four major components:

- Planner architecture
- Execution engine
- Replot workflow
- Artifact model

---

# Planner Architecture

The planner converts natural-language requests into structured execution plans.

Importantly, the LLM **does not generate executable code**.  
It generates **JSON execution plans** constrained by a schema.

This architecture ensures that execution remains deterministic and auditable.

## Planner Pipeline

```
User prompt
   ↓
LLM planner
   ↓
Structured JSON plan
   ↓
Schema validation
   ↓
Execution engine
```

The planner lives in:

```
spc_agent/agent/
```

Key modules:

```
planner.py
planner_llm.py
planner_stub.py
planner_prompt.py
```

---

## planner.py

Primary entry point for planning.

Responsibilities:

- selecting planner backend
- loading planner configuration
- invoking the LLM or stub planner
- returning parsed execution plans

Main function:

```
generate_plan_from_prompt()
```

---

## planner_llm.py

Handles interaction with the LLM API.

Responsibilities:

- building the system prompt
- submitting the prompt to the LLM
- parsing the JSON response

LLM output must conform to the **planner schema**.

If the LLM returns invalid JSON, the plan is rejected.

---

## planner_prompt.py

Constructs the system prompt used by the LLM planner.

The prompt includes:

- available SQL templates
- available preprocessing modules
- available plot modules
- available table modules
- supported entity groups
- supported sensors

These values are loaded from the **planner catalog** generated during setup.

Catalog location:

```
planner/metadata/catalog.json
```

This prevents the LLM from inventing tools or sensors.

---

## Planner Schema

Execution plans must conform to the schema defined in:

```
docs/planner_schema.md
```

Validation is enforced by:

```
runner/validate_plan.py
```

Invalid plans are rejected before execution.

---

# Execution Engine

The execution engine performs deterministic analytics workflows.

It lives in:

```
runner/
```

Key modules:

```
run_one_run.py
validate_plan.py
```

---

## Execution Pipeline

Each job follows the same pipeline:

```
SQL extraction
→ preprocessing
→ output generation
→ artifact storage
```

Example job:

```
{
  "job_id": "arm_vibration_7d",
  "sql_template": "fleet_sensor_history",
  "preprocess": "ewma_spc",
  "filters": {
    "entity_group": "ARM",
    "sensor": "vibration_rms"
  },
  "outputs": {
    "plots": [
      {
        "plot": "fleet_time_trend"
      }
    ]
  }
}
```

---

## SQL Templates

SQL queries are defined as templates under:

```
sql/
```

The execution engine never accepts arbitrary SQL.

Instead, it selects from a fixed set of templates and injects filter parameters.

This prevents:

- SQL injection
- LLM-generated queries
- unsafe database access

---

## Preprocessing Modules

Preprocessing modules live under:

```
preprocess/
```

Example:

```
ewma_spc.py
```

Responsibilities may include:

- smoothing
- SPC limit calculation
- anomaly detection

Preprocessing operates on extracted datasets.

---

## Plot Modules

Plot modules live under:

```
plots/
```

Examples:

```
spc_time_series.py
fleet_time_trend.py
fleet_boxplot.py
```

Each module reads `processed_data.csv` and produces visualization artifacts.

---

## Table Modules

Summary tables live under:

```
tables/
```

Examples:

```
fleet_ooc_summary.py
```

These modules produce CSV outputs summarizing analytics results.

---

# Replot Workflow

The replot system allows modification of previous outputs without rerunning the full pipeline.

Replots reuse existing artifacts from a previous run.

Example prompt:

```
Remove the legend from the last plot.
```

---

## Replot Plan

Example replot plan:

```
{
  "mode": "replot",
  "run_ref": "latest",
  "jobs": [
    {
      "job_id": "arm_vibration_7d",
      "outputs": {
        "plots": [
          {
            "plot": "fleet_time_trend",
            "params": {
              "legend": false
            }
          }
        ]
      }
    }
  ]
}
```

---

## Replot Resolution

Replot execution performs the following steps:

```
Resolve run reference
→ locate job artifacts
→ load processed_data.csv
→ generate new outputs
→ write replot artifacts
```

Replots never rerun:

- SQL extraction
- preprocessing

---

## Run Lookup

Semantic references such as:

```
run_ref = "latest"
```

are resolved using:

```
runner/run_lookup.py
```

The lookup scans the `runs/` directory and selects the appropriate run.

---

# Artifact Model

Every execution produces a reproducible artifact directory.

Example:

```
runs/
  2026-03-15T18-22-44/

      run.json
      run_summary.md
      hash_manifest.json

      arm_vibration_7d/

          extracted_data.csv
          processed_data.csv
          arm_vibration_7d.png
```

---

## Artifact Types

Artifacts include:

### Execution Plan

```
run.json
```

Stores the exact execution plan.

---

### Extracted Data

```
extracted_data.csv
```

Raw SQL output.

---

### Processed Data

```
processed_data.csv
```

Result of preprocessing modules.

---

### Output Artifacts

Plots and tables generated by output modules.

Examples:

```
spc_plot.png
summary_table.csv
```

---

### Verification Manifest

```
hash_manifest.json
```

Stores hashes for all artifacts in the run directory.

Verification is performed by:

```
verify/verify_hashes.py
```

This ensures artifact integrity.

---

# Setup Pipeline

Before execution, the system must initialize two resources.

---

## Dataset Initialization

Script:

```
scripts/setup_data.py
```

Creates:

```
data/mfg.duckdb
```

from the included dataset.

---

## Planner Catalog

Script:

```
scripts/build_planner_catalog.py
```

Generates:

```
planner/metadata/catalog.json
```

This catalog defines the allow-lists used by the planner.

---

# Adding New Analytics Modules

Developers can extend the system by adding new modules.

---

## Adding a New Plot

1. Create module in:

```
plots/
```

2. Implement plotting function.

3. Register the plot name in the planner catalog.

---

## Adding a New Table

1. Create module in:

```
tables/
```

2. Implement summary logic.

3. Register in planner catalog.

---

## Adding a New SQL Template

1. Add SQL template under:

```
sql/
```

2. Register template in planner catalog.

---

# Design Philosophy

The architecture follows a strict separation:

```
LLM → reasoning only
Execution → deterministic modules
```

This design prevents AI systems from executing arbitrary code while still enabling natural-language interfaces for analytics.