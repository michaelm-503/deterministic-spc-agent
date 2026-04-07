from __future__ import annotations

from pathlib import Path
import pandas as pd


def write_multi_sensor_health_table(
    df: pd.DataFrame,
    job: dict,
    params: dict | None,
    output_path: str | Path,
) -> pd.DataFrame:
    """
    Pass-through writer for multi-sensor health summary output.
    """
    expected = {
        "entity",
        "sensor",
        "latest_value",
        "latest_ewma",
        "centerline",
        "std",
        "latest_z_score",
        "baseline_trend",
        "health_status",
    }
    missing = expected - set(df.columns)
    if missing:
        raise KeyError(
            "Multi-sensor health table expected pre-summarized preprocess output. "
            f"Missing columns: {sorted(missing)}"
        )

    out = df.drop(["latest_value", "latest_ewma", "centerline", "std"], axis=1).copy()
    out.to_csv(Path(output_path), index=False)
    return out
