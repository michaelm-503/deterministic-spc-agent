
# CLI Reference — Deterministic SPC Agent

The Deterministic SPC Agent exposes a command line interface for validating plans, executing runs, generating replots, and verifying artifacts.

All commands are executed through the module entrypoint:

```
python -m spc_agent <command>
```

---

# Commands

## Validate

Validate a plan library or a single run JSON file.

```
python -m spc_agent validate planner/demo_gallery.json
```

Validation enforces:

- JSON schema compliance
- SQL template allow-lists
- Preprocess registry validation
- Plot/table registry validation

---

## Run

Execute a run from a plan library.

```
python -m spc_agent run planner/demo_gallery.json --run-index 0
```

Steps performed:

1. SQL templates execute against DuckDB
2. Deterministic preprocessing modules run
3. Plot and table outputs generate
4. Run artifacts are written to a run directory
5. Artifact hashes are generated

---

## Replot

Generate new plots from existing processed artifacts without rerunning SQL or preprocessing.

```
python -m spc_agent replot planner/demo_replot.json
```

Optional override:

```
python -m spc_agent replot planner/demo_replot.json --run-dir runs/<timestamp>
```

Replots are written under:

```
job/replots/<timestamp>/
```

Original run artifacts remain unchanged.

---

## Verify

Verify artifact integrity for a run.

```
python -m spc_agent verify runs/<timestamp>
```

Verification checks:

- missing files
- unexpected files
- hash mismatches

Replot artifacts are verified recursively.

---

# Typical Workflow

```
validate → run → verify → replot
```

Example:

```
python -m spc_agent validate planner/demo_gallery.json
python -m spc_agent run planner/demo_gallery.json --run-index 0
python -m spc_agent verify runs/<timestamp>
python -m spc_agent replot planner/demo_replot.json --run-dir runs/<timestamp>
```

`runs/<timestamp>` is printed to console after a successful run command.