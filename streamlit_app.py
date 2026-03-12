
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from spc_agent.agent.agent_runner import ask_agent


st.set_page_config(
    page_title="Deterministic SPC Agent",
    page_icon="📈",
    layout="wide",
)

st.title("Deterministic SPC Agent")
st.caption("Natural-language wrapper for prompt → plan → execute / replot → verify → summarize")


def _default_project_root() -> str:
    return str(Path.cwd().resolve())


def _read_text_if_exists(path_str: str | None):
    if not path_str:
        return None
    path = Path(path_str)
    if path.exists() and path.is_file():
        return path.read_text()
    return None


def _render_result(result):
    st.subheader("Result")

    left, right = st.columns(2)

    with left:
        st.write("**Planner backend**")
        st.code(result.planner_backend)

        st.write("**Planner context**")
        st.code(result.planner_context)

        st.write("**Verification summary**")
        st.code(result.verification_summary)

        if result.unsupported_request:
            st.warning(f"Unsupported request: {result.unsupported_reason}")

        if result.run_dir is not None:
            st.write("**Artifact directory**")
            st.code(str(result.run_dir))

        if result.run_summary_path is not None:
            st.write("**Summary artifact**")
            st.code(str(result.run_summary_path))

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
            st.subheader("Run Summary")
            st.markdown(summary_text)

    if result.run_dir is not None and result.run_summary_path is None:
        st.info("This result did not generate run_summary.md. Check the artifact directory above.")


with st.sidebar:
    st.header("Configuration")
    project_root = st.text_input("Project root", value=_default_project_root())
    planner_backend = st.selectbox("Planner backend", options=["llm", "stub"], index=0)
    planner_file = st.text_input("Planner file", value="planner/demo_gallery.json")
    model_name = st.text_input("LLM model", value="gpt-4.1")
    temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0, value=0.0, step=0.1)
    show_json = st.checkbox("Include executed plan in run_summary.md", value=False)
    verbose = st.checkbox("Verbose server logs", value=False)

    st.divider()
    st.markdown(
        "Examples:\n"
        "- Plot 7 days of vibration data for ARM tools.\n"
        "- Remove the legend from the last plot. Add a boxplot for the last 3 days and an OOC summary.\n"
        "- CPR11 needed maintenance last week due to motor temperature and again due to vibration. How is the tool doing now?"
    )

prompt = st.text_area(
    "Prompt",
    height=140,
    placeholder="Ask for an SPC plot, summary table, or replot modification...",
)

run_clicked = st.button("Run Agent", type="primary", use_container_width=True)

if "history" not in st.session_state:
    st.session_state.history = []

if run_clicked:
    if not prompt.strip():
        st.error("Enter a prompt first.")
    else:
        planner_config = {
            "model": model_name,
            "temperature": float(temperature),
        }

        try:
            with st.spinner("Running agent..."):
                result = ask_agent(
                    prompt=prompt.strip(),
                    project_root=Path(project_root),
                    planner_backend=planner_backend,
                    planner_file=planner_file,
                    planner_config=planner_config,
                    show_json=show_json,
                    verbose=verbose,
                )

            st.session_state.history.insert(
                0,
                {
                    "prompt": prompt.strip(),
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
