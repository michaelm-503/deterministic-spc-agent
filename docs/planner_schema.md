
# Deterministic SPC Agent
## Planner Schema

The planner schema defines the structure of valid JSON plans used by the Deterministic SPC Agent.

Planners generate structured plans that conform to this schema.  
Plans are validated before execution.

---

# 1. Plan Types

| Plan Type | Description |
|---|---|
| Execution Plan | Executes SQL extraction, preprocessing, and output generation |
| Replot Plan | Generates new outputs from existing processed artifacts |
| Unsupported Response | Safe exit when a request cannot be resolved |

---

# 2. Plan Library

A plan library contains multiple runs.

Example:

```json
{
  "runs": [
    { "...": "..." },
    { "...": "..." }
  ]
}
```

Plan libraries are commonly used for:

- curated demo prompts
- test fixtures
- plan validation

For `ask_agent()`, the planner is expected to resolve to a single run unless multiple runs are explicitly required.

---

# 3. Execution Run Plan

Each execution run defines one batch of jobs.

Example:

```json
{
  "run_id": "example_run",
  "request_text": "Show vibration trend for CNC01",
  "jobs": [ ... ]
}
```
-
### Required run-level fields

| Field | Required | Description |
|---|---|---|
| run_id | ✅ | Short snake_case summary of the run |
| request_text | ✅ | Original user request or matched curated prompt |
| jobs | ✅ | Non-empty list of jobs |

---

# 4. Job Structure

Each job defines one deterministic analytics workflow.

A job includes:

- one SQL template
- one preprocess step
- filters
- optional preprocess parameters
- one or more visible outputs

Example:

```json
{
  "job_id": "CPR11_temperature_motor",
  "sql_template": "entity_sensor_history",
  "preprocess": "ewma_spc",
  "filters": { "...": "..." },
  "params": { "...": "..." },
  "outputs": { "...": "..." }
}
```
-
### Required job-level fields

| Field | Required | Description |
|---|---|---|
| job_id | ✅ | Short snake_case job identifier |
| sql_template | ✅ | Registered SQL template key |
| preprocess | ✅ | Registered preprocess key |
| filters | ✅ | Job-level extraction filters |
| outputs | ✅ | Visible outputs to generate |

-

### Output requirement

Each execution job must produce **at least one visible output**:

- one or more plots
- or one or more tables

Jobs with no visible outputs are invalid.

---

# 5. SQL Template

SQL templates define how data is extracted.

Only registered templates may execute.

Templates are stored under:

```text
sql/
```

Example:

```text
entity_sensor_history
```
-

### Filters

Filters control SQL-level extraction.

| Field | Required | Description |
|---|---|---|
| entity_group | ✅ | Required for all jobs |
| entity | Depends | Required for single-entity views; null for fleet-level workflows |
| sensor | ✅ | Required for sensor-based views |
| start_ts | ❌ | Optional SQL-level lower bound |
| end_ts | ❌ | Optional SQL-level upper bound |

##### Notes

- Some plots require specific filters. For example, `spc_time_series` requires a single `entity`.
- `start_ts` and `end_ts` are SQL-level extraction filters, not plot-level zoom controls.
- `entity_group` must be consistent with `entity` when `entity` is specified.

---

# 6. Preprocess

Preprocess modules apply deterministic transformations to extracted data.

Only registered preprocess modules may execute.

Examples:

- EWMA smoothing
- SPC violation detection

Job-level parameters typically apply to preprocess behavior.

-

### Job-Level Params

Job-level params affect preprocessing only.

Supported job-level parameters:

| Field | Required | Description |
|---|---|---|
| ewma_alpha | ❌ | EWMA alpha parameter. Default = 0.2 |

Params is optional if no parameter overrides are needed.

---

# 7. Outputs

Outputs define plots and summary tables.

Only registered output modules may execute.

Output objects may include optional per-output parameters.

-

### Parameter Hierarchy

Parameters may appear at two levels:

| Level | Applies To |
|---|---|
| Job-level params | Preprocessing behavior |
| Output-level params | Plot or table behavior |

Output-level params do **not** change preprocessing.

---

# 7.1 Plot Specification

Example:

```json
{
  "outputs": {
    "plots": [
      {
        "plot": "spc_time_series",
        "plot_name": "plot.png",
        "params": {}
      }
    ]
  }
}
```
-
### Plot-level fields

| Field | Required | Description |
|---|---|---|
| plot | ✅ | Registered plot key |
| plot_name | ✅ | Output filename |
| params | ❌ | Plot-level params |

-
### Supported plot-level parameters

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


##### Notes

- Violations are shown only if show_limits=true.
- Limits are drawn using the latest non-null limit values.
- Violations are computed from raw values vs. limits (null-safe).
- `window_days` and `entities` are applied after SQL + preprocessing and before each plot call
- `x_min`/`x_max` is applied to plot axis and do not affect data slicing.
- Params is optional if no parameter overrides are needed.

