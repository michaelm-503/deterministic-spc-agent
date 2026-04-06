from __future__ import annotations

from pathlib import Path
import pandas as pd


def write_pm_event_summary_table(df: pd.DataFrame, job: dict, params: dict | None, output_path: str | Path) -> pd.DataFrame:
    """
    Pass-through table writer for PM-event summaries.

    Assumes the preprocess stage has already produced one row per PM event with:
    - entity
    - ts
    - hours_pre_pm
    - failure_type
    - ooc_sensors
    """
    params = params or {}
    expected = {"entity", "ts", "hours_pre_pm", "failure_type", "ooc_sensors"}
    missing = expected - set(df.columns)
    if missing:
        raise KeyError(
            "PM event summary table expected pre-summarized preprocess output. "
            f"Missing columns: {sorted(missing)}"
        )

    out = df.copy()
    out = out.rename(columns={"ts": "timestamp"})
    out = out.rename(columns={"hours_pre_pm": "hours_since_last_maintenance"})
    out.to_csv(Path(output_path), index=False)
    return out
