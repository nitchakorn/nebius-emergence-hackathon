"""Streamlit UI for ClinicalxCRAFT 2.0 — cohort dashboard + contextual follow-up.

Unlike app.py's blank-box UX, this opens on a live cohort snapshot (dashboard_data.py:
a fixed set of direct CRAFT queries, not the free-form agent) so the user sees the data
before asking anything. Follow-up questions still run the full agentic investigation
(agent.run, same as app.py) but with the visible snapshot folded in as context, so the
model doesn't re-derive numbers already on screen. app.py is untouched — this is a
second, independent entrypoint. Run with:
streamlit run apps/clinicalq/app_dashboard.py
"""
import asyncio
import os
import sys
from pathlib import Path

# See app.py for why this path dance is needed under `streamlit run`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from apps.clinicalq import config, dashboard_data, dashboard_render
from apps.clinicalq.agent import DEFAULT_QUESTION, run
from apps.clinicalq.craft_auth import build_oauth_provider

# (button label, question) — reuses app.py's EXAMPLE_QUESTIONS verbatim where a question
# maps 1:1 to a dashboard section, plus one new genomics-scoped question.
QUICK_ASKS = [
    ("Outcomes →", DEFAULT_QUESTION),
    (
        "Genomic drivers →",
        "What are the most frequently mutated genes in this cohort, and how does that "
        "compare to the published TCGA KIRC driver profile?",
    ),
    (
        "Mutation burden →",
        "Given the mutation rates shown for the top genes, is there a relationship "
        "between mutation burden and vital status or pathologic stage in this cohort?",
    ),
    (
        "Stage & surgery →",
        "Is there a relationship between pathologic stage and the type of surgery performed?",
    ),
    (
        "Demographics →",
        "How does age at diagnosis differ across race or sex in this cohort?",
    ),
    (
        "Histology & outcome →",
        "Does histological subtype relate to survival outcome?",
    ),
]

st.set_page_config(page_title="ClinicalxCRAFT 2.0", page_icon="📊", layout="wide")
st.title("📊 ClinicalxCRAFT 2.0 — Cohort Dashboard")
st.caption(
    "See the KIRC (kidney renal clear cell carcinoma) cohort first, then ask a follow-up "
    "scoped to what you're looking at — the model is told to treat the numbers already on "
    "screen as its starting baseline, so it goes straight to deeper investigation instead "
    "of re-deriving them, and only reaches for outside background (Wikipedia, always "
    "cited) when the question turns on biology the data alone can't explain. This is "
    "de-identified public research data — findings are for research/education, not "
    "individual patient care. Looking for the original free-text version? "
    "See `app.py`."
)


async def _check_connection() -> str:
    auth = await build_oauth_provider()
    async with streamablehttp_client(config.MCP_URL, auth=auth, headers=config.HEADERS) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("hello_world", {})
            return result.content[0].text


with st.sidebar:
    st.header("Connection")
    st.write("Complete OAuth once before running (opens a browser tab).")
    if st.button("Check connection"):
        with st.spinner("Contacting CRAFT…"):
            try:
                st.success(f"Connected: {asyncio.run(_check_connection())}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

# --- snapshot: load cached, or fetch fresh on first load / explicit refresh ---
if "snapshot" not in st.session_state:
    st.session_state["snapshot"] = dashboard_data.load_cached_snapshot()

snapshot = st.session_state["snapshot"]

cap_col, btn_col = st.columns([5, 1])
with cap_col:
    if snapshot:
        st.caption(f"Snapshot fetched {snapshot['fetched_at']}")
    else:
        st.caption("No snapshot cached yet — fetching one now.")
with btn_col:
    refresh_clicked = st.button("🔄 Refresh" if snapshot else "Fetch now")

if refresh_clicked or snapshot is None:
    progress_box = st.empty()

    def on_progress(label: str) -> None:
        progress_box.info(label)

    with st.spinner("Querying the cohort…"):
        try:
            snapshot = asyncio.run(dashboard_data.fetch_snapshot(on_progress=on_progress))
            dashboard_data.save_snapshot(snapshot)
            st.session_state["snapshot"] = snapshot
        except Exception as e:
            st.error(f"Couldn't fetch the snapshot: {e}")
        finally:
            progress_box.empty()

# --- specimen ledger: per-patient table, mutations, protein, purity, imaging links ---
# This is the primary view — the actual per-patient data and imaging links, not an
# aggregate chart. It's what a researcher wants in front of them first.
_LEDGER_PATH = Path(__file__).parent / "kirc_ledger.html"
if _LEDGER_PATH.exists():
    st.iframe(_LEDGER_PATH, height=1200)
else:
    st.warning("Specimen ledger not found — expected apps/clinicalq/kirc_ledger.html.")

# --- cohort snapshot (aggregate charts) — collapsed, still used as context below ---
if snapshot:
    with st.expander("📊 Cohort snapshot (aggregate charts)", expanded=False):
        st.iframe(dashboard_render.render_html(snapshot), height=1350)
else:
    st.warning("No snapshot available. Click **Fetch now** above (requires CRAFT OAuth — see sidebar).")

st.divider()

# --- contextual follow-up ---
st.subheader("Ask about what you're seeing")
cols = st.columns(3)
for i, (label, q) in enumerate(QUICK_ASKS):
    with cols[i % 3]:
        if st.button(label, key=f"qa_{i}"):
            st.session_state["question"] = q

question = st.text_area(
    "Or type your own follow-up",
    value=st.session_state.get("question", DEFAULT_QUESTION),
    height=90,
)

if st.button("🔎 Investigate", type="primary"):
    trace_box = st.container()
    trace_box.subheader("Live reasoning trace")
    status = trace_box.status("Investigating…", expanded=True)

    def on_event(kind: str, detail: str) -> None:
        icon = {"note": "💭", "tool": "🔧", "status": "•"}.get(kind, "•")
        if kind == "note":
            status.markdown(f"💭 **{detail}**")
        else:
            status.write(f"{icon} {detail}")

    context = dashboard_data.summarize_for_context(snapshot) if snapshot else None
    try:
        result = asyncio.run(run(question, on_event=on_event, context=context))
        status.update(label="Investigation complete", state="complete")
        st.session_state["result"] = result
    except Exception as e:
        status.update(label="Investigation failed", state="error")
        st.exception(e)

result = st.session_state.get("result")
if result is not None:
    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Findings")
        st.markdown(result.report)
    with right:
        for path in result.chart_paths or []:
            st.image(path, use_container_width=True)
    with st.expander(f"💭 The model's reasoning ({len(result.notes)} notes)"):
        for i, note in enumerate(result.notes or [], 1):
            st.markdown(f"{i}. {note}")
    with st.expander(f"🔍 Generated SQL — the LLM wrote every one ({len(result.sql_log)} queries)"):
        for label, sql in result.sql_log or []:
            st.markdown(f"**{label}**")
            st.code(sql, language="sql")
    st.caption(f"Outputs saved to `{result.out_dir}`")
