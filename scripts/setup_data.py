from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

SENSOR_COLUMNS = [
    "vibration_rms",
    "temperature_motor",
    "current_phase_avg",
    "pressure_level",
    "rpm",
    "ambient_temp",
]

ENTITY_GROUP_MAP = {
    "CNC": "CNC",
    "Pump": "PMP",
    "Compressor": "CPR",
    "Robotic Arm": "ARM",
}


def load_raw_dataset(raw_csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(raw_csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["entity_group"] = df["machine_type"].replace(ENTITY_GROUP_MAP)
    df["entity"] = df["entity_group"] + df["machine_id"].astype("str").str.zfill(2)
    return df


def build_long_sensor_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("timestamp")
    df_long = df.melt(
        id_vars=[
            "timestamp",
            "entity",
            "entity_group",
            "operating_mode",
            "hours_since_maintenance",
            "failure_within_24h",
            "rul_hours",
            "failure_type",
        ],
        value_vars=SENSOR_COLUMNS,
        var_name="sensor",
        value_name="value",
    )
    return df_long.dropna(subset=["value"])


def build_spc_limits(df_long: pd.DataFrame) -> pd.DataFrame:
    df_normal = df_long[df_long["operating_mode"] == "normal"].copy()

    spc_stats = (
        df_normal.groupby(["entity_group", "sensor"], as_index=False)
        .agg(mean=("value", "mean"), std=("value", "std"))
    )

    spc_stats["ucl"] = spc_stats["mean"] + 3 * spc_stats["std"]
    spc_stats["centerline"] = spc_stats["mean"]
    spc_stats["lcl"] = spc_stats["mean"] - 3 * spc_stats["std"]
    return spc_stats


def write_duckdb(sensor_data_csv: Path, chart_limits_csv: Path, duckdb_path: Path) -> None:
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(duckdb_path))

    con.execute("DROP TABLE IF EXISTS sensor_data")
    con.execute("DROP TABLE IF EXISTS sensor_spc_limits")

    con.execute(
        f"""
        CREATE TABLE sensor_data AS
        SELECT *
        FROM read_csv_auto('{sensor_data_csv.as_posix()}')
        """
    )

    con.execute(
        f"""
        CREATE TABLE sensor_spc_limits AS
        SELECT *
        FROM read_csv_auto('{chart_limits_csv.as_posix()}')
        """
    )

    con.close()


def setup_data(
    project_root: Path,
    *,
    raw_csv_rel: str = "data/raw/predictive_maintenance_v3.csv",
    processed_sensor_rel: str = "data/processed/predictive_maintenance.csv",
    processed_limits_rel: str = "data/processed/chart_limits.csv",
    duckdb_rel: str = "data/mfg.duckdb",
) -> None:
    raw_csv_path = project_root / raw_csv_rel
    sensor_csv_path = project_root / processed_sensor_rel
    limits_csv_path = project_root / processed_limits_rel
    duckdb_path = project_root / duckdb_rel

    sensor_csv_path.parent.mkdir(parents=True, exist_ok=True)
    limits_csv_path.parent.mkdir(parents=True, exist_ok=True)

    df = load_raw_dataset(raw_csv_path)
    df_long = build_long_sensor_table(df)
    spc_limits = build_spc_limits(df_long)

    df_long.to_csv(sensor_csv_path, index=False)
    spc_limits.to_csv(limits_csv_path, index=False)
    write_duckdb(sensor_csv_path, limits_csv_path, duckdb_path)

    print("Setup complete:")
    print(f"  Raw input:    {raw_csv_path}")
    print(f"  Sensor CSV:   {sensor_csv_path}")
    print(f"  Limits CSV:   {limits_csv_path}")
    print(f"  DuckDB:       {duckdb_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build processed manufacturing tables and DuckDB.")
    parser.add_argument("--project-root", default=".", help="Path to repo root.")
    args = parser.parse_args()
    setup_data(Path(args.project_root).resolve())


if __name__ == "__main__":
    main()