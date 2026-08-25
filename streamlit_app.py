"""
Dash2BI AI — Streamlit Cloud entrypoint.

This runs the exact same analysis / mapping / PBIP-generation logic as the
FastAPI backend in backend/app/services/, just called directly from a single
Streamlit script instead of through REST endpoints + a React frontend.
Streamlit Cloud only runs one Python file, so this *is* the app for that
deployment target — the FastAPI + React version under backend/ and
frontend/ still exists and can be run/deployed separately (e.g. Render +
Vercel) if you want the full multi-page UI.
"""
import os
import sys
import json
import tempfile
import uuid
from pathlib import Path

import streamlit as st

# --- Make backend/app importable, and push config (API keys, dirs) into
# --- the environment BEFORE importing anything from app.core.config, since
# --- Settings() reads os.environ at import time. ---
BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

_WORKDIR = Path(tempfile.gettempdir()) / "dash2bi_streamlit"
_WORKDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("UPLOAD_DIR", str(_WORKDIR / "uploads"))
os.environ.setdefault("OUTPUT_DIR", str(_WORKDIR / "outputs"))

if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    os.environ.setdefault("AI_PROVIDER", "anthropic")
else:
    os.environ.setdefault("AI_PROVIDER", "none")

from app.services import excel_analyzer, html_analyzer, mapping_engine, conversion_service  # noqa: E402

st.set_page_config(page_title="Dash2BI AI", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
defaults = {
    "dataset_path": None, "dashboard_path": None,
    "dataset_analysis": None, "dashboard_analysis": None,
    "mappings": None, "preview_summary": None, "conversion_report": None,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

LEVEL_ICON = {"automatic": "✅", "ai_suggested": "⚠️", "unsupported": "❌"}
LEVEL_LABEL = {"automatic": "Automatic", "ai_suggested": "AI Suggested", "unsupported": "Unsupported"}


def save_upload(uploaded_file, subdir: str) -> str:
    dest_dir = Path(os.environ["UPLOAD_DIR"]) / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4()}_{uploaded_file.name}"
    dest.write_bytes(uploaded_file.getbuffer())
    return str(dest)


def reset_downstream(from_step: str):
    """Clear anything computed after `from_step` when an upstream input changes."""
    order = ["upload", "analyze", "map", "preview", "convert"]
    idx = order.index(from_step)
    if idx <= order.index("analyze"):
        st.session_state.dataset_analysis = None
        st.session_state.dashboard_analysis = None
    if idx <= order.index("map"):
        st.session_state.mappings = None
    if idx <= order.index("preview"):
        st.session_state.preview_summary = None
    if idx <= order.index("convert"):
        st.session_state.conversion_report = None


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📊 Dash2BI AI")
st.caption(
    "Upload your Excel dataset and HTML dashboard. AI analyzes, maps, and reconstructs "
    "your dashboard as a real Power BI Project (PBIP) — never a renamed HTML file."
)

if os.environ.get("AI_PROVIDER") == "none":
    st.info(
        "No AI provider configured — running on deterministic heuristic matching. "
        "Add `ANTHROPIC_API_KEY` under Settings → Secrets in Streamlit Cloud for AI-assisted "
        "column matching and DAX generation.",
        icon="ℹ️",
    )

step1, step2, step3, step4 = st.tabs(
    ["1️⃣ Upload", "2️⃣ Analyze", "3️⃣ Preview & Map", "4️⃣ Convert & Download"]
)

# ---------------------------------------------------------------------------
# Step 1 — Upload
# ---------------------------------------------------------------------------
with step1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Excel Dataset")
        dataset_file = st.file_uploader("xlsx / xls / csv", type=["xlsx", "xls", "csv"], key="dataset_uploader")
        if dataset_file is not None:
            path = save_upload(dataset_file, "dataset")
            if path != st.session_state.dataset_path:
                st.session_state.dataset_path = path
                reset_downstream("upload")
            st.success(f"Uploaded: {dataset_file.name}")

    with col2:
        st.subheader("HTML Dashboard")
        dashboard_file = st.file_uploader("html / htm / zip", type=["html", "htm", "zip"], key="dashboard_uploader")
        if dashboard_file is not None:
            path = save_upload(dashboard_file, "dashboard")
            if path != st.session_state.dashboard_path:
                st.session_state.dashboard_path = path
                reset_downstream("upload")
            st.success(f"Uploaded: {dashboard_file.name}")

    ready = st.session_state.dataset_path and st.session_state.dashboard_path
    if ready:
        st.success("Both files uploaded. Head to the **Analyze** tab.")
    else:
        st.caption("Upload both files to continue.")

# ---------------------------------------------------------------------------
# Step 2 — Analyze
# ---------------------------------------------------------------------------
with step2:
    if not (st.session_state.dataset_path and st.session_state.dashboard_path):
        st.warning("Upload both files in the **Upload** tab first.")
    else:
        if st.button("Run analysis", type="primary"):
            with st.spinner("Analyzing dataset (pandas) and dashboard (HTML/JS AST)…"):
                try:
                    st.session_state.dataset_analysis = excel_analyzer.analyze_dataset(st.session_state.dataset_path)
                    st.session_state.dashboard_analysis = html_analyzer.analyze_dashboard(st.session_state.dashboard_path)
                    reset_downstream("analyze")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

        ds = st.session_state.dataset_analysis
        dash = st.session_state.dashboard_analysis

        if ds:
            st.subheader(f"Dataset: {ds['file_name']}")
            for sheet in ds["sheets"]:
                with st.expander(f"{sheet['sheet_name']} — {sheet['row_count']} rows, {len(sheet['columns'])} columns", expanded=True):
                    col_info = [{"Column": c["name"], "Type": c["dtype"], "Missing": c["missing_count"], "Unique": c["unique_count"]} for c in sheet["columns"]]
                    st.dataframe(col_info, use_container_width=True, hide_index=True)
                    st.caption("Preview")
                    st.dataframe(sheet["preview_rows"][:10], use_container_width=True, hide_index=True)

        if dash:
            st.subheader(f"Dashboard: {dash['file_name']}")
            visuals = dash["detected_visuals"]
            cols = st.columns(3)
            for i, v in enumerate(visuals):
                with cols[i % 3]:
                    st.markdown(f"**{v['raw_title'] or v['visual_id']}**")
                    st.caption(f"{v['candidate_type']} · source: {v['source']}")
            if not visuals:
                st.warning("No visuals detected in the dashboard file.")

# ---------------------------------------------------------------------------
# Step 3 — Map & Preview
# ---------------------------------------------------------------------------
with step3:
    if not (st.session_state.dataset_analysis and st.session_state.dashboard_analysis):
        st.warning("Run analysis in the **Analyze** tab first.")
    else:
        if st.button("Build mapping & preview", type="primary"):
            with st.spinner("Matching visuals to dataset columns and drafting DAX…"):
                try:
                    mappings = mapping_engine.build_mappings(
                        st.session_state.dataset_analysis, st.session_state.dashboard_analysis
                    )
                    st.session_state.mappings = mappings
                    st.session_state.preview_summary = conversion_service.build_preview_summary(mappings)
                    reset_downstream("preview")
                except Exception as e:
                    st.error(f"Mapping failed: {e}")

        mappings = st.session_state.mappings
        summary = st.session_state.preview_summary

        if summary:
            counts_line = "  ·  ".join(f"✓ {v} {k}" for k, v in summary["counts"].items())
            if counts_line:
                st.success(counts_line)
            if summary["unsupported"]:
                for u in summary["unsupported"]:
                    st.warning(f"**{u['title']}** — {u['reason']} Suggested alternative: {u['suggested_alternative']}")

        if mappings:
            st.subheader("Visual mappings")
            all_columns = []
            for sheet in st.session_state.dataset_analysis["sheets"]:
                all_columns.extend(c["name"] for c in sheet["columns"])

            for m in mappings:
                icon = LEVEL_ICON[m["level"]]
                with st.expander(f"{icon} {m['title']} — {m['power_bi_type']} ({LEVEL_LABEL[m['level']]})"):
                    st.write(f"Confidence: {round(m.get('confidence', 0) * 100)}%")
                    if m.get("warning"):
                        st.caption(m["warning"])
                    if m["level"] == "ai_suggested" and all_columns:
                        current = m.get("field") or m.get("category") or m.get("x_axis") or ""
                        new_val = st.selectbox(
                            "Confirm or correct the mapped column",
                            options=[""] + all_columns,
                            index=([""] + all_columns).index(current) if current in all_columns else 0,
                            key=f"select_{m['visual_id']}",
                        )
                        if new_val and new_val != current:
                            target_field = "field" if m.get("field") else ("category" if m.get("category") else "x_axis")
                            m[target_field] = new_val
                            m["level"] = "automatic"
                            m["confidence"] = 1.0
                            m["warning"] = None
                            st.session_state.mappings = mappings
                            st.session_state.preview_summary = conversion_service.build_preview_summary(mappings)
                            st.rerun()
                    if m.get("dax_measure"):
                        st.code(m["dax_measure"]["expression"], language="sql")

            st.info("Head to **Convert & Download** once you're happy with the mappings.")

# ---------------------------------------------------------------------------
# Step 4 — Convert & Download
# ---------------------------------------------------------------------------
with step4:
    if not st.session_state.mappings:
        st.warning("Build the mapping in the **Preview & Map** tab first.")
    else:
        project_name = st.text_input("Project name", value="Dash2BI_Project")
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ("_", "-")) or "Dash2BI_Project"

        if st.button("Generate Power BI Project", type="primary"):
            steps = [
                "Reading Excel", "Analyzing HTML", "Detecting visuals",
                "Mapping dataset", "Generating DAX", "Building Power BI project", "Validation",
            ]
            progress = st.progress(0, text=steps[0])
            for i, label in enumerate(steps[:-1]):
                progress.progress(int((i + 1) / len(steps) * 100), text=label)
            try:
                report = conversion_service.run_conversion(
                    session_id=str(uuid.uuid4()),
                    project_name=safe_name,
                    dataset_analysis=st.session_state.dataset_analysis,
                    mappings=st.session_state.mappings,
                )
                progress.progress(100, text="Validation")
                st.session_state.conversion_report = report
            except Exception as e:
                st.error(f"Conversion failed: {e}")

        report = st.session_state.conversion_report
        if report:
            if report["status"] == "completed":
                st.success("Conversion completed")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Visuals converted", report["visuals_converted"])
                c2.metric("Data mappings", report["data_mappings_created"])
                c3.metric("DAX measures", report["dax_measures_generated"])
                c4.metric("Slicers", report["slicers_created"])

                for w in report.get("warnings", []):
                    st.warning(w)

                output_path = report.get("output_path")
                if output_path and Path(output_path).exists():
                    with open(output_path, "rb") as f:
                        st.download_button(
                            "⬇️ Download Power BI Project (.zip)",
                            data=f.read(),
                            file_name=Path(output_path).name,
                            mime="application/zip",
                            type="primary",
                        )
                    st.caption("Unzip and open the .pbip file in Power BI Desktop (File → Open → Power BI Project).")
            else:
                st.error("Conversion could not complete.")
                for err in report.get("errors", []):
                    st.write(f"Reason: {err}")
