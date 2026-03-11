from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def build_catalog(project_root: Path, *, duckdb_rel: str = "data/mfg.duckdb") -> dict:
    duckdb_path = project_root / duckdb_rel
    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB not found: {duckdb_path}")

    con = duckdb.connect(str(duckdb_path))

    entity_groups = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT entity_group FROM sensor_data ORDER BY entity_group"
        ).fetchall()
    ]
    entities = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT entity FROM sensor_data ORDER BY entity"
        ).fetchall()
    ]
    sensors = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT sensor FROM sensor_data ORDER BY sensor"
        ).fetchall()
    ]

    rows = con.execute(
        """
        SELECT entity_group, entity
        FROM sensor_data
        GROUP BY entity_group, entity
        ORDER BY entity_group, entity
        """
    ).fetchall()

    con.close()

    entities_by_group: dict[str, list[str]] = {}
    for entity_group, entity in rows:
        entities_by_group.setdefault(entity_group, []).append(entity)

    return {
        "entity_groups": entity_groups,
        "entities": entities,
        "entities_by_group": entities_by_group,
        "sensors": sensors,
    }


def write_catalog(project_root: Path, catalog: dict, *, out_rel: str = "planner/metadata/catalog.json") -> Path:
    out_path = project_root / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cached planner metadata catalog from DuckDB.")
    parser.add_argument("--project-root", default=".", help="Path to repo root.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    catalog = build_catalog(project_root)
    out_path = write_catalog(project_root, catalog)

    print("Planner catalog built:")
    print(f"  Output: {out_path}")
    print(f"  Entity groups: {catalog['entity_groups']}")
    print(f"  Sensors: {catalog['sensors']}")


if __name__ == "__main__":
    main()