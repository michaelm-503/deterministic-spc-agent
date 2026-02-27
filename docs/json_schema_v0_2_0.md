# Deterministic SPC Agent -- JSON Schema (v0.2.0)

## Overview

The Deterministic SPC Agent operates from a structured JSON execution
plan.

The LLM acts as a planner and produces structured JSON only. The backend executes deterministic SQL, preprocessing, and rendering
logic.

Defaults are handled internally by the backend. The LLM should only provide parameters when overriding defaults.

------------------------------------------------------------------------

# 1️⃣ Standard Execution Mode

``` json
{
  "runs": [
    {
      "run_id": "string",
      "request_text": "string",
      "jobs": [
        {
          "job_id": "string",
          "sql_template": "string",
          "preprocess": "string",
          "filters": {
            "entity_group": "string",
            "entity": "string | null",
            "sensor": "string",
            "start_ts": "ISO-8601 datetime | null",
            "end_ts": "ISO-8601 datetime | null"
          },
          "params": {
            "...": "preprocess-level overrides (optional)"
          },
          "outputs": {
            "plots": [
              {
                "plot": "string",
                "plot_name": "string",
                "params": {
                  "...": "plot-level overrides (optional)"
                }
              }
            ],
            "tables": [
              {
                "table": "string",
                "table_name": "string",
                "params": {
                  "...": "table-level overrides (optional)"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

------------------------------------------------------------------------

## Field Definitions

### Top-Level

The root JSON object is a **plan library**. It must contain a single key `runs`: an array of **run plans**

Each **run plan** contains one or more **jobs**, and each job contains one or more output specs (plots and/or tables).

Note: The pipeline executes one run plan at a time (one element of runs).

| Field           | Required  | Description                                     |
|-----------------|-----------|-------------------------------------------------|
| runs            | ✅        | List of independent run objects                 |

------------------------------------------------------------------------

### Run Object

| Field           | Required  | Description                                     |
|-----------------|-----------|-------------------------------------------------|
| run_id          | ✅        | Unique identifier for the run                   |
| request_text    | ✅        | Natural language prompt that generated this plan|
| jobs            | ✅        | List of jobs executed under this run            |

------------------------------------------------------------------------

### Job Object

| Field           | Required  | Description                                     |
|-----------------|-----------|-------------------------------------------------|
| job_id          | ✅        | Unique identifier within run                    |
| sql_template    | ✅        | Key into SQL_REGISTRY                           |
| preprocess      | ✅        | Key into PREPROCESS_REGISTRY                    |
| filters         | ✅        | Data selection parameters                       |
| params          | ❌        | Preprocess-level overrides (e.g., ewma_alpha)   |
| outputs         | ❌        | Output specifications (plots and/or tables)     |

------------------------------------------------------------------------

### Filters Object

| Field           | Required  | Description                                     |
|-----------------|-----------|-------------------------------------------------|
| entity_group    | ✅         | Required for fleet-level views                  |
| entity          | Depends   | Required for single-entity views                |
| sensor          | ✅         | Required for sensor-based views                 |
| start_ts        | ❌        | ISO datetime; SQL-level filter (optional)       |
| end_ts          | ❌        | ISO datetime; SQL-level filter (optional)       |

Note: Some plot types require specific filters (e.g., spc_time_series requires entity).

------------------------------------------------------------------------

### Outputs

Outputs are optional. If omitted, the job executes but produces no artifacts.

------------------------------------------------------------------------

## Plot Specification

``` json
{
  "plot": "spc_time_series",
  "plot_name": "example.png",
  "params": {}
}
```

### Supported Plot-Level Parameters

All parameters are optional and will default to settings below, as indicated by chart type.

| Parameter   | Type     | Description                           | Entity Time Trend | Fleet Time Trend | Boxplot |
|-------------|----------|---------------------------------------|-------------------|------------------|---------|
| show_raw    | bool     | Show raw scatter points               | true              | false            | n/a     |
| show_ewma   | bool     | Show EWMA line                        | true              | true             | false   |
| show_limits | bool     | Show SPC limits                       | true              | true             | true    |
| legend      | bool     | Show legend                           | true              | true             | false   |
| window_days | int      | Slice last N days of dataset          | null              | null             | null    |
| x_min       | datetime | Override x-axis lower bound           | null              | null             | n/a     |
| x_max       | datetime | Override x-axis upper bound           | null              | null             | n/a     |
| y_min       | float    | Override y-axis lower bound           | null              | null             | null    |
| y_max       | float    | Override y-axis upper bound           | null              | null             | null    |
| entities    | list     | Entity subset on fleet charts         | n/a               | [ *all* ]        | [ *all* ] |

Notes:
- Violations are shown only if show_limits=true.
- Limits are drawn using the latest non-null limit values.
- Violations are computed from raw values vs. limits (null-safe).
- `window_days` and `entities` are applied after SQL + preprocessing and before each plot call
- `x_min`/`x_max` is applied to plot axis.
	
## Table Specification

``` json
{
  "table": "fleet_ooc_summary",
  "table_name": "summary.csv",
  "params": {}
}
```

### Supported Table-Level Parameters

| Parameter   | Type     | Default | Description                           |
|-------------|----------|---------|---------------------------------------|
| window_days | int      | null    | Slice last N days of dataset          |
| start_ts    | datetime | null    | Explicit start bound                  |
| end_ts      | datetime | null    | Explicit end bound                    |
| entities    | list     | [all]   | Entity subset on fleet charts         |

Notes:
- Tables must write a CSV artifact.
- Time slicing and `entities` are applied after SQL + preprocessing and before each table call.
- Precedence: if `start_ts` or `end_ts` is provided, those bounds are applied; otherwise `window_days` is applied (if present).


------------------------------------------------------------------------

# 2️⃣ Replot Mode

Replot mode regenerates plots/tables from existing `processed_data.csv` without executing SQL.

``` json
{
  "mode": "replot",
  "run_dir": "runs/2024-01-15T12-05-11",
  "jobs": [
    {
      "job_id": "CPR11_temperature_motor",
      "outputs": {
        "plots": [
          {
            "plot": "spc_time_series",
            "plot_name": "zoom.png",
            "params": {
              "legend": false,
              "x_min": "2024-01-12T00:00:00",
              "x_max": "2024-01-15T00:00:00"
            }
          }
        ]
      }
    }
  ]
}
```
Replot mode:
- Does not access SQL
- Loads existing artifacts
- Applies deterministic rendering only
- Writes results to replots/<timestamp>/

------------------------------------------------------------------------

# 3️⃣ Execution Rules

1.  SQL is executed once per job.
2.  Preprocessing is executed once per job.
3.  Multiple plots/tables reuse the same processed dataset.
4.  Filename collisions are resolved automatically.
5.  Defaults are defined in code --- not in JSON.
6.  The LLM must only output overrides when necessary.

------------------------------------------------------------------------

# 4️⃣ Registry Contract

Valid keys must exist in:
- `SQL_REGISTRY`
- `PREPROCESS_REGISTRY`
- `PLOT_REGISTRY`
- `TABLE_REGISTRY`

Invalid keys result in execution error.

------------------------------------------------------------------------

# 5️⃣ Determinism Guarantees

-   No dynamic randomness in plotting
-   No implicit date usage
-   All transformations are pure functions of extracted data
-   Every run writes a plan artifact for reproducibility

------------------------------------------------------------------------

# 6️⃣ Minimal Valid Example

``` json
{
  "runs": [
    {
      "run_id": "example",
      "request_text": "Show vibration trend for CNC01",
      "jobs": [
        {
          "job_id": "cnc01_vibration",
          "sql_template": "entity_sensor_history",
          "preprocess": "ewma_spc",
          "filters": {
            "entity_group": "CNC",
            "entity": "CNC01",
            "sensor": "vibration_rms",
            "start_ts": null,
            "end_ts": null
          },
          "outputs": {
            "plots": [
              {
                "plot": "spc_time_series",
                "plot_name": "cnc01_vibration.png"
              }
            ]
          }
        }
      ]
    }
  ]
}
```
# 7️⃣ Schema Stability

This schema defines the contract for v0.2.0.

Future versions may introduce:
- Schema validation via Pydantic
- Typed parameter validation
- Versioned schema metadata


------------------------------------------------------------------------