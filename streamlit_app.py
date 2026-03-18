from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from spc_agent.agent.agent_runner import ask_agent


st.set_page_config(
    page_title="Deterministic SPC Agent",
    page_icon="📈",
    layout="wide",
)

st.title("Deterministic SPC Agent")
st.caption("Natural-language wrapper for prompt → plan → execute / replot → verify → summarize")


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

def _collect_output_artifacts(result) -> tuple[list[Path], list[Path]]:
    if result.run_dir is None:
        return [], []

    root = Path(result.run_dir)
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    image_paths: list[Path] = []
    table_paths: list[Path] = []

    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in image_exts:
                image_paths.append(path)
            elif path.suffix.lower() == ".csv":
                name = path.name.lower()
                if "summary" in name or "ooc" in name:
                    table_paths.append(path)

    return sorted(image_paths), sorted(table_paths)


def _render_outputs(result) -> None:
    image_paths, table_paths = _collect_output_artifacts(result)

    if image_paths or table_paths:
        st.subheader("Outputs")

    for image_path in image_paths:
        st.image(str(image_path), caption=image_path.name, width='content')
        st.caption(str(image_path))

    for table_path in table_paths:
        st.write(f"**{table_path.name}**")
        try:
            df = pd.read_csv(table_path)
            st.dataframe(df, width='content')
        except Exception as e:
            st.warning(f"Could not load table {table_path.name}: {e}")
        st.caption(str(table_path))


def _read_text_if_exists(path_str: str | None):
    if not path_str:
        return None
    path = Path(path_str)
    if path.exists() and path.is_file():
        return path.read_text()
    return None


def _render_result(result):
    _render_outputs(result)

    st.subheader("Artifacts")
    if result.run_dir is not None:
        st.write("**Artifact directory**")
        st.code(str(result.run_dir))

    if result.run_summary_path is not None:
        st.write("**Summary artifact**")
        st.code(str(result.run_summary_path))

    if result.unsupported_request:
        st.warning(f"Unsupported request: {result.unsupported_reason}")

    if result.recovery_used:
        st.info("Recovery pass used prior run context.")
        if result.recovery_details:
            with st.expander("Recovery details", expanded=False):
                st.code(json.dumps(result.recovery_details, indent=2), language="json")

    st.subheader("Diagnostics")
    left, right = st.columns(2)

    with left:
        st.write("**Planner backend**")
        st.code(result.planner_backend)

        st.write("**Planner context**")
        st.code(result.planner_context)

        st.write("**Verification summary**")
        st.code(result.verification_summary)

    with right:
        if result.plan is not None:
            with st.expander("Final plan JSON", expanded=False):
                st.code(json.dumps(result.plan, indent=2), language="json")

        if result.planner_raw_output:
            with st.expander("Planner raw output", expanded=False):
                st.code(result.planner_raw_output, language="json")

    if result.run_summary_path is not None:
        summary_text = _read_text_if_exists(str(result.run_summary_path))
        if summary_text:
            with st.expander("Run Summary Markdown", expanded=False):
                st.markdown(summary_text)


if "history" not in st.session_state:
    st.session_state.history = []
if "prompt_input" not in st.session_state:
    st.session_state.prompt_input = ""

with st.sidebar:
    st.header("Configuration")
    project_root = st.text_input("Project root", value=_default_project_root())
    planner_backend = st.selectbox("Planner backend", options=["auto", "llm", "curated"], index=0)
    planner_file = st.text_input("Planner file", value="planner/demo_gallery.json")
    model_name = st.text_input("LLM model", value="gpt-4.1")
    temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0, value=0.0, step=0.1)
    show_json = st.checkbox("Include executed plan in run_summary.md", value=False)
    verbose = st.checkbox("Verbose server logs", value=False)

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

demo_prompts = _load_demo_prompts(Path(project_root).resolve(), planner_file)

col1, col2 = st.columns([4, 1])
with col1:
    prompt = st.text_area(
        "Prompt",
        key="prompt_input",
        height=140,
        placeholder="Ask for an SPC plot, summary table, or replot modification...",
    )
with col2:
    st.write("")
    st.write("")
    st.button(
        "Random Demo Prompt",
        use_container_width=True,
        on_click=_set_random_demo_prompt,
        args=(demo_prompts,),
    )

run_clicked = st.button("Run Agent", type="primary", width='content')

if run_clicked:
    if not st.session_state.prompt_input.strip():
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

        try:
            with st.spinner("Running agent..."):
                result = ask_agent(
                    prompt=st.session_state.prompt_input.strip(),
                    project_root=project_root_path,
                    planner_backend=planner_backend,
                    planner_file=planner_file,
                    planner_config=planner_config,
                    show_json=show_json,
                    verbose=verbose,
                )

            st.session_state.history.insert(
                0,
                {
                    "prompt": st.session_state.prompt_input.strip(),
                    "planner_backend": planner_backend,
                    "result": result,
                },
            )

        except Exception as e:
            st.exception(e)

if st.session_state.history:
    latest = st.session_state.history[0]
    st.subheader("Latest Run")
    st.write(f"**Prompt:** {latest['prompt']}")
    _render_result(latest["result"])

    with st.expander("History", expanded=False):
        for i, item in enumerate(st.session_state.history[1:], start=2):
            st.markdown(f"### Run {i}")
            st.write(f"**Prompt:** {item['prompt']}")
            _render_result(item["result"])
            st.divider()