---

# 7.2 Table Specification

Example:

```json
{
  "outputs": {
    "tables": [
      {
        "table": "fleet_ooc_summary",
        "table_name": "summary.csv",
        "params": {}
      }
    ]
  }
}
```

-
### Table-level fields

| Field | Required | Description |
|---|---|---|
| table | ✅ | Registered table key |
| table_name | ✅ | Output filename |
| params | ❌ | Table-level params |

-
### Supported table-level parameters

| Parameter   | Type     | Default | Description                           |
|-------------|----------|---------|---------------------------------------|
| window_days | int      | null    | Slice last N days of dataset          |
| start_ts    | datetime | null    | Explicit start bound                  |
| end_ts      | datetime | null    | Explicit end bound                    |
| entities    | list     | [all]   | Entity subset on fleet charts         |

##### Table notes

- Tables must write a CSV artifact.
- Time slicing and `entities` are applied after SQL + preprocessing and before each table call.
- Precedence: if `start_ts` or `end_ts` is provided, those bounds are applied; otherwise `window_days` is applied (if present).
- `start_ts` or `end_ts` flags passed as a table parameter will only affect the associated table. These flags do not apply to the job-level SQL filter.
- Params is optional if no parameter overrides are needed.

---

# 8. Planner Guidelines

When generating execution plans, the planner should:

- prefer minimal overrides
- use defaults when possible
- avoid specifying parameters unless needed
- generate one job per analytic question unless multiple jobs are clearly required
- prefer fleet-level views unless a single entity is explicitly requested
- keep multiple outputs in one job when they share the same extracted dataset and time scope
- split into separate jobs when outputs require materially different SQL time windows or sensors

The planner must not:

- invent SQL templates
- invent preprocess modules
- invent plot types
- invent table types
- generate executable code

---

# 9. Execution Rules

1. A plan library may contain multiple runs.  
2. A run may contain multiple jobs.  
3. SQL executes once per job.  
4. Preprocessing executes once per job.  
5. All outputs in a job reuse the same processed dataset.  
6. Defaults are defined in code, not in the JSON schema.  
7. Filename collisions are resolved by the execution engine.  
8. Replot is output-only and does not rerun SQL or preprocessing.  

---

# 10. Registry Contract

Valid keys must exist in:

- `SQL_REGISTRY`
- `PREPROCESS_REGISTRY`
- `PLOT_REGISTRY`
- `TABLE_REGISTRY`

Invalid keys fail validation and do not execute.

---

# 11. Minimal Valid Execution Example

```json
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

---

# 12. Recovery Sentinel and Context Recovery

The system supports a recovery sentinel for ambiguous follow-up requests.

Minimal sentinel form:

```json
{
  "mode": "replot",
  "run_ref": "latest"
}
```

More specialized run lookup behavior may exist internally, but is not part of the primary v1.0 replot contract.
---

# 13. Replot Plans

Replot plans generate new outputs from a previous run.

A replot plan may reference the prior run in one of two ways:

##### Explicit `run_dir`

```json
{
  "mode": "replot",
  "run_dir": "runs/<timestamp>",
  "jobs": [ ... ]
}
```

##### Semantic `run_ref`

```json
{
  "mode": "replot",
  "run_ref": "latest",
  "jobs": [ ... ]
}
```

-
### Resolution rules

When executing a replot plan:

1. If `run_dir` is present, it takes precedence.  
2. Otherwise, if `run_ref` is present, the system resolves it to a concrete prior run directory.  
3. If neither is present, validation fails.  

---
# 13.1 Replot job structure

Each replot job references an existing `job_id` from the prior run and defines one or more new outputs.

Example:

```json
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
            "plot_name": "arm_vibration_7d_no_legend.png",
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

-
### Replot constraints

A valid replot plan:

- must contain at least one job
- must reference an existing `job_id`
- must generate at least one visible output
- may modify output parameters only
- may add new outputs that reuse the existing processed dataset

Replot plans must not include:

- `sql_template`
- `preprocess`
- `filters`

Those belong only to execution plans.

---

# 14. Unsupported Responses

Unsupported responses are safe exits and do not execute analytical code.

Examples:

```json
{
  "unsupported_request": true,
  "reason": "entity_group_undetermined"
}
```

Other supported reasons may include:

- `sensor_undetermined`
- `output_request_undetermined`
- `valid_request_undetermined`

---

# 15. Schema vs Runtime Behavior

This schema defines the structure of planner outputs, not the full runtime behavior.

The system may:

- perform recovery passes before final execution
- reinterpret sentinel plans into execution or replot plans
- inject context derived from prior runs

As a result:
- the final executed plan may differ from the initial planner output
- validation always applies to the final resolved plan

---

# 16. Schema Stability

This schema defines the v1.0 planner contract.

Future versions may introduce:

- stronger typed validation
- versioned schema metadata
- richer parameter validation
- expanded recovery semantics
- broader analytics module coverage

---