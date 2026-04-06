from __future__ import annotations

import pandas as pd


def preprocess_pm_event_ooc_summary(df: pd.DataFrame, job: dict, params: dict | None = None) -> pd.DataFrame:
    """
    Summarize PM-event sensor rows into one row per PM event.

    Expected input columns
    ----------------------
    entity_group, entity, ts, hours_pre_pm, failure_type, sensor, value, ucl, lcl

    Output columns
    --------------
    entity
    ts
    hours_pre_pm
    failure_type
    ooc_sensors

    Notes
    -----
    - One SQL row is expected per sensor at the final pre-PM timestamp.
    - OOC is computed on raw value vs. lcl/ucl.
    - Only violated sensors are included in ooc_sensors.
    """
    params = params or {}

    required = {
        "entity_group",
        "entity",
        "ts",
        "hours_pre_pm",
        "failure_type",
        "sensor",
        "value",
        "ucl",
        "lcl",
    }
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    if df.empty:
        return pd.DataFrame(
            columns=["entity", "ts", "hours_pre_pm", "failure_type", "ooc_sensors"]
        )

    work = df.copy()
    work["ts"] = pd.to_datetime(work["ts"])

    # Null-safe OOC calculation
    have_limits = work["ucl"].notna() & work["lcl"].notna()
    work["sensor_ooc"] = False
    work.loc[have_limits, "sensor_ooc"] = (
        (work.loc[have_limits, "value"] > work.loc[have_limits, "ucl"])
        | (work.loc[have_limits, "value"] < work.loc[have_limits, "lcl"])
    )

    def _agg(group: pd.DataFrame) -> pd.Series:
        ooc_sensors = sorted(group.loc[group["sensor_ooc"], "sensor"].dropna().astype(str).unique())
        return pd.Series(
            {
                "hours_pre_pm": group["hours_pre_pm"].iloc[0],
                "failure_type": group["failure_type"].iloc[0],
                "ooc_sensors": ", ".join(ooc_sensors),
            }
        )

    summary = (
        work.groupby(["entity", "ts"], dropna=False)
        .apply(_agg, include_groups=False)
        .reset_index()
        .sort_values(["ts", "entity"])
        .reset_index(drop=True)
    )

    return summary
