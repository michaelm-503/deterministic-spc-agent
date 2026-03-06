
# System Architecture — Deterministic SPC Agent

This document describes the architecture of the **Deterministic SPC Agent** and the execution model used to safely orchestrate manufacturing analytics using LLM planning with deterministic execution.

The system is designed to allow **AI-assisted planning** while ensuring that **all analytical execution remains deterministic, validated, and reproducible**.

---

# 1. Architectural Overview

The Deterministic SPC Agent separates the system into two distinct layers:

**Planning Layer**
- Natural language interpretation
- Structured plan generation (JSON)

**Execution Layer**
- Guardrailed deterministic analytics
- Registry-driven modules
- Verified reproducible outputs

The LLM **never executes analysis logic**.  
It only generates a **structured plan** that is validated and executed by deterministic modules.

---

# 2. Execution Pipeline

```
User Question
      ↓
LLM Planner: converts request to structured JSON
      ↓
Schema Validation
      ↓
SQL Execution from Template
      ↓
Deterministic Preprocessing
      ↓
Plot/Table Generation
      ↓
Run Artifacts + Hashing + Verification
      ↓↑
Replot (visual-only adjustments)
```

---

# 3. Determinism Model

The system enforces a **determinism contract**.

## Guarantees

- SQL templates are version controlled
- Preprocessing logic is deterministic
- No stochastic models
- Plot rendering is parameterized
- Execution modules are registry-controlled
- JSON plans are validated before execution

## Artifact guarantees

Base run artifacts are **immutable**.

Replot artifacts are **additive** and stored separately.

Each artifact set includes a **hash manifest** used for verification.

---

# 4. Run Artifact Model

```
runs/<timestamp>/
│
├── run.json
├── hashes.json
│
├── job_1/
│   ├── job.json
│   ├── extracted_data.csv
│   ├── processed_data.csv
│   ├── <plot>.png
│   ├── <table>.csv
│   └── replots/
│       └── <timestamp>/
│           ├── plot.png
│           ├── hashes.json
│           └── replot_plan.json
│
└── job_2/ ...
```

Base artifacts represent the **authoritative run state**.

Replots create additional artifact sets without modifying the base run.

---

# 5. Registry System

Execution modules are controlled by registries.

Registries exist for:

- SQL templates
- preprocessing functions
- plots
- tables

Example registry entry:

```
sql_template: entity_sensor_history
preprocess: ewma_spc
plot: spc_time_series, fleet_time_trend, fleet_boxplot
table: fleet_ooc_summary
```

Only registered modules can execute.

---

# 6. SQL Template System

SQL queries are implemented as **static templates**.

Templates define:

- allowed parameters
- parameter types
- safe filtering structure

The planner **cannot modify SQL logic**.

Only parameters are injected.

---

# 7. Preprocessing Modules

Preprocessing functions implement deterministic statistical operations.

Examples:

- EWMA smoothing
- SPC violation detection

Characteristics:

- deterministic mathematics
- no randomization
- version-controlled logic

---

# 8. Plotting System

Plots are generated using standardized modules.

Examples:

- SPC time-series plots 
- boxplots

Plot modules accept:

- processed data
- deterministic parameters

---

# 9. Replot Architecture

Replot mode enables **visual refinement without recomputing analytics**.

Replots operate on:

```
processed_data.csv
```

Replots generate new artifacts under:

```
job/replots/<timestamp>/
```

Original run outputs remain unchanged.

---

# 10. Verification System

Each run generates a hash manifest:

```
hashes.json
```

Verification command:

```
python -m spc_agent verify runs/<timestamp>
```

The system checks:

- missing files
- unexpected files
- hash mismatches

Verification recursively validates **replot artifacts**.

---

# 11. CI Integration

The CI pipeline performs:

1. environment creation
2. smoke test execution
3. run artifact generation
4. artifact verification

This guarantees deterministic reproducibility.

---

# 12. Safety Model

The LLM **cannot**:

- generate SQL
- execute Python
- access raw data
- perform statistical calculations

The LLM **only produces structured plans**.

All analytics are executed by deterministic modules.

---

# 13. Phase 4 Architecture

Phase 4 introduces the LLM planning interface.

```
Natural Language Prompt
        ↓
Prompt Interpretation Layer
        ↓
LLM Planner
        ↓
JSON Plan
        ↓
Schema Validation
        ↓
Deterministic Execution Engine
```

Future guardrails:

- planner schema enforcement
- tool allow-lists
- prompt safety validation

---

# 14. Design Philosophy

**LLMs plan. Deterministic systems execute.**

This architecture enables:

- safe AI orchestration
- reproducible analytics
- transparent engineering workflows
