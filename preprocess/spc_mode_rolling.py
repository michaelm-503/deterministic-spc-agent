import pandas as pd
from pathlib import Path

def preprocess(df_long, processed_dir="data/processed"):
    """
    Preprocess sensor data for SPC analysis.

    Steps:
    1. Filter to operating_mode == 'normal' (verify)
    2. Compute EWMA rolling average per chart
       - Reset after maintenance (hours_since_maintenance == 0)
       - No NaNs retained
    3. SPC violation flag using EWMA vs. SPC limits
    """

    # -----------------------------
    # 0. Required Columns
    # -----------------------------
    required = {
        'entity', 'entity_group', 'ts', 'operating_mode', 'hours_since_maintenance',
        'failure_type', 'sensor', 'value', 'ucl', 'centerline', 'lcl'
    }
    
    missing = required - set(df_long.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")


    # -----------------------------
    # 1. Filter to NORMAL operation (verify)
    # -----------------------------
    
    df_long = df_long[df_long["operating_mode"] == "normal"].copy()

    # -----------------------------
    # 2. EWMA with maintenance reset
    # -----------------------------

    EWMA_ALPHA = 0.2
    
    # Deterministic ordering
    df_long = df_long.sort_values(['entity', 'sensor', 'ts']).copy()
    
    # Define maintenance blocks per chart (reset when hours_since_maintenance == 0)
    df_long['maintenance_block'] = (
        df_long.groupby(['entity', 'sensor'])['hours_since_maintenance']
              .transform(lambda s: (s == 0).cumsum())
    )
    
    # EWMA per (entity_group, sensor, maintenance_block)
    # transform guarantees alignment and preserves all columns
    df_long['ewma'] = (
        df_long.groupby(['entity', 'sensor', 'maintenance_block'])['value']
              .transform(lambda s: s.ewm(alpha=EWMA_ALPHA, adjust=False).mean())
    )
    
    # Generate SPC violation column
    
    df_long['spc_violation'] = (
        (df_long['ewma'] > df_long['ucl']) |
        (df_long['ewma'] < df_long['lcl'])
    )
    
    df_long = df_long.drop(columns=['maintenance_block'])

    # -----------------------------
    # 3. SPC violation flag using EWMA
    # -----------------------------

<<<<<<< Updated upstream
    df_long["spc_violation"] = (
        (df_long["ewma"] > df_long["ucl"]) |
        (df_long["ewma"] < df_long["lcl"])
    )
=======
    # expects columns: value, ucl, lcl
    ucl_ok = df["ucl"].isna() | (df["value"] <= df["ucl"])
    lcl_ok = df["lcl"].isna() | (df["value"] >= df["lcl"])
    df["spc_violation"] = ~(ucl_ok & lcl_ok)
>>>>>>> Stashed changes


    return df_long
