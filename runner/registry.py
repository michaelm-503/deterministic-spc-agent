from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# -----------------------------------------------------------------------------
# Project Root
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# SQL Registry (with explicit parameter signatures)
# -----------------------------------------------------------------------------

from runner.sql_render import render_sql_entity_helper

@dataclass(frozen=True)
class SQLSpec:
    path: Path
    params: tuple[str, ...]
    renderer: Callable | None = None # optional Python renderer for dynamic SQL


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
    "pm_event_sensor_history": SQLSpec(
        path=PROJECT_ROOT / "sql" / "pm_event_sensor_history.sql",
        params=("entity_group", "entity", "start_ts", "end_ts"),
        renderer=render_sql_entity_helper,
    ),
    "entity_all_sensor_history": SQLSpec(
        path=PROJECT_ROOT / "sql" / "entity_all_sensor_history.sql",
        params=("entity_group", "entity", "start_ts", "end_ts"),
        renderer=render_sql_entity_helper,
    ),
}


# -----------------------------------------------------------------------------
# Preprocess Registry
# -----------------------------------------------------------------------------

from preprocess.spc_mode_rolling import preprocess_ewma_spc
from preprocess.pm_event_ooc_summary import preprocess_pm_event_ooc_summary
from preprocess.multi_sensor_health_summary import preprocess_multi_sensor_health_summary

PREPROCESS_REGISTRY = {
    "ewma_spc": preprocess_ewma_spc,
    "pm_event_ooc_summary": preprocess_pm_event_ooc_summary,
    "multi_sensor_health_summary": preprocess_multi_sensor_health_summary,
}


# -----------------------------------------------------------------------------
# Plot Registry
# -----------------------------------------------------------------------------

from plots.spc_time_series import plot_spc_time_series
from plots.fleet_time_trend import plot_fleet_time_trend
from plots.fleet_boxplot import plot_fleet_boxplot

PLOT_REGISTRY = {
    "spc_time_series": plot_spc_time_series,
    "fleet_time_trend": plot_fleet_time_trend,
    "fleet_boxplot": plot_fleet_boxplot,
}


# -----------------------------------------------------------------------------
# Table Registry
# -----------------------------------------------------------------------------

from tables.fleet_ooc_summary import write_fleet_ooc_summary_csv
from tables.pm_event_summary_table import write_pm_event_summary_table
from tables.multi_sensor_health_table import write_multi_sensor_health_table

TABLE_REGISTRY = {
    "fleet_ooc_summary": write_fleet_ooc_summary_csv,
    "pm_event_summary_table": write_pm_event_summary_table,
    "multi_sensor_health_table": write_multi_sensor_health_table,
}