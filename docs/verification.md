

# Deterministic SPC Agent
## Artifact Verification


The Deterministic SPC Agent records cryptographic hashes for all generated artifacts.

This enables:

- detection of post-run modification  
- reproducibility validation  
- artifact integrity guarantees  

Verification is intentionally **decoupled from execution**.

Runs produce artifacts and hash manifests.  
Verification is performed separately as a read-only check.

---

# 1. Hash Manifest

Each execution run produces a hash manifest:

```
hashes.json
```

This file contains a SHA256 hash for every tracked artifact in the run directory.

Example:

```json
{
  "run.json": "sha256:...",
  "run_summary.md": "sha256:...",
  "planner_raw.txt": "sha256:...",
  "planner_plan.json": "sha256:...",
  "job_1/processed_data.csv": "sha256:...",
  "job_1/plot.png": "sha256:..."
}
```
-
### Scope of hashing

Hashing occurs **after all artifacts are written**, including:

- execution plan (`run.json`)
- generated report (`run_summary.md`)
- planner debug artifacts (when applicable)
- job-level artifacts (data, plots, tables)
- replot artifacts (if present)

This ensures the manifest reflects the **final, complete state of the run**.

---

# 2. Verification Command

Artifacts are verified using the CLI:

```
python -m spc_agent verify runs/<timestamp>
```

Verification is:

- read-only (does not modify artifacts)
- deterministic
- independent of planner or execution logic

-
### Verification checks

The verification process compares the current filesystem against `hashes.json` and reports:

- **missing files** — expected artifacts not present  
- **extra files** — unexpected artifacts present  
- **hash mismatches** — files modified after execution  

A successful verification confirms that the run artifacts are intact and unmodified.

---

# 3. Replot Verification

Replot workflows generate additional artifacts under:

```
job/replots/<timestamp>/
```

Each replot directory includes its own:

```
hashes.json
```
-
### Recursive validation

Verification automatically includes:

- base run artifacts  
- all nested replot artifacts  

This ensures that:

- original execution outputs are intact  
- all replot outputs are independently verifiable  

Replots do not modify original artifacts; they only append new artifact sets.

---

# 4. Relationship to Execution

Verification is not part of execution.

- Execution produces artifacts and a hash manifest  
- Verification evaluates artifact integrity after the fact  

This separation ensures:

- no runtime overhead during execution  
- no coupling between planner/execution logic and validation  
- ability to validate runs long after they are generated  

---

# 5. What Verification Guarantees

A successful verification guarantees:

- no tracked artifacts have been modified  
- no artifacts are missing  
- no unexpected artifacts were introduced  

This provides:

- reproducibility confidence  
- auditability for engineering workflows  
- trust in generated analysis outputs  

---

# 6. What Verification Does Not Guarantee

Verification does not validate:

- correctness of the analysis logic  
- correctness of the underlying data  
- equivalence across different runs  
- equivalence across different environments  

It only verifies that:

> **the artifacts match the exact state at the time the run was completed**

---

# 7. Cross-Platform Considerations

Some artifacts may differ across platforms.

### Common example: PNG files

Plot images may produce different hashes across environments due to:

- rendering backends  
- font differences  
- library version differences  

This is expected when comparing runs generated on different systems.

-
### Recommended practice

- Use verification to validate **within the same environment**
- Treat cross-platform hash differences as expected unless strict reproducibility is required

---
