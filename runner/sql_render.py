from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any


def normalize_entity_filter(entity: Any) -> list[str]:
    """
    Normalize planner/entity filter input into a clean list of entity IDs.

    Supported input shapes
    ----------------------
    - None -> []
    - "ARM20" -> ["ARM20"]
    - ["ARM20", "ARM21"] -> ["ARM20", "ARM21"]
    - ("ARM20", "ARM21") -> ["ARM20", "ARM21"]
    """
    if entity is None:
        return []

    if isinstance(entity, str):
        value = entity.strip()
        return [value] if value else []

    if isinstance(entity, Iterable):
        out: list[str] = []
        for item in entity:
            if item is None:
                continue
            value = str(item).strip()
            if value:
                out.append(value)
        return out

    value = str(entity).strip()
    return [value] if value else []


def build_entity_filter_clause(column_name: str, entity: Any) -> tuple[str, list[Any]]:
    """
    Build a SQL WHERE clause fragment plus matching parameter list.

    Returns
    -------
    clause, params

    Examples
    --------
    None -> ("", [])
    "ARM20" -> (" AND entity = ?", ["ARM20"])
    ["ARM20", "ARM21"] -> (" AND entity IN (?, ?)", ["ARM20", "ARM21"])
    """
    entities = normalize_entity_filter(entity)

    if not entities:
        return "", []

    if len(entities) == 1:
        return f" AND {column_name} = ?", [entities[0]]

    placeholders = ", ".join(["?"] * len(entities))
    return f" AND {column_name} IN ({placeholders})", list(entities)


def render_sql_template(sql_path: str | Path, substitutions: dict[str, str]) -> str:
    """
    Load a SQL template from disk and replace simple string placeholders.
    """
    sql = Path(sql_path).read_text()
    for key, value in substitutions.items():
        sql = sql.replace(key, value)
    return sql


def render_pm_event_sensor_history_sql(
    sql_path: str | Path,
    *,
    entity_group: str,
    entity: Any = None,
    start_ts: Any = None,
    end_ts: Any = None,
) -> tuple[str, list[Any]]:
    """
    Render the PM-event SQL template and return (sql, params).

    Parameter order matches the rendered SQL:
    1. entity_group
    2..N entity params if entity filter is present
    N+1. start_ts
    N+2. end_ts
    """
    entity_clause, entity_params = build_entity_filter_clause("data.entity", entity)

    sql = render_sql_template(
        sql_path,
        {"{{ENTITY_FILTER_CLAUSE}}": entity_clause},
    )

    params: list[Any] = [entity_group, *entity_params, start_ts, end_ts]
    return sql, params
