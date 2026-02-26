import pandas as pd
import matplotlib.pyplot as plt


def _latest_nonnull(series: pd.Series):
    s = series.dropna()
    return None if s.empty else s.iloc[-1]


def plot_spc_time_series(df, job: dict, params: dict | None, output_path):
    """
    Single-entity SPC time series plot.

    Expected columns in df (after preprocess):
      - ts (datetime or parseable)
      - entity_group, entity, sensor
      - value (raw)
      - ewma (optional but expected when show_ewma=True)
      - ucl/lcl/centerline (optional; may be null)
      - spc_violation (bool; expected from preprocess, computed from RAW vs limits)

    Parameters
    ----------
    df : pandas.DataFrame
    job : dict
        Job dict from plan (must contain filters with entity_group/entity/sensor)
    params : dict
        Plot-level params. Supported:
          - show_raw (bool, default False)
          - show_ewma (bool, default True)
          - show_limits (bool, default True)
          - legend (bool, default True)
          - x_min, x_max (datetime strings)
          - y_min, y_max (floats)
    output_path : str | Path
    """
    params = params or {}

    # Plot toggles
    show_raw = bool(params.get("show_raw", False))
    show_ewma = bool(params.get("show_ewma", True))
    show_limits = bool(params.get("show_limits", True))
    legend = bool(params.get("legend", True))

    # Axis overrides
    x_min = params.get("x_min", None)
    x_max = params.get("x_max", None)
    y_min = params.get("y_min", None)
    y_max = params.get("y_max", None)

    # -----------------------------
    # Interpret job filters
    # -----------------------------
    filters = (job.get("filters") or {})
    entity_group = filters.get("entity_group")
    entity = filters.get("entity")
    sensor = filters.get("sensor")

    if entity_group is None or entity is None or sensor is None:
        raise KeyError(
            "spc_time_series requires filters.entity_group, filters.entity, and filters.sensor. "
            f"Got: entity_group={entity_group}, entity={entity}, sensor={sensor}"
        )

    # -----------------------------
    # Filter to chart
    # -----------------------------
    chart_df = df.copy()

    if "ts" not in chart_df.columns:
        raise KeyError("spc_time_series expected a 'ts' column in dataframe.")
    chart_df["ts"] = pd.to_datetime(chart_df["ts"])

    for col in ["entity_group", "entity", "sensor"]:
        if col not in chart_df.columns:
            raise KeyError(f"spc_time_series expected column '{col}' in dataframe.")

    chart_df = chart_df[
        (chart_df["entity_group"] == entity_group) &
        (chart_df["entity"] == entity) &
        (chart_df["sensor"] == sensor)
    ].copy()

    if chart_df.empty:
        raise ValueError(f"No data for entity_group={entity_group}, entity={entity}, sensor={sensor}")

    chart_df = chart_df.sort_values("ts")

    # -----------------------------
    # Limits (use latest non-null values)
    # -----------------------------
    centerline = _latest_nonnull(chart_df["centerline"]) if "centerline" in chart_df.columns else None
    ucl = _latest_nonnull(chart_df["ucl"]) if "ucl" in chart_df.columns else None
    lcl = _latest_nonnull(chart_df["lcl"]) if "lcl" in chart_df.columns else None
    have_limits = (ucl is not None) or (lcl is not None)

    # Violation mask (expected from preprocess; RAW vs limits with null-safe logic)
    vmask = chart_df["spc_violation"].fillna(False).astype(bool) if "spc_violation" in chart_df.columns else None

    # -----------------------------
    # Plot
    # -----------------------------
    plt.figure(figsize=(8, 5))

    # Raw points
    if show_raw:
        if "value" not in chart_df.columns:
            raise KeyError("show_raw=True but 'value' column not found in dataframe")
        plt.scatter(
            chart_df["ts"],
            chart_df["value"],
            alpha=0.2,
            s=10,
            label="Raw"
        )
        # Highlight raw violations (single-entity: yes)
        if vmask is not None and vmask.any():
            v = chart_df[vmask]
            plt.scatter(
                v["ts"],
                v["value"],
                s=30,
                marker="o",
                label="_nolegend_"
            )

    # EWMA line
    if show_ewma:
        if "ewma" not in chart_df.columns:
            raise KeyError("show_ewma=True but 'ewma' column not found in dataframe")
        plt.plot(
            chart_df["ts"],
            chart_df["ewma"],
            linewidth=2,
            label="EWMA"
        )
        # Highlight EWMA at violation timestamps (single-entity: yes)
        if vmask is not None and vmask.any():
            v = chart_df[vmask]
            plt.scatter(
                v["ts"],
                v["ewma"],
                s=30,
                marker="o",
                label="_nolegend_"
            )

    # Limits (do not include in legend)
    if show_limits and have_limits:
        if centerline is not None:
            plt.axhline(centerline, linestyle="--", linewidth=1, color="black", label="_nolegend_")
        if ucl is not None:
            plt.axhline(ucl, linestyle="--", linewidth=1, color="red", label="_nolegend_")
        if lcl is not None:
            plt.axhline(lcl, linestyle="--", linewidth=1, color="red", label="_nolegend_")

    # -----------------------------
    # Axis overrides (rendering only)
    # -----------------------------
    if x_min is not None:
        plt.xlim(left=pd.to_datetime(x_min))
    if x_max is not None:
        plt.xlim(right=pd.to_datetime(x_max))
    if (y_min is not None) or (y_max is not None):
        plt.ylim(bottom=y_min, top=y_max)

    # -----------------------------
    # Formatting
    # -----------------------------
    plt.title(f"{entity} | {sensor} | Normal Mode SPC")
    plt.xticks(rotation="vertical")
    plt.xlabel("Timestamp")
    plt.ylabel(sensor)

    if legend:
        plt.legend(loc="best")

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()