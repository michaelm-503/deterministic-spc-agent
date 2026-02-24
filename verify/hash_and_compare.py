import hashlib
from pathlib import Path


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def verify_reproduction(original_run, reproduced_run):
    original = Path(original_run)
    reproduced = Path(reproduced_run)

    files = [
        "processed_data.csv",
        "spc_reference.csv"
    ]

    for fname in files:
        h1 = file_hash(original / fname)
        h2 = file_hash(reproduced / fname)

        if h1 != h2:
            raise ValueError(f"Mismatch in {fname}")

    print("Reproduction verified: hashes match")