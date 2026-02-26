import matplotlib.pyplot as plt


def plot_spc_time_series(
    df,
    entity_group,
    entity,
    sensor,
    output_path,
    show_raw=True
):
    """
    Generate an SPC-style time series plot for one chart.

    Parameters
    ----------
    df : pandas.DataFrame
        Preprocessed (long-format) dataframe
    entity : str
        Tool identifier (e.g. 'CNC01')
    sensor : str
        Sensor name (e.g. 'vibration_rms')
    output_path : str
        File path to save the plot
    show_raw : bool
        Whether to overlay raw sensor values (faded)
    """

    # -----------------------------
<<<<<<< Updated upstream
=======
    # Interpret job dictionaries
    # -----------------------------
    filters = job["filters"]
    sensor = filters["sensor"]
    entity = filters["entity"]
    entity_group = filters["entity_group"]

    params = params or {}

    # Plot toggles
    show_raw = bool(params.get("show_raw", True))
    show_ewma = bool(params.get("show_ewma", True))
    show_limits = bool(params.get("show_limits", True))
    legend = bool(params.get("legend", True))

    # Axis overrides (optional)
    x_min = params.get("x_min", None)  # datetime string
    x_max = params.get("x_max", None)  # datetime string
    y_min = params.get("y_min", None)  # float
    y_max = params.get("y_max", None)  # float

    # -----------------------------
>>>>>>> Stashed changes
    # Filter to chart of interest
    # -----------------------------
    chart_df = df[
        (df["entity_group"] == entity_group) &
        (df["entity"] == entity) &
        (df["sensor"] == sensor)
    ].copy()

    if chart_df.empty:
        raise ValueError(
            f"No data for entity ={entity}, sensor={sensor}"
        )

    chart_df = chart_df.sort_values("ts")

    # -----------------------------
    # Extract SPC constants
    # -----------------------------
<<<<<<< Updated upstream
    centerline = chart_df["centerline"].iloc[0]
    ucl = chart_df["ucl"].iloc[0]
    lcl = chart_df["lcl"].iloc[0]
=======
    centerline = _latest_nonnull(chart_df["centerline"]) if "centerline" in chart_df.columns else None
    ucl = _latest_nonnull(chart_df["ucl"]) if "ucl" in chart_df.columns else None
    lcl = _latest_nonnull(chart_df["lcl"]) if "lcl" in chart_df.columns else None

    have_limits = (ucl is not None) or (lcl is not None)
>>>>>>> Stashed changes

    # -----------------------------
    # Plot
    # -----------------------------
<<<<<<< Updated upstream
    plt.figure(figsize=(8,5))

    if show_raw:
=======
    plt.figure(figsize=(8, 5))
    
    # Violation mask (expected from preprocess; computed from RAW vs limits with null-safe logic)
    if "spc_violation" in chart_df.columns:
        vmask = chart_df["spc_violation"].fillna(False).astype(bool)
    else:
        vmask = None
    
    # Raw points
    if show_raw and "value" in chart_df.columns:
>>>>>>> Stashed changes
        plt.scatter(
            chart_df["ts"],
            chart_df["value"],
            alpha=0.2,
            s=10,
            label="Raw"
        )
<<<<<<< Updated upstream

    plt.plot(
        chart_df["ts"],
        chart_df["ewma"],
        linewidth=2,
        label="EWMA"
    )

    plt.axhline(centerline, linestyle="--", linewidth=1, color="black", label="Centerline")
    plt.axhline(ucl, linestyle="--", linewidth=1, color="red", label="UCL (+3σ)")
    plt.axhline(lcl, linestyle="--", linewidth=1, color="red", label="LCL (-3σ)")
=======
    
        # Highlight raw violations (single-entity: yes)
        if vmask is not None and vmask.any():
            v = chart_df[vmask]
            plt.scatter(
                v["ts"],
                v["value"],
                s=30,
                marker="o",
                label="Violation"
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
        if vmask is not None and vmask.any() and show_raw == False:
            v = chart_df[vmask]
            plt.scatter(
                v["ts"],
                v["ewma"],
                s=30,
                marker="o",
                label="_nolegend_"
            )

    # Limits (optional)
    if show_limits:
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
>>>>>>> Stashed changes

    # -----------------------------
    # Formatting
    # -----------------------------
    plt.title(f"{entity} | {sensor} | Normal Mode SPC")
    plt.xticks(rotation='vertical')
    plt.xlabel("Timestamp")
    plt.ylabel(sensor)
    plt.legend(loc="best")
    plt.tight_layout()

    plt.savefig(output_path)
    plt.close()
