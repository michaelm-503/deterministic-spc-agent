import pandas as pd


def compute_fleet_ooc_summary(df: pd.DataFrame, job: dict, params: dict | None = None) -> pd.DataFrame:
    """
    Compute fleet-level %OOC summary over the provided dataframe window.

    Assumptions
    ----------
    - Runner applies any desired time slicing BEFORE calling this function.
    - df includes multiple entities for one entity_group + sensor.
    - OOC is defined by SPC limits; we use:
        - 'spc_violation' if present
        - otherwise compute from ewma/value vs ucl/lcl if available
    - If limits are missing, %OOC will be 0% for that entity.

    Output
    ------
    DataFrame with:
      entity, total_points, ooc_points, percent_ooc
    """

    params = params or {}
    
    filters = job["filters"]
    sensor = filters.get("sensor")
    entity_group = filters.get("entity_group")

    chart_df = df[
        (df["entity_group"] == entity_group) &
        (df["sensor"] == sensor)
    ].copy()

    if chart_df.empty:
        raise ValueError(f"No data for entity_group={entity_group}, sensor={sensor}")

    # %OOC must always be computed from RAW data.
    if "value" not in chart_df.columns:
        raise KeyError("%OOC requires raw 'value' column in dataframe")
    
    # Determine violation boolean series using:
    #   pass if (value <= UCL OR UCL is null) AND (value >= LCL OR LCL is null)
    # Missing limits are treated as automatic pass (common to have only one bound).
    if "ucl" in chart_df.columns:
        pass_ucl = chart_df["ucl"].isna() | (chart_df["value"] <= chart_df["ucl"])
    else:
        pass_ucl = pd.Series(True, index=chart_df.index)
    
    if "lcl" in chart_df.columns:
        pass_lcl = chart_df["lcl"].isna() | (chart_df["value"] >= chart_df["lcl"])
    else:
        pass_lcl = pd.Series(True, index=chart_df.index)
    
    violation = ~(pass_ucl & pass_lcl)
    chart_df = chart_df.assign(_violation=violation)

    def _agg(group: pd.DataFrame) -> pd.Series:
        total = int(len(group))

        # If violations are NA (no limits), return NA metrics
        if group["_violation"].isna().all():
            return pd.Series(
                {
                    "total_points": total,
                    "ooc_points": pd.NA,
                    "percent_ooc": pd.NA,
                }
            )

        ooc = int(group["_violation"].sum())
        pct = 100 * (ooc / total) if total > 0 else pd.NA
        return pd.Series(
            {
                "total_points": total,
                "ooc_points": ooc,
                "percent_ooc": pct,
            }
        )

    summary = (
        chart_df
        .groupby("entity", dropna=False)
        .apply(_agg)
        .reset_index()
        .sort_values("entity")
        .reset_index(drop=True)
    )

    # Add context columns (nice for CSVs)
    summary.insert(0, "entity_group", entity_group)
    summary.insert(1, "sensor", sensor)

    return summary


def write_fleet_ooc_summary_csv(df: pd.DataFrame, job: dict, params: dict | None, output_path) -> pd.DataFrame:
    """
    Convenience wrapper: compute summary and write to CSV.
    Returns the summary DataFrame.
    """
    summary = compute_fleet_ooc_summary(df, job=job, params=params)
    summary.to_csv(output_path, index=False)
    return summary