
# Deterministic SPC Agent
## CLI Reference


The Deterministic SPC Agent exposes a command line interface for:

- natural-language analytics (`ask`)
- deterministic execution (`run`)
- replot workflows (`replot`)
- artifact verification (`verify`)
- plan validation (`validate`)

All commands are executed through the module entrypoint:

```bash
python -m spc_agent <command>
```

---

# 1. Setup

The setup step prepares the local analytics environment.

```bash
python -m spc_agent setup
```

-
### What setup does

1. Extracts the raw dataset  
2. Transforms data into sensor tables  
3. Builds the DuckDB database  
4. Generates the planner metadata catalog  

-
### Outputs

Setup creates:

- processed CSV files under `data/processed/`  
- DuckDB database under `data/mfg.duckdb`  
- planner catalog under `planner/metadata/catalog.json`  

-
### When to run setup

Run setup:

- on first clone of the repository  
- after deleting local data directories  
- after updates to dataset or schema  

-
### Notes

- Setup is **idempotent** — safe to run multiple times  
- Streamlit runs setup automatically if initialization is missing  
- CLI users must run setup manually before using `ask` or `run`  

---

# 2. Command Overview

| Command | Purpose |
|---|---|
| `setup` | Initialize data, database, and planner catalog |
| `ask` | End-to-end workflow: prompt → plan → execution → artifacts |
| `run` | Execute a pre-defined plan (no planner) |
| `replot` | Generate new outputs from existing artifacts |
| `verify` | Validate artifact integrity |
| `validate` | Validate plan JSON against schema and registries |

---

# 3. ask (Primary Interface)

Run an end-to-end workflow from a natural-language prompt.

```bash
python -m spc_agent ask "Plot 7 days of vibration data for ARM tools"
```

-
### What `ask` does

1. Routes request (`curated`, `llm`, or `auto`)  
2. Generates a structured plan  
3. Performs validation  
4. Executes deterministic pipeline  
5. Writes artifacts  
6. Generates hash manifest  

-
### Recovery behavior

For follow-up or ambiguous prompts, `ask` may:

- reuse context from the most recent run  
- perform a recovery planning pass  
- resolve into:
  - execution plan  
  - replot plan  
  - unsupported response  

---

# 4. run (Deterministic Execution)

Execute a plan without using the planner.

```bash
python -m spc_agent run planner/demo_gallery.json --run-index 0
```

-
### What `run` does

1. Validates the selected run  
2. Executes SQL templates  
3. Runs preprocessing modules  
4. Generates plots and tables  
5. Writes run artifacts  
6. Generates `hashes.json`  

-
### When to use

- testing curated plans  
- debugging execution logic  
- CI workflows  
- reproducible batch execution  

`run` does **not** perform planning or recovery.

---

# 5. replot (Artifact Reuse)

Generate new outputs from existing processed artifacts.

```bash
python -m spc_agent replot planner/demo_replot.json
```

Optional override:

```bash
python -m spc_agent replot planner/demo_replot.json --run-dir runs/<timestamp>
```

-
### What `replot` does

- loads processed artifacts from a prior run  
- generates new plots or tables  
- writes outputs under:

```text
job/replots/<timestamp>/
```

-
### Key behavior

- does **not** rerun SQL  
- does **not** rerun preprocessing  
- does **not** modify original artifacts  
- generates its own hash manifest  

---

# 6. verify (Artifact Integrity)

Verify that a run’s artifacts have not changed.

```bash
python -m spc_agent verify runs/<timestamp>
```

-
### Verification checks

- missing files  
- unexpected files  
- hash mismatches  

Verification recursively includes:

- base run artifacts  
- all replot artifacts  

-
### Notes

- verification is read-only  
- independent of execution and planning  
- can be run at any time  

---

# 7. validate (Schema + Registry)

Validate a plan file before execution.

```bash
python -m spc_agent validate planner/demo_gallery.json
```

-
### Validation checks

- JSON schema compliance  
- SQL template allow-list  
- preprocess registry  
- plot registry  
- table registry  

Validation does **not** execute any workflows.

---

# 8. Hashing Behavior

Hashing is part of execution (`ask`, `run`, `replot`).

Each run produces:

```text
hashes.json
```

Hashing includes:

- run metadata (`run.json`)  
- generated report (`run_summary.md`)  
- planner artifacts (when applicable)  
- job outputs (data, plots, tables)  

Verification (`verify`) consumes these manifests.

---

# 9. Typical Workflows

### Interactive (recommended)

```bash
python -m spc_agent ask "Plot vibration trends for ARM tools"
```

-
### Deterministic / CI

```bash
python -m spc_agent setup
python -m spc_agent validate planner/demo_gallery.json
python -m spc_agent run planner/demo_gallery.json --run-index 0
python -m spc_agent verify runs/<timestamp>
```

-
### Replot workflow

```bash
python -m spc_agent replot planner/demo_replot.json --run-dir runs/<timestamp>
```

---

# 10. Output Location

All execution outputs are written under:

```text
runs/<timestamp>/
```

The run directory is printed to the console after execution.
