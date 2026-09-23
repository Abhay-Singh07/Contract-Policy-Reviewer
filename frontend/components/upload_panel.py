import streamlit as st

from utils.api_client import trigger_review, upload_document

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def render_upload_panel():
    st.subheader("Upload a contract")
    uploaded = st.file_uploader("PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])

    if uploaded and st.button("Upload & Review", type="primary"):
        ext = "." + uploaded.name.rsplit(".", 1)[-1].lower()
        with st.spinner("Parsing document..."):
            upload_result = upload_document(uploaded.getvalue(), uploaded.name, CONTENT_TYPES[ext])
        st.session_state.document_id = upload_result["document_id"]
        st.success(f"Parsed into {upload_result['clause_count']} clauses.")

        with st.spinner("Running review pipeline (risk + compliance + ambiguity agents)..."):
            review_result = trigger_review(upload_result["document_id"])

        if review_result.get("_error"):
            st.error(
                f"Review API failed — HTTP {review_result['status_code']}"
            )
        st.code(review_result["response"])
        st.stop()

st.session_state.reviewed = True
st.rerun()
