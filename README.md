# Deterministic SPC Agent

A reproducible, guardrailed, agent-driven manufacturing analytics system.

---

## Overview

Large manufacturing facilities may contain thousands of equipment fleets, each with hundreds of sensors or other health indicators. The breadth of possible plots and the need for timely analysis limits the usefulness of static dashboards for sustaining engineering activities. Engineers frequently rely on hand-edited SQL filters and ad hoc plotting workflows, which are difficult to standardize and reproduce, as well as time consuming.

**Deterministic SPC Agent** augments and replaces ad hoc plotting workflows with a constrained, reproducible execution pipeline.

Instead of allowing AI models to generate analysis code or write SQL, this system:

- Uses an LLM only to generate a structured plan (JSON)
- Executes only approved SQL templates
- Applies deterministic preprocessing logic
- Generates standardized SPC visualizations
- Exports fully reproducible run artifacts
- Supports plot rework without re-running SQL or preprocessing
- Verifies outputs via schema validation and hashing

**Deterministic SPC Agent** demonstrates how LLMs can safely orchestrate manufacturing analytics without generating SQL, Python, or statistical logic.

All analytics are executed through a guardrailed, registry-driven execution engine with deterministic outputs and full run traceability.

Public predictive manufacturing data from the [Industrial Machine Predictive Maintenance Dataset](https://www.kaggle.com/datasets/tatheerabbas/industrial-machine-predictive-maintenance) was used for this repository.

---

## Why This Exists

##### Most AI analytics systems suffer from:

- Non-deterministic outputs
- Hidden logic
- Poor reproducibility
- Weak validation
- Unsafe SQL or code generation

##### This system enforces:

- Deterministic mathematical processing
- Full run traceability
- Strict JSON schema validation
- Tool allow-lists
- Artifact hashing and verification

##### Determinism Contract:
- SQL templates are version-controlled
- Preprocess logic is deterministic
- No stochastic models
- Plot rendering is parameterized only
- Replot never re-executes SQL
- Run artifacts are immutable

The LLM acts strictly as a planner, not an analyst.

---

## Core Features

- SQL-backed data extraction (DuckDB)
- SPC statistics and violation detection
- EWMA smoothing with maintenance reset
- Standardized time-series plots
- Multi-job batch execution via structured plan library
- Full reproducibility via run folders
- Artifact hashing for verification
- Extensible architecture for additional SQL templates, preprocess logic, and plot types
- Replot (Rework) mode enables visual plot adjustments without re-running SQL or preprocessing

---

### Example Output

**User prompt:**

>CPR11 needed maintenance last week due to motor temperature and again due to vibration. How is it doing now?

**Planner output:**

```
{
  "runs": [
    {
      "run_id": "demo_cpr11_health_check",
      "request_text": "CPR11 needed maintenance last week due to motor temperature and again due to vibration. How is the tool doing now?",
      "jobs": [
        {
          "job_id": "CPR11_temperature_motor",
          "sql_template": "entity_sensor_history",
          "preprocess": "ewma_spc",
          "filters": {
            "entity_group": "CPR",
            "entity": "CPR11",
            "sensor": "temperature_motor",
            "start_ts": null,
            "end_ts": null
          },
          "outputs": {
            "plots": [
              {
                "plot": "spc_time_series",
                "plot_name": "cpr11_temperature_motor_spc.png"
              }
            ]
          }
        }, ...
      ]
    }
  ]
}
```

**System generates:**
- Two SPC plots
- Processed datasets
- Reproducibility script
- Hash verification output

![Image](assets/CPR11_demo.png)

#### Selected additional examples:

- [The ARM technician will be out next week. Are any vibration PMs coming up?](docs/demo_gallery.md#the-arm-technician-will-be-out-next-week-are-any-vibration-pms-coming-up)

- [PMP06 had a vibration event around Jan 3. Show vibration trend ±3 days around that date.](docs/demo_gallery.md#pmp06-had-a-vibration-event-around-jan-3-show-vibration-trend-3-days-around-that-date)

- [PMP07 had current/rpm issues around Jan 2. Show both current and rpm ±2 days.](docs/demo_gallery.md#pmp07-had-currentrpm-issues-around-jan-2-show-both-current-and-rpm-2-days)

- [PMP09 had temp/current/rpm issues on Jan 12. Show temp trend last 3 days and an OOC summary table last 3 days (temp).](docs/demo_gallery.md#pmp09-had-tempcurrentrpm-issues-on-jan-12-show-temp-trend-last-3-days-and-an-ooc-summary-table-last-3-days-temp)

- [CPR15 had vibration on Jan 9 and pressure instability on Jan 11. Show last 7 days for vibration and
    pressure.](#cpr15-had-vibration-on-jan-9-and-pressure-instability-on-jan-11-show-last-7-days-for-vibration-and-pressure)

- [Replot pressure for just the bad PM cycle. 1/10-1/12.](docs/demo_gallery.md#replot-pressure-for-just-the-bad-pm-cycle-110-112)

- View more examples in the [Demo Gallery](docs/demo_gallery.md)

---

### How to Run (30-Second Quickstart)

Generate a deterministic SPC plot in under a minute. See example prompts and outputs in [Demo Gallery](docs/demo_gallery.md).

1️⃣ Clone the repository

```
git clone https://github.com/michaelm-503/deterministic-spc-agent.git
cd deterministic-spc-agent
```

2️⃣ Create the environment

``` bash
conda env create -f environment.yml
conda activate agentic_mfg
```
3️⃣ Load the dataset

Run the setup notebook once:
```
notebooks/02_data_setup.ipynb
```
This loads the synthetic manufacturing dataset into DuckDB.
	
4️⃣ Validate a plan

```
python -m spc_agent validate planner/demo_gallery.json
```
Validation enforces:
- JSON schema compliance
- SQL template allow-lists
- Preprocess registry validation
- Plot/table registry validation

5️⃣ Run the first demo

```
python -m spc_agent run planner/demo_gallery.json --run-index 0
```
This command will:
1. Execute SQL templates
2. Apply deterministic preprocessing
3. Generate plots and tables
4. Write reproducible artifacts

6️⃣ View outputs

Each execution creates:
```
runs/<timestamp>/
├── run.json
├── job_1/
│   ├── job.json
│   ├── extracted_data.csv
│   ├── processed_data.csv
│   ├── <plot_name>.png
│   └── <table_name>.csv
├── job_2/
│   └── ...
└── hashes.json (optional)
```

You can re-run an existing execution plan directly:

```
python -m spc_agent run runs/<timestamp>/run.json
```
This creates a new runs/<new_timestamp>/ directory with the same artifact set and deterministic outputs (content-equivalent), based on the recorded plan.

7️⃣ Optional: Replot existing runs (no SQL / no preprocess)

Replot mode regenerates plots and tables from existing processed artifacts, without re-running SQL queries or preprocessing logic.

```
python -m spc_agent replot planner/demo_replot.json
```

The replot planner must reference a valid runs/<timestamp> directory containing previously generated job artifacts.

This enables rapid visualization refinement without altering the original run outputs.

---


## Architecture

```
User Question
      ↓
LLM Planner (JSON only)
      ↓
Validated Plan Schema
      ↓
SQL Template Execution
      ↓
Deterministic Preprocessing
      ↓
Plot/Table Generation
      ↓
Verification (optional, extensible) + Run Artifacts
```

The LLM will never:
- Write SQL
- Execute Python
- Access raw data
- Perform statistical calculations

All analytics are executed by deterministic, version-controlled modules.

Schema reference: [`json_schema_v0_2_0.md`](docs/json_schema_v0_2_0.md).

---

### Design Principles

- LLMs plan; deterministic code executes.
- All execution pathways are registry-controlled.
- SQL parameter signatures are explicitly declared.
- No dynamic code generation.
- All outputs are reproducible from stored artifacts.

---

### Project Structure

```
deterministic-spc-agent/
│
├── data/
├── planner/
├── plots/
├── preprocess/
├── runner/
├── runs/
├── sql/
├── tables/
├── tests/
├── verify/
│
├── README.md
├── docs/
├── notebooks/
├── environment.yml
└── LICENSE
```

---

## Roadmap

#### Phase 1 - Proof of Concept Workflow ✅
- Structured data model
- Deterministic preprocessing
- Guardrailed execution

#### Phase 2 – An Execution Framework ✅
- Single-tool and fleet-level analytics workflows
- Plot-level parameter overrides and slicing
- Replot (visual-only rework) mode
- SQL template registry with parameter signatures
- JSON schema validation framework

#### Phase 3 – Production Hardening
- CLI runner
- CI integration
- Automated artifact validation
- Environment pinning

#### Phase 4 – Agentic Front-End
- LLM planner integration
- Guardrail enforcement
- Prompt interpretation layer
- Secure execution interface
- Tool allow-lists

---

### License

MIT License

---

