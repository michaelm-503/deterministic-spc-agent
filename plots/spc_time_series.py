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
    centerline = chart_df["centerline"].iloc[0]
    ucl = chart_df["ucl"].iloc[0]
    lcl = chart_df["lcl"].iloc[0]

    # -----------------------------
    # Plot
    # -----------------------------
    plt.figure(figsize=(8,5))

    if show_raw:
        plt.scatter(
            chart_df["ts"],
            chart_df["value"],
            alpha=0.2,
            s=10,
            label="Raw"
        )

    plt.plot(
        chart_df["ts"],
        chart_df["ewma"],
        linewidth=2,
        label="EWMA"
    )

    plt.axhline(centerline, linestyle="--", linewidth=1, color="black", label="Centerline")
    plt.axhline(ucl, linestyle="--", linewidth=1, color="red", label="UCL (+3σ)")
    plt.axhline(lcl, linestyle="--", linewidth=1, color="red", label="LCL (-3σ)")

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
