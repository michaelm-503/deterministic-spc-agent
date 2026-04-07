from __future__ import annotations

import numpy as np
import pandas as pd


def preprocess_multi_sensor_health_summary(
    df: pd.DataFrame,
    job: dict,
    params: dict | None = None,
) -> pd.DataFrame:
    """
    Summarize one entity across all sensors into a health-status table.

    Expected input columns
    ----------------------
    entity_group, entity, ts, sensor, value, ucl, centerline, lcl

    Optional params
    ---------------
    window_days : int, default 2
        Window used for recent OOC rate and EWMA slope classification.
    ewma_alpha : float, default 0.2
        EWMA smoothing constant used for trend and z-score calculation.
    stable_slope_z_per_day : float, default 0.25
        Max absolute EWMA z-score slope/day for stable baseline.
    drifting_slope_z_per_day : float, default 0.50
        Min absolute EWMA z-score slope/day for drifting classification.
    volatile_ooc_rate : float, default 0.05
        Minimum recent OOC rate to classify as volatile when not drifting or OOC.
    slope_window_hours : int, default 24
        Defines start of window for slope calculation (relative to latest data point).
    """
    params = params or {}

    required = {
        "entity_group",
        "entity",
        "ts",
        "sensor",
        "value",
        "ucl",
        "centerline",
        "lcl",
    }
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    if df.empty:
        return pd.DataFrame(
            columns=[
                "entity",
                "sensor",
                "latest_value",
                "latest_ewma",
                "centerline",
                "std",
                "latest_z_score",
                "ooc_rate_2d",
                "ewma_slope_z_per_day_24h",
                "baseline_trend",
                "health_status",
            ]
        )

    window_days = int(params.get("window_days", 2))
    ewma_alpha = float(params.get("ewma_alpha", 0.2))
    stable_slope_z_per_day = float(params.get("stable_slope_z_per_day", 0.25))
    drifting_slope_z_per_day = float(params.get("drifting_slope_z_per_day", 0.50))
    volatile_ooc_rate = float(params.get("volatile_ooc_rate", 0.05))
    slope_window_hours = int(params.get("slope_window_hours", 24))

    work = df.copy()
    work["ts"] = pd.to_datetime(work["ts"])
    work = work.sort_values(["entity", "sensor", "ts"]).reset_index(drop=True)

    # Sigma estimate from control limits: std = (ucl - centerline) / 3
    work["std"] = (work["ucl"] - work["centerline"]) / 3.0
    work.loc[work["std"] <= 0, "std"] = np.nan

    # Null-safe OOC check
    have_limits = work["ucl"].notna() & work["lcl"].notna()
    work["sensor_ooc"] = False
    work.loc[have_limits, "sensor_ooc"] = (
        (work.loc[have_limits, "value"] > work.loc[have_limits, "ucl"])
        | (work.loc[have_limits, "value"] < work.loc[have_limits, "lcl"])
    )

    def _per_sensor(group: pd.DataFrame) -> pd.Series:
        group = group.sort_values("ts").copy()
    
        latest = group.iloc[-1]
        entity = str(latest["entity"])
        sensor = str(latest["sensor"])

        group["ewma"] = group["value"].ewm(alpha=ewma_alpha, adjust=False).mean()
        latest_ewma = float(group["ewma"].iloc[-1])

        centerline = latest["centerline"]
        std = latest["std"]

        if pd.notna(centerline) and pd.notna(std) and std > 0:
            latest_z_score = (latest_ewma - centerline) / std
        else:
            latest_z_score = np.nan

        max_ts = group["ts"].max()
        recent_cutoff = max_ts - pd.Timedelta(days=window_days)
        recent = group[group["ts"] >= recent_cutoff].copy()

        if recent.empty:
            recent = group.tail(1).copy()

        ooc_rate = float(recent["sensor_ooc"].mean()) if len(recent) else 0.0

        # EWMA trend expressed in z-score/day using only the last slope_window_hours.
        slope_z_per_day = np.nan

        if pd.notna(centerline) and pd.notna(std) and std > 0:
            slope_cutoff = max_ts - pd.Timedelta(hours=slope_window_hours)
            slope_df = group[group["ts"] >= slope_cutoff].copy()

            if len(slope_df) >= 2:
                slope_df = slope_df.sort_values("ts").copy()
                slope_df["ewma"] = slope_df["value"].ewm(alpha=ewma_alpha, adjust=False).mean()

                dt_days = (slope_df["ts"].iloc[-1] - slope_df["ts"].iloc[0]).total_seconds() / 86400.0
                if dt_days > 0:
                    delta_z = (slope_df["ewma"].iloc[-1] - slope_df["ewma"].iloc[0]) / std
                    slope_z_per_day = float(delta_z / dt_days)

        if pd.notna(latest_z_score) and abs(latest_z_score) > 3.0:
            baseline_trend = "ooc"
            health_status = "ooc"
        elif pd.notna(slope_z_per_day) and slope_z_per_day >= drifting_slope_z_per_day:
            baseline_trend = "drifting_up"
            health_status = "attention"
        elif pd.notna(slope_z_per_day) and slope_z_per_day <= -drifting_slope_z_per_day:
            baseline_trend = "drifting_down"
            health_status = "attention"
        elif ooc_rate >= volatile_ooc_rate:
            baseline_trend = "volatile"
            health_status = "attention"
        elif pd.notna(slope_z_per_day) and abs(slope_z_per_day) <= stable_slope_z_per_day and (
            pd.isna(latest_z_score) or abs(latest_z_score) <= 1.0
        ):
            baseline_trend = "stable_baseline"
            health_status = "stable"
        elif pd.notna(latest_z_score) and abs(latest_z_score) > 1.0:
            baseline_trend = "trending_baseline"
            health_status = "attention"
        else:
            baseline_trend = "stable_baseline"
            health_status = "stable"

        return pd.Series(
            {
                "entity": entity,
                "sensor": sensor,
                "latest_value": float(latest["value"]),
                "latest_ewma": latest_ewma,
                "centerline": float(centerline) if pd.notna(centerline) else np.nan,
                "std": float(std) if pd.notna(std) else np.nan,
                "latest_z_score": float(latest_z_score) if pd.notna(latest_z_score) else np.nan,
                f"ooc_rate_{window_days}d": ooc_rate,
                f"ewma_slope_z_per_day_{slope_window_hours}h": float(slope_z_per_day) if pd.notna(slope_z_per_day) else np.nan,
                "baseline_trend": baseline_trend,
                "health_status": health_status,
            }
        )

    out = (
        work.groupby(["entity", "sensor"], dropna=False)
        .apply(_per_sensor)
        .reset_index(drop=True)
    )

    out["_severity_rank"] = out["health_status"].map({"ooc": 0, "attention": 1, "stable": 2}).fillna(3)
    out["_abs_z"] = out["latest_z_score"].abs().fillna(-1)
    out = out.sort_values(["_severity_rank", "_abs_z", "sensor"], ascending=[True, False, True]).reset_index(drop=True)
    out = out.drop(columns=["_severity_rank", "_abs_z"])

    return out
