import matplotlib.pyplot as plt
import pandas as pd

def _latest_nonnull(series: pd.Series):
    s = series.dropna()
    return None if s.empty else s.iloc[-1]
    
def plot_fleet_boxplot(df, job: dict, params: dict, output_path):
    """
    Fleet-level boxplot:
    - x-axis: entity
    - y-axis: sensor values (show_ewma='True' to plot ewma values instead of raw data)
    - Runner applies any desired time slicing BEFORE calling this function.

    Parameters
    ----------
    df : pandas.DataFrame
        Preprocessed dataframe (may include multiple entities for one entity_group + sensor)
    job : dict
        job dict passed from JSON planner (uses filters for title/context)
    params : dict
        plot-level params (legend, y_min/y_max, show_ewma)
    output_path : str or Path
        File path to save the plot
    """

    filters = job["filters"]
    sensor = filters["sensor"]
    entity_group = filters["entity_group"]

    params = params or {}

    legend = bool(params.get("legend", False))
    show_limits = bool(params.get("show_limits", True))
    show_ewma = bool(params.get("show_ewma", False))
    y_min = params.get("y_min", None)
    y_max = params.get("y_max", None)

    # Filter by group + sensor only (defensive)
    chart_df = df[
        (df["entity_group"] == entity_group) &
        (df["sensor"] == sensor)
    ].copy()

    if chart_df.empty:
        raise ValueError(f"No data for entity_group={entity_group}, sensor={sensor}")

    # -----------------------------
    # Extract SPC constants (use latest non-null values)
    # -----------------------------
    centerline = _latest_nonnull(chart_df["centerline"]) if "centerline" in chart_df.columns else None
    ucl = _latest_nonnull(chart_df["ucl"]) if "ucl" in chart_df.columns else None
    lcl = _latest_nonnull(chart_df["lcl"]) if "lcl" in chart_df.columns else None
    
    # Choose series to plot
    if show_ewma and "ewma" in chart_df.columns:
        y_col = "ewma"
        y_label = f"{sensor} (EWMA)"
    elif "value" in chart_df.columns:
        y_col = "value"
        y_label = f"{sensor} (Raw)"
    else:
        raise KeyError("Expected at least one of ['ewma', 'value'] in dataframe")

    chart_df = chart_df.dropna(subset=[y_col])

    if chart_df.empty:
        raise ValueError(f"All values are NaN for y_col={y_col}")

    # Create boxplot data in deterministic order
    entities = sorted(chart_df["entity"].unique())
    data = [chart_df.loc[chart_df["entity"] == e, y_col].values for e in entities]

    plt.figure(figsize=(min(10, 3 * len(entities)), 6))
    ax = plt.gca()

    ax.boxplot(
        data,
        labels=entities,
        showfliers=True
    )
    
    # Limits (optional)
    if show_limits:
        if centerline is not None:
            plt.axhline(centerline, linestyle="--", linewidth=1, color="black", label="Centerline")
        if ucl is not None:
            plt.axhline(ucl, linestyle="--", linewidth=1, color="red", label="UCL")
        if lcl is not None:
            plt.axhline(lcl, linestyle="--", linewidth=1, color="red", label="LCL")
            
    # Axis overrides
    if (y_min is not None) or (y_max is not None):
        ax.set_ylim(bottom=y_min, top=y_max)

    plt.title(f"{entity_group} Fleet | {sensor} | Boxplot")
    plt.xlabel("Entity")
    plt.ylabel(y_label)
    plt.xticks(rotation="vertical")

    # No legend by default; keep option for future (e.g., overlay lines)
    if legend:
        plt.legend(loc="best")

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()