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
- Verifies outputs via schema validation and hashing

This project demonstrates how to integrate LLMs into manufacturing analytics without sacrificing engineering rigor.

Synthetic manufacturing data from the [Industrial Machine Predictive Maintenance Dataset](https://www.kaggle.com/datasets/tatheerabbas/industrial-machine-predictive-maintenance) was used for this demo.

---

### Why This Exists

Most AI analytics systems suffer from:
- Non-deterministic outputs
- Hidden logic
- Poor reproducibility
- Weak validation
- Unsafe SQL or code generation

This system enforces:
- Tool allow-lists
- Schema validation
- Deterministic mathematical processing
- Artifact hashing and verification
- Full run traceability

The LLM acts strictly as a planner, not an analyst.

---

### Architecture

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
Standardized Plot Generation
      ↓
Verification + Run Artifacts
```

The LLM will never:
- Write SQL
- Execute Python
- Access raw data
- Perform statistical calculations

All analytics are executed by deterministic, version-controlled modules.

---

### Core Features

- SQL-backed data extraction (DuckDB)
- SPC statistics (mean, std, UCL, LCL) and violation detection
- EWMA smoothing with maintenance reset
- Standardized time-series plots
- Multi-run batch execution via structured plan library
- Full reproducibility via run folders
- Artifact hashing for verification
- Extensible architecture for additional SQL templates, preprocess logic, and plot types

---

### Example Output

**User prompt:**

>CPR11 needed maintenance last week due to motor temperature and again due to vibration. How is it doing now?

**Planner output:**

```
{
  "runs": [
    {"entity":"CPR11","sensor":"temperature_motor"},
    {"entity":"CPR11","sensor":"vibration_rms"}
  ]
}
```

**System generates:**
- Two SPC plots
- Processed datasets
- SPC reference tables
- Reproducibility script
- Hash verification output

![Image](assets/CPR11_demo.png)

---

### Project Structure

```
agentic-predictive-maintenance/
│
├── data/
├── notebooks/
├── preprocess/
├── plots/
├── planner/
├── sql/
├── verify/
├── runs/
│
├── environment.yml
├── README.md
└── LICENSE
```

---

### How to Run (Notebook Mode)

1️⃣ Create environment

```
conda env create -f environment.yml
conda activate agentic_mfg
```

2️⃣ Load dataset into DuckDB

Run:
```
notebooks/02_data_setup.ipynb
```
This notebook:
- Loads raw data
- Creates the long-format sensor table
- Computes SPC limits
- Stores both tables in DuckDB
	
3️⃣ Execute pipeline

Run:
```
notebooks/04_run_pipeline.ipynb
```
This notebook:
- Loads structured demo plans
- Executes parameterized SQL queries
- Applies deterministic EWMA processing
- Generates standardized plots
- Writes reproducible run artifacts
	
4️⃣ View outputs

Each execution creates:
```
runs/<timestamp>/
├── plan.json
├── extracted_data.csv
├── processed_data.csv
├── spc_reference.csv
├── plot.png
├── reproduce.py
└── hashes.json
```

Running reproduce.py regenerates identical outputs.

All results are:
- Deterministic
- Parameterized
- Version-controlled
- Verifiable

---

### Roadmap

Phase 1 - Proof of Concept Workflow ✅
- Structured data model
- Deterministic preprocessing
- Guardrailed execution
- Multi-run batch execution

Phase 2 – Expand workflows
- Full tool health check
- Fleet health check
- Violation metrics dashboard
- Boxplots and Heatmaps

Phase 3 – Production Hardening
- CLI runner
- Environment validation
- CI testing
- Artifact validation automation

Phase 4 – Agentic Front-End
- Plan schema enforcement
- Tool allow-lists
- LLM planner integration
- Guardrail validation
- Prompt + structured output

---

### License

MIT License

---

