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
            "entity_group": "string | null",
            "entity": "string | null",
            "sensor": "string | null",
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
| entity_group    | Depends   | Required for fleet-level views                  |
| entity          | Depends   | Required for single-entity views                |
| sensor          | Depends   | Required for sensor-based views                 |
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

All parameters are optional.

| Parameter   | Type     | Default | Description                           |
|-------------|----------|---------|---------------------------------------|
| show_raw    | bool     | false   | Show raw scatter points               |
| show_ewma   | bool     | true    | Show EWMA line                        |
| show_limits | bool     | true    | Show SPC limits                       |
| legend      | bool     | true    | Show legend                           |
| window_days | int      | null    | Slice last N days                     |
| x_min       | datetime | null    | Override x-axis lower bound           |
| x_max       | datetime | null    | Override x-axis upper bound           |
| y_min       | float    | null    | Override y-axis lower bound           |
| y_max       | float    | null    | Override y-axis upper bound           |
| entities    | list     | [all]   | Entity subset on fleet charts         |

Notes:
- Violations are shown only if show_limits=true.
- Limits are drawn using the latest non-null limit values.
	
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
| window_days | int      | null    | Slice last N days                     |
| start_ts    | datetime | null    | Explicit start bound                  |
| end_ts      | datetime | null    | Explicit end bound                    |
| entities    | list     | [all]   | Entity subset on fleet charts         |

Tables must write a CSV artifact.

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