
# Artifact Verification — Deterministic SPC Agent

The Deterministic SPC Agent records cryptographic hashes for all generated artifacts.

This enables verification that:

- outputs have not been modified
- runs are reproducible
- artifacts remain intact

---

# Hash Manifest

Each run generates:

```
hashes.json
```

This file records the hash for every artifact generated during execution.

Example:

```
{
  "job_1/processed_data.csv": "sha256:...",
  "job_1/plot.png": "sha256:..."
}
```

---

# Verification Command

Verify artifacts using:

```
python -m spc_agent verify runs/<timestamp>
```

Verification checks:

- missing files
- extra files
- mismatched hashes

---

# Replot Verification

Replots generate their own artifact sets under:

```
job/replots/<timestamp>/
```

Each replot includes its own `hashes.json` manifest.

Verification recursively validates:

- base run artifacts
- all replot artifacts

---

# Cross‑Platform Considerations

PNG hashes may differ across platforms due to rendering differences.

This is expected when verifying runs created on different operating systems.
