from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from preprocess.spc_mode_rolling import preprocess_ewma_spc
from plots.spc_time_series import plot_spc_time_series
from plots.fleet_time_trend import plot_fleet_time_trend
from plots.fleet_boxplot import plot_fleet_boxplot
from tables.fleet_ooc_summary import write_fleet_ooc_summary_csv


# -----------------------------------------------------------------------------
# Project Root
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# SQL Registry (with explicit parameter signatures)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SQLSpec:
    path: Path
    params: tuple[str, ...]  # ordered param names matching '?' placeholders


SQL_REGISTRY: dict[str, SQLSpec] = {
    # entity-level query
    # Must match '?' order in entity_sensor_all_history.sql
    "entity_sensor_history": SQLSpec(
        path=PROJECT_ROOT / "sql" / "entity_sensor_all_history.sql",
        params=("entity_group", "entity", "sensor", "start_ts", "end_ts"),
    ),

    # fleet-level query (no entity parameter)
    # Must match '?' order in fleet_sensor_history.sql
    "fleet_sensor_history": SQLSpec(
        path=PROJECT_ROOT / "sql" / "fleet_sensor_history.sql",
        params=("entity_group", "sensor", "start_ts", "end_ts"),
    ),
}


# -----------------------------------------------------------------------------
# Preprocess Registry
# -----------------------------------------------------------------------------

PREPROCESS_REGISTRY = {
    "ewma_spc": preprocess_ewma_spc,
}


# -----------------------------------------------------------------------------
# Plot Registry
# -----------------------------------------------------------------------------

PLOT_REGISTRY = {
    "spc_time_series": plot_spc_time_series,
    "fleet_time_trend": plot_fleet_time_trend,
    "fleet_boxplot": plot_fleet_boxplot,
}


# -----------------------------------------------------------------------------
# Table Registry
# -----------------------------------------------------------------------------

TABLE_REGISTRY = {
    "fleet_ooc_summary": write_fleet_ooc_summary_csv,
}