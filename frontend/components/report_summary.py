import streamlit as st

RISK_COLOR = {"low": "green", "medium": "orange", "high": "red", "critical": "violet"}


def render_report_summary(report: dict):
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Overall Score", f"{report['overall_score']}/100")
    with col2:
        color = RISK_COLOR.get(report["overall_risk"], "gray")
        st.markdown(f"**Risk level:** :{color}[{report['overall_risk'].upper()}]")
        st.write(report["summary"])

    if report["top_issues"]:
        st.markdown("**Top issues:**")
        for issue in report["top_issues"]:
            st.markdown(f"- {issue}")