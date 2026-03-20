
# Deterministic SPC Agent
## Developer Guide

This guide focuses on how to safely extend or modify the system.

---

# 1. System Overview

The system enforces a strict contract:

```
User intent → Structured plan → Validated plan → Deterministic execution → Artifacts
```

Key principle:

> The LLM interprets intent. The system executes deterministically.

LLMs **never generate executable code**.  
They produce **structured JSON plans** that reference pre-approved modules.

---

# 2. LLM System Prompt

`planner_prompt.py` constructs the system prompt for the LLM planner.

The planner schema is defined in `docs/planner_schema.md` and enforced by `runner/validate_plan.py`.

The prompt mirrors this schema to guide LLM output but is not the source of truth.

The system prompt includes:

- Safety rules
- Plan structure and shape definitions
- Supported parameters and flags
- Replot and Recovery Sentinel behaviors
- Unsupported plan responses
- Tool allow lists (auto generated from registry)
	- SQL templates
	- preprocess modules
	- plot modules
	- table modules
- Named entity recognition lists (auto generated from catalog)
	- entities/entity groups
	- sensors

This is essential to LLM performance as a planner. Substantially new analysis workflows may need to be explained. *Future:* update registry to store prompt engineering text for each analytical feature.

---

# 3. Registry + Catalog

`runner/registry.py` is the official record of which code modules are supported by the analytical back-end. Any new modules must be manually registered after validation and vetting.

`planner/metadata/catalog.json` is a generated artifact used by the planner to expose available entities and sensors.

It is typically derived from the underlying dataset and updated via the setup pipeline. *Future:* In a production environment, it should be scheduled or automated to run whenever a new named entity is added to the database.

The planner prompt is built from both:
- registry (available tools)
- catalog (entities and sensors)

After adding new modules or updating data sources, ensure the planner catalog is rebuilt if required by the change (e.g., new entities, sensors, or data sources).

The registry defines what can be executed.  
The catalog defines what the planner can reference.

---
	
# 4. Analytical Modules

#### Module Requirements

**All modules must:**

- be deterministic and operate only on provided inputs  
- not perform external I/O, dynamic code execution, or side effects  
- must be stateless and not depend on external runtime context

---
# 4.1 SQL Templates

Location:

```
sql/
```

Properties:

- parameterized templates only
- no arbitrary SQL execution
- receive validated filter parameters from the execution engine at runtime

Prevents:

- SQL injection
- LLM-generated queries

-
### Add a New SQL Template

1. Add template in: `sql/`
2. Validate code and add to registry

---

# 4.2 Preprocess Modules

Location:

```
preprocess/
```

Example:

```
ewma_spc.py
```

Responsibilities:

- smoothing
- SPC limits
- derived metrics

-
### Add a New Preprocess Module

1. Create module in: `preprocess/`
2. Implement deterministic transformation
3. Validate code and add to registry

---

# 4.3 Plot Modules

Plots must not modify input data and must only read from processed_data.csv

Location:

```
plots/
```

Examples:

```
spc_time_series.py
fleet_time_trend.py
fleet_boxplot.py
```

Inputs:

```
processed_data.csv
```

Outputs:

```
*.png
```
-
### Add a New Plot

1. Create file in: `plots/`
2. Implement plotting function
3. Validate code and add to registry

---

# 4.4 Table Modules

Tables must not modify input data and must produce deterministic CSV outputs derived only from processed_data.csv

Location:

```
tables/
```

Example:

```
fleet_ooc_summary.py
```

Outputs:

```
*.csv
```
### Add a New Table

1. Create file in: `tables/`
2. Implement summarization workflow
3. Validate code and add to registry


---

# 5. Non-Extensible Components

The following components are not intended to be modified:

- Planner schema (`docs/planner_schema.md`)
- Validation logic (`runner/validate_plan.py`)
- Execution pipeline structure

Changes to these components may break system guarantees and should be treated as core architecture changes.

---

# 6. Development Workflow

1. Add or modify module (sql / preprocess / plot / table)
2. Register module in registry
3. Rebuild planner catalog if needed
4. Validate with CLI (`python -m spc_agent validate`)
5. Execute test run (`python -m spc_agent run`)

---