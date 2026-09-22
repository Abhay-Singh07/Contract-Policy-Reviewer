import streamlit as st

SEVERITY_DISPLAY = {
    "critical": ("🟣", st.error),
    "high": ("🔴", st.error),
    "medium": ("🟠", st.warning),
    "low": ("🔵", st.info),
}
SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}


def render_findings_panel(report: dict):
    st.subheader(f"Findings ({len(report['findings'])})")
    if not report["findings"]:
        st.success("No issues found.")
        return

    ranked = sorted(report["findings"], key=lambda x: SEVERITY_RANK.get(x["severity"], -1), reverse=True)
    for f in ranked:
        icon, box = SEVERITY_DISPLAY.get(f["severity"], ("⚪", st.info))
        with box(f"{icon} **{f['severity'].upper()}** · {f['agent']}"):
            st.write(f["issue"])
            st.caption(f"Suggested fix: {f['recommendation']}")