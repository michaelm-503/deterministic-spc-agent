import pandas as pd


def preprocess_ewma_spc(df, job: dict | None = None, params: dict | None = None):
    """
    Preprocess sensor data for SPC visualization.

    Steps:
    1) Filter to operating_mode == 'normal'
    2) Compute EWMA per (entity, sensor), resetting after maintenance
       - Reset when hours_since_maintenance == 0
    3) Compute SPC violation flag from RAW value vs limits (null-safe)
       pass iff (value <= UCL OR UCL is null) AND (value >= LCL OR LCL is null)

    Notes:
    - EWMA is a visual aid; it does NOT drive violation calculation.
    - Limits may be one-sided (UCL-only or LCL-only). Missing sides auto-pass.

    Returns
    -------
    pandas.DataFrame
        Same dataframe with added columns:
        - ewma
        - spc_violation (bool)
    """

    job = job or {}
    params = params or {}

    alpha = float(params.get("ewma_alpha", 0.2))
    if not (0 < alpha <= 1.0):
        raise ValueError(f"ewma_alpha must be in (0, 1], got {alpha}")

    # -----------------------------
    # Required columns (minimal)
    # -----------------------------
    required = {
        "entity",
        "entity_group",
        "ts",
        "operating_mode",
        "hours_since_maintenance",
        "sensor",
        "value",
    }
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns for ewma_spc preprocess: {sorted(missing)}")

    # Ensure limit columns exist (values can be null => auto-pass)
    if "ucl" not in df.columns:
        df = df.assign(ucl=pd.NA)
    if "lcl" not in df.columns:
        df = df.assign(lcl=pd.NA)

    # Optional centerline: nice for plotting, not required
    if "centerline" not in df.columns:
        df = df.assign(centerline=pd.NA)

    # -----------------------------
    # 1) Filter to NORMAL operation
    # -----------------------------
    df = df[df["operating_mode"] == "normal"].copy()
    if df.empty:
        # No normal-mode data: return empty with required output columns
        df["ewma"] = pd.Series(dtype="float64")
        df["spc_violation"] = pd.Series(dtype="bool")
        return df

    # Timestamp type safety
    df["ts"] = pd.to_datetime(df["ts"])

    # Deterministic ordering
    df = df.sort_values(["entity", "sensor", "ts"]).copy()

    # -----------------------------
    # 2) EWMA with maintenance reset
    # -----------------------------
    df["maintenance_block"] = (
        df.groupby(["entity", "sensor"])["hours_since_maintenance"]
          .transform(lambda s: (s == 0).cumsum())
    )

    df["ewma"] = (
        df.groupby(["entity", "sensor", "maintenance_block"])["value"]
          .transform(lambda s: s.ewm(alpha=alpha, adjust=False).mean())
    )

    df = df.drop(columns=["maintenance_block"])

    # -----------------------------
    # 3) SPC violation flag from RAW value vs limits (null-safe)
    # -----------------------------
    ucl_ok = df["ucl"].isna() | (df["value"] <= df["ucl"])
    lcl_ok = df["lcl"].isna() | (df["value"] >= df["lcl"])
    df["spc_violation"] = ~(ucl_ok & lcl_ok)

    return df