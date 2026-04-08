from __future__ import annotations

import json
import random
import subprocess
import sys
import re
import base64
import mimetypes
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spc_agent.agent.agent_runner import ask_agent


st.set_page_config(
    page_title="Deterministic SPC Agent",
    page_icon="📈",
    layout="wide",
)

# -----------------------------
# Verbose Debugging
# -----------------------------

verbose = False

# -----------------------------
# Setup helpers
# -----------------------------
def check_setup(project_root: Path) -> tuple[bool, list[Path]]:
    required = [
        project_root / "data" / "mfg.duckdb",
        project_root / "planner" / "metadata" / "catalog.json",
    ]
    missing = [p for p in required if not p.exists()]
    return (len(missing) == 0, missing)


def ensure_setup(project_root: Path) -> tuple[bool, str]:
    ok, missing = check_setup(project_root)
    if ok:
        return True, "Setup already complete."

    try:
        subprocess.run(
            [sys.executable, "scripts/setup_data.py", "--project-root", str(project_root)],
            check=True,
            cwd=str(project_root),
        )
        subprocess.run(
            [sys.executable, "scripts/build_planner_catalog.py", "--project-root", str(project_root)],
            check=True,
            cwd=str(project_root),
        )
    except subprocess.CalledProcessError as e:
        return False, f"Setup failed while running scripts: {e}"

    ok, missing = check_setup(project_root)
    if not ok:
        missing_str = ", ".join(str(p) for p in missing)
        return False, f"Setup completed but required artifacts are still missing: {missing_str}"

    return True, "Setup completed successfully."


def _default_project_root() -> str:
    return str(Path.cwd().resolve())


# -----------------------------
# UI helpers
# -----------------------------
def _load_markdown_file(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return f"File not found: {path}"    



def _markdown_with_embedded_local_images(md_path: Path) -> str:
    """
    Load markdown and replace local image links with base64 data URIs
    so that st.markdown() can render them inline.

    Remote image URLs are left unchanged.
    """
    if not md_path.exists():
        return f"File not found: {md_path}"

    text = md_path.read_text()
    image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')

    def _replace(match: re.Match) -> str:
        alt_text = match.group(1)
        raw_path = match.group(2).strip()

        # Leave remote images alone
        if raw_path.startswith("http://") or raw_path.startswith("https://"):
            return match.group(0)

        image_path = (md_path.parent / raw_path).resolve()
        if not image_path.exists():
            return match.group(0)

        mime_type, _ = mimetypes.guess_type(str(image_path))
        if mime_type is None or not mime_type.startswith("image/"):
            return match.group(0)

        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{encoded}"

        return f"![{alt_text}]({data_uri})"

    return image_pattern.sub(_replace, text)
    

# -----------------------------
# Prompt helpers
# -----------------------------
def _load_demo_prompts(project_root: Path, planner_file: str) -> list[str]:
    planner_path = (project_root / planner_file).resolve() if not Path(planner_file).is_absolute() else Path(planner_file)
    if not planner_path.exists():
        return []
    data = json.loads(planner_path.read_text())
    runs = data.get("runs", []) or []
    prompts = [str(run.get("request_text", "")).strip() for run in runs if run.get("request_text")]
    return [p for p in prompts if p]


def _set_random_demo_prompt(demo_prompts: list[str]) -> None:
    if demo_prompts:
        st.session_state["prompt_input"] = random.choice(demo_prompts)


def _make_replot_prompt(builder_key: str) -> str:
    prompts = {
        "hide_legend": "Remove the legend from the last plot.",
        "entity_filter": "Filter the last plot for <entity(s)>",
        "last_3d": "Zoom in on the last 3 days.",
        "last_7d": "Replot the previous result for the last 7 days.",
        "add_ooc_summary_3d": "Add an OOC summary table for the last 3 days to the previous result.",
        "boxplot_only": "Add a boxplot to the previous result.",
    }
    return prompts.get(builder_key, "")


def _apply_replot_builder_prompt() -> None:
    builder_key = st.session_state.get("replot_builder_choice")
    prompt = _make_replot_prompt(builder_key)
    if prompt:
        st.session_state["prompt_input"] = prompt
        st.session_state["force_json_upload"] = True


# -----------------------------
# Result / history helpers
# -----------------------------
def _extract_run_timestamp(result: Any) -> str:
    if getattr(result, "run_dir", None):
        return Path(result.run_dir).name
    return "unsupported"


def _extract_plan_jobs(plan: dict | None) -> list[dict]:
    if not isinstance(plan, dict):
        return []

    if "jobs" in plan and isinstance(plan.get("jobs"), list):
        return plan["jobs"]

    runs = plan.get("runs", [])
    if isinstance(runs, list) and runs:
        first = runs[0]
        if isinstance(first, dict) and isinstance(first.get("jobs"), list):
            return first["jobs"]

    return []


def _extract_job_ids(plan: dict | None) -> list[str]:
    jobs = _extract_plan_jobs(plan)
    out = []
    for job in jobs:
        job_id = job.get("job_id")
        if job_id:
            out.append(str(job_id))
    return out


def _extract_run_json(plan: dict | None) -> str | None:
    if not isinstance(plan, dict):
        return None

    # Replot / single-plan shape
    if "jobs" in plan:
        return json.dumps(plan, indent=2)

    # Plan library shape
    runs = plan.get("runs", [])
    if isinstance(runs, list) and len(runs) == 1 and isinstance(runs[0], dict):
        return json.dumps(runs[0], indent=2)

    # Fallback: keep full plan if shape is still valid JSON
    return json.dumps(plan, indent=2)


def _selected_history_item() -> dict | None:
    history = st.session_state.get("history", [])
    idx = st.session_state.get("selected_history_index", 0)
    if not history:
        return None
    if idx < 0 or idx >= len(history):
        return history[0]
    return history[idx]


def _select_history_item(index: int) -> None:
    st.session_state["selected_history_index"] = index
    st.session_state["context_history_index"] = index
    st.session_state["force_json_upload"] = True


def _read_text_if_exists(path_str: str | None) -> str | None:
    if not path_str:
        return None
    path = Path(path_str)
    if path.exists() and path.is_file():
        return path.read_text()
    return None


def _collect_output_artifacts(result: Any) -> tuple[list[Path], list[Path]]:
    if getattr(result, "run_dir", None) is None:
        return [], []

    root = Path(result.run_dir)
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    
    # CSV files that are pipeline artifacts, not user-facing table outputs
    excluded_csv_names = {
        "extracted_data.csv",
        "processed_data.csv",
    }

    image_paths: list[Path] = []
    table_paths: list[Path] = []

    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            suffix = path.suffix.lower()
            name = path.name.lower()

            if suffix in image_exts:
                image_paths.append(path)

            elif suffix == ".csv":
                if name in excluded_csv_names:
                    continue
                table_paths.append(path)

    return sorted(image_paths), sorted(table_paths)


def _build_augmented_prompt(base_prompt: str, selected_item: dict | None, force_json_upload: bool) -> str:
    prompt = base_prompt.strip()
    if not force_json_upload or not selected_item:
        return prompt

    run_json = selected_item.get("run_json")
    run_dir = getattr(selected_item.get("result"), "run_dir", None)
    
    if not run_json or not run_dir:
        return prompt

    return (
        f"{prompt}\n\n"
        f"Use this run_dir for replot requests: {run_dir}\n\n"
        f"Previous execution run JSON:\n"
        f"```json\n{run_json}\n```"
    )


def _mode_label(result: Any) -> str:
    if getattr(result, "unsupported_request", False):
        return "Unsupported"
    plan = getattr(result, "plan", None)
    if isinstance(plan, dict) and plan.get("mode") == "replot":
        return "Replot"
    return "Execution"


def _sync_force_json_context() -> None:
    history = st.session_state.get("history", [])
    if st.session_state.get("force_json_upload"):
        if st.session_state.get("context_history_index") is None and history:
            st.session_state.context_history_index = 0
    else:
        st.session_state.context_history_index = None
        
        
def _compute_active_context() -> dict | None:
    history = st.session_state.get("history", [])
    idx = st.session_state.get("context_history_index")

    if idx is not None and history and 0 <= idx < len(history):
        return history[idx]

    return None


# -----------------------------
# Rendering
# -----------------------------
def _render_header() -> None:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.title("Deterministic SPC Agent")
        st.caption("Deterministic SPC analytics powered by structured AI planning")
    with c2:
        st.markdown(
            """
<a href="https://github.com/michaelm-503/deterministic-spc-agent" target="_blank">GitHub Home</a>
&nbsp;•&nbsp;
<a href="https://michaelm-503.github.io" target="_blank">About the Author</a>
            """,
            unsafe_allow_html=True,
        )
    st.divider()


def _render_active_context(ctx: dict | None) -> None:
    if not ctx:
        return

    timestamp = ctx.get("timestamp", "unknown")
    mode = ctx.get("mode", "Execution")
    job_ids = ctx.get("job_ids", [])

    st.info(
        f"Selected context: **{mode}** run `{timestamp}`"
        + (f" | Jobs: `{', '.join(job_ids)}`" if job_ids else "")
    )


def _render_outputs(result: Any) -> None:
    image_paths, table_paths = _collect_output_artifacts(result)

    if not image_paths and not table_paths:
        return

    st.subheader("Outputs")

    for image_path in image_paths:
        st.image(str(image_path), caption=image_path.name, width="content")

    for table_path in table_paths:
        st.write(f"**{table_path.name}**")
        try:
            df = pd.read_csv(table_path)
            st.dataframe(_style_output_table(df), width="stretch")
        except Exception as e:
            st.warning(f"Could not load table {table_path.name}: {e}")


def _render_result(result: Any) -> None:
    if getattr(result, "unsupported_request", False):
        st.warning(f"Unsupported request: {result.unsupported_reason}")

    if getattr(result, "recovery_used", False):
        st.info("Recovery pass used prior run context.")

    _render_outputs(result)

    if getattr(result, "plan", None) is not None:
        with st.expander("Final JSON plan", expanded=True):
            st.code(json.dumps(result.plan, indent=2), language="json")

    summary_text = _read_text_if_exists(str(getattr(result, "run_summary_path", None)))
    if summary_text:
        with st.expander("run_summary.md", expanded=False):
            st.markdown(summary_text)

    with st.expander("Run metadata", expanded=False):
        st.write(f"**Mode:** {_mode_label(result)}")
        st.write(f"**Planner backend:** {getattr(result, 'planner_backend', 'unknown')}")
        if getattr(result, "planner_context", None):
            st.write(f"**Planner context:** `{result.planner_context}`")
        if getattr(result, "run_dir", None):
            st.write(f"**Run directory:** `{result.run_dir}`")
        if getattr(result, "verification_summary", None):
            st.code(result.verification_summary)


# -----------------------------
# Guided demo helpers
# -----------------------------
def _start_guided_demo(demo_prompts: list[str]) -> None:
    step = st.session_state.get("guided_demo_step", 0)

    # Steps 0-2: canonical gallery prompts
    if step in (0, 1, 2):
        if len(demo_prompts) > step:
            st.session_state["prompt_input"] = demo_prompts[step]
            st.session_state["force_json_upload"] = False
            st.session_state["context_history_index"] = None
            st.session_state["run_requested_from_guided_demo"] = True
        return

    # Steps 3-5: contextual follow-ups
    history = st.session_state.get("history", [])
    if not history:
        return

    st.session_state["force_json_upload"] = False     #force_json_upload=True to improve success rate for demo of conversational prompts.
    st.session_state["context_history_index"] = 0

    if step == 3:
        st.session_state["prompt_input"] = "How is the tool doing now?"
        st.session_state["run_requested_from_guided_demo"] = True
        return

    if step == 4:
        st.session_state["prompt_input"] = "Plot ambient temp"
        st.session_state["run_requested_from_guided_demo"] = True
        return

    if step == 5:
        st.session_state["prompt_input"] = "Zoom in on just the last 2 days."
        st.session_state["run_requested_from_guided_demo"] = True
        return


def _guided_demo_label() -> str:
    step = st.session_state.get("guided_demo_step", 0)

    labels = {
        0: "▶ Run Guided Demo",
        1: "▶ Continue Guided Demo",
        2: "▶ Continue Guided Demo",
        3: "▶ Continue Guided Demo",
        4: "▶ Continue Guided Demo",
        5: "▶ Continue Guided Demo",
    }
    return labels.get(step, "")


# -----------------------------
# Conditional Formatting
# -----------------------------
def _style_output_table(df: pd.DataFrame):
    """
    Apply lightweight conditional formatting for supported summary tables.

    Current rules
    -------------
    - health_status != stable -> orange row accent
    - baseline_trend != stable_baseline -> orange row accent
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    if "health_status" not in df.columns and "baseline_trend" not in df.columns:
        return df

    def _row_style(row: pd.Series) -> list[str]:
        highlight = False

        if "health_status" in row.index and str(row["health_status"]) != "stable":
            highlight = True
        if "baseline_trend" in row.index and str(row["baseline_trend"]) != "stable_baseline":
            highlight = True

        if highlight:
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


# -----------------------------
# Session state init
# -----------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_history_index" not in st.session_state:
    st.session_state.selected_history_index = 0
if "context_history_index" not in st.session_state:
    st.session_state.context_history_index = None
if "prompt_input" not in st.session_state:
    st.session_state.prompt_input = ""
if "force_json_upload" not in st.session_state:
    st.session_state.force_json_upload = False
if "reset_force_json_upload" not in st.session_state:
    st.session_state.reset_force_json_upload = False
if "guided_demo_step" not in st.session_state:
    st.session_state.guided_demo_step = 0
if "run_requested_from_guided_demo" not in st.session_state:
    st.session_state.run_requested_from_guided_demo = False
    
# -----------------------------
# Header
# -----------------------------
_render_header()

tab_agent, tab_dataset, tab_project = st.tabs(
    ["Agent", "About This Dataset", "About This Project"]
)

with tab_agent:
    # -----------------------------
    # Sidebar
    # -----------------------------
    with st.sidebar:
        st.header("Configuration")
        project_root = st.text_input("Project root", value=_default_project_root())
        planner_backend = st.selectbox("Planner backend", options=["auto", "llm", "curated"], index=0)
        planner_file = st.text_input("Planner file", value="planner/demo_gallery.json")
        model_name = st.text_input("LLM model", value="gpt-4.1")
        temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0, value=0.0, step=0.1)
    
        project_root_path = Path(project_root).resolve()
        setup_ok, missing_paths = check_setup(project_root_path)
    
        st.divider()
        if setup_ok:
            st.success("Project artifacts ready.")
        else:
            st.warning("Project artifacts missing. They will be built automatically on first run.")
            with st.expander("Missing artifacts"):
                for p in missing_paths:
                    st.code(str(p))
    
        st.divider()
        st.subheader("Run History")
    
        if not st.session_state.history:
            st.caption("No prior runs yet.")
        else:
            for i, item in enumerate(st.session_state.history):
                label = f"{item['timestamp']} | {item['mode']}"
                if item["job_ids"]:
                    label += f" | {', '.join(item['job_ids'][:2])}"
                    if len(item["job_ids"]) > 2:
                        label += "..."
                if st.button(label, key=f"hist_{i}", use_container_width=True):
                    _select_history_item(i)
    
    
    # -----------------------------
    # Main controls
    # -----------------------------
    demo_prompts = _load_demo_prompts(Path(project_root).resolve(), planner_file)
    selected_item = _compute_active_context()

    col_prompt, col_demo = st.columns([3, 1])
    with col_prompt:
        st.text_area(
            "Prompt",
            key="prompt_input",
            height=140,
            placeholder="Ask for an SPC plot, summary table, or replot modification...",
        )
    with col_demo:
        st.write("")
        st.write("")
        if st.session_state.get("guided_demo_step", 0) < 6:
            st.button(
                _guided_demo_label(),
                use_container_width=True,
                on_click=_start_guided_demo,
                args=(demo_prompts,),
                type="primary",
            )
        else:
            st.button(
                "Random Demo Prompt",
                use_container_width=True,
                on_click=_set_random_demo_prompt,
                args=(demo_prompts,),
            )
        if st.session_state.history:
            builder_choice = st.selectbox(
                "Replot builder",
                options=[
                    "Choose a helper...",
                    "hide_legend",
                    "entity_filter",
                    "last_3d",
                    "last_7d",
                    "add_ooc_summary_3d",
                    "boxplot_only",
                ],
                key="replot_builder_choice",
                format_func=lambda x: {
                    "Choose a helper...": "Choose a helper...",
                    "hide_legend": "Hide legend",
                    "entity_filter": "Filter entities",
                    "last_3d": "Last 3 days",
                    "last_7d": "Last 7 days",
                    "add_ooc_summary_3d": "Add OOC summary - last 3 days",
                    "boxplot_only": "Add boxplot",
                }[x],
                on_change=_apply_replot_builder_prompt,
            )
    
    run_col, checkbox_col = st.columns([1, 2])
    
    with run_col:
        run_clicked = st.button("Run Agent", type="primary", use_container_width=True)
    
    if st.session_state.get("reset_force_json_upload", False):
        st.session_state.force_json_upload = False
        st.session_state.context_history_index = None
        st.session_state.reset_force_json_upload = False
    
    with checkbox_col:
        st.checkbox(
            "Force JSON upload with prompt",
            key="force_json_upload",
            help="The agent can determine when previous prompt information is necessary for a request. Checking this box forces the agent to send previous prompt information on the next request.",
            on_change=_sync_force_json_context,
        )
    
    active_context = _compute_active_context()
    _render_active_context(active_context)
    
    # -----------------------------
    # Run agent
    # -----------------------------
    if st.session_state.get("run_requested_from_guided_demo", False):
        run_clicked = True
        st.session_state["run_requested_from_guided_demo"] = False
    
    if run_clicked:
        prompt_text = st.session_state.prompt_input.strip()
        if not prompt_text:
            st.error("Enter a prompt first.")
        else:
            project_root_path = Path(project_root).resolve()
    
            setup_ok, setup_msg = ensure_setup(project_root_path)
            if not setup_ok:
                st.error(setup_msg)
                st.stop()
    
            planner_config = {
                "model": model_name,
                "temperature": float(temperature),
            }
    
            final_prompt = _build_augmented_prompt(
                base_prompt=prompt_text,
                selected_item=selected_item,
                force_json_upload=st.session_state.force_json_upload,
            )
    
            try:
                with st.spinner("Running agent..."):
                    result = ask_agent(
                        prompt=final_prompt,
                        project_root=project_root_path,
                        planner_backend=planner_backend,
                        planner_file=planner_file,
                        planner_config=planner_config,
                        show_json=False,
                        verbose=verbose,
                    )
    
                item = {
                    "prompt": prompt_text,
                    "submitted_prompt": final_prompt,
                    "planner_backend": planner_backend,
                    "timestamp": _extract_run_timestamp(result),
                    "job_ids": _extract_job_ids(getattr(result, "plan", None)),
                    "run_json": _extract_run_json(getattr(result, "plan", None)),
                    "mode": _mode_label(result),
                    "result": result,
                }
                st.session_state.history.insert(0, item)
                st.session_state.selected_history_index = 0
                st.session_state.context_history_index = None

                if st.session_state.get("guided_demo_step", 0) < 6:
                    st.session_state["guided_demo_step"] += 1
    
                st.session_state.reset_force_json_upload = True
                st.rerun()
                
            except Exception as e:
                st.exception(e)
    
    
    # -----------------------------
    # Current viewer
    # -----------------------------
    current = _selected_history_item()
    if current:
        st.subheader("Current View")
        st.write(f"**Prompt:** {current['prompt']}")
        if current["submitted_prompt"] != current["prompt"]:
            with st.expander("Submitted prompt with embedded run JSON context", expanded=False):
                st.code(current["submitted_prompt"])
        _render_result(current["result"])
    else:
        if st.session_state.get("guided_demo_step", 0) < 2:
            st.markdown("### Welcome to the Deterministic SPC Agent")
            st.write("Ask manufacturing questions and get deterministic SPC analysis.")
            st.write("Start with **Run Guided Demo** for a two-step walkthrough, or enter your own prompt above.")
        else:
            st.markdown("### Welcome to the Deterministic SPC Agent")
            st.write("Ask manufacturing questions and get deterministic SPC analysis.")
            st.write("Use **Random Demo Prompt** for inspiration, or enter your own prompt above.")

# -----------------------------
# Dataset Tab
# -----------------------------
with tab_dataset:
    dataset_path = Path(project_root).resolve() / "dataset.md"
    dataset_md = _markdown_with_embedded_local_images(dataset_path)
    st.markdown(dataset_md, unsafe_allow_html=True)

# -----------------------------
# README Tab
# -----------------------------
with tab_project:
    readme_path = Path(project_root).resolve() / "README.md"
    readme_md = _markdown_with_embedded_local_images(readme_path)
    st.markdown(readme_md, unsafe_allow_html=True)