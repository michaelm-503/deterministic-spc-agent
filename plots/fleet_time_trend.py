import matplotlib.pyplot as plt
import pandas as pd

def _latest_nonnull(series: pd.Series):
    s = series.dropna()
    return None if s.empty else s.iloc[-1]

def plot_fleet_time_trend(df, job: dict, params: dict, output_path):
    """
    Fleet-level time trend:
    - One ewma trace per entity
    - Optional raw scatter per entity
    """

    filters = job["filters"]
    sensor = filters["sensor"]
    entity_group = filters["entity_group"]

    params = params or {}

    show_raw = bool(params.get("show_raw", False))
    show_ewma = bool(params.get("show_ewma", True))
    show_limits = bool(params.get("show_limits", True))
    legend = bool(params.get("legend", True))

    x_min = params.get("x_min", None)
    x_max = params.get("x_max", None)
    y_min = params.get("y_min", None)
    y_max = params.get("y_max", None)

    # Filter by group + sensor only
    chart_df = df[
        (df["entity_group"] == entity_group) &
        (df["sensor"] == sensor)
    ].copy()

    if chart_df.empty:
        raise ValueError(f"No data for entity_group={entity_group}, sensor={sensor}")

    chart_df["ts"] = pd.to_datetime(chart_df["ts"])
    chart_df = chart_df.sort_values("ts")

    plt.figure(figsize=(10, 6))
    ax = plt.gca()

    # Extract SPC constants (use latest non-null values)
    centerline = _latest_nonnull(chart_df["centerline"]) if "centerline" in chart_df.columns else None
    ucl = _latest_nonnull(chart_df["ucl"]) if "ucl" in chart_df.columns else None
    lcl = _latest_nonnull(chart_df["lcl"]) if "lcl" in chart_df.columns else None

    violation_legend = 'Violation'
    
    # Plot one entity at a time
    for entity in sorted(chart_df["entity"].unique()):
        entity_df = chart_df[chart_df["entity"] == entity].copy()
    
        # Get consistent color for this entity
        color = ax._get_lines.get_next_color()
    
        if show_raw and "value" in entity_df.columns:
            ax.scatter(
                entity_df["ts"],
                entity_df["value"],
                alpha=0.2,
                s=10,
                color=color,
                label="_nolegend_"
            )
    
        if show_ewma:
            if "ewma" not in entity_df.columns:
                raise KeyError("Expected 'ewma' column for fleet_time_trend")
    
            ax.plot(
                entity_df["ts"],
                entity_df["ewma"],
                linewidth=2,
                color=color,
                label=entity
            )

        # ---- Violations: derived from RAW (spc_violation), highlighted on EWMA only (fleet rule) ----
        if "spc_violation" in entity_df.columns:
            vmask = entity_df["spc_violation"].fillna(False).astype(bool)
            if vmask.any():
                v = entity_df[vmask]
                ax.scatter(
                    v["ts"],
                    v["ewma"],
                    s=30,
                    marker="o",
                    color='black',
                    label=violation_legend
                )
                violation_legend="_nolegend_"
   
    # Limits (optional)
    if show_limits:
        if centerline is not None:
            plt.axhline(centerline, linestyle="--", linewidth=1, color="black", label="_nolegend_")
        if ucl is not None:
            plt.axhline(ucl, linestyle="--", linewidth=1, color="red", label="_nolegend_")
        if lcl is not None:
            plt.axhline(lcl, linestyle="--", linewidth=1, color="red", label="_nolegend_")
            
    # Axis overrides
    if x_min is not None:
        ax.set_xlim(left=pd.to_datetime(x_min))
    if x_max is not None:
        ax.set_xlim(right=pd.to_datetime(x_max))
    if (y_min is not None) or (y_max is not None):
        ax.set_ylim(bottom=y_min, top=y_max)

    plt.title(f"{entity_group} Fleet | {sensor} | Time Trend")
    plt.xlabel("Timestamp")
    plt.ylabel(sensor)
    plt.xticks(rotation="vertical")

    if legend:
        plt.legend(loc="best")

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()