import streamlit as st

from components.clause_viewer import render_clause_viewer
from components.findings_panel import render_findings_panel
from components.report_summary import render_report_summary
from components.upload_panel import render_upload_panel
from utils.api_client import get_report

st.set_page_config(page_title="Contract Reviewer", layout="wide")
st.title("📄 Contract Reviewer")
st.caption("Multi-agent review for Indian contracts — risk, DPDP/IT Act compliance, and ambiguity checks.")

if "document_id" not in st.session_state:
    st.session_state.document_id = None
    st.session_state.reviewed = False

render_upload_panel()

if st.session_state.document_id and st.session_state.reviewed:
    st.divider()
    report = get_report(st.session_state.document_id)
    render_report_summary(report)
    st.divider()

    left, right = st.columns(2)
    with left:
        render_clause_viewer(st.session_state.document_id)
    with right:
        render_findings_panel(report)