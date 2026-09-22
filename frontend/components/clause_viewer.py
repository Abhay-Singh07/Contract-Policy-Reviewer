import streamlit as st

from utils.api_client import get_document


def render_clause_viewer(document_id: str):
    st.subheader("Document")
    doc = get_document(document_id)
    for clause in doc["clauses"]:
        heading = clause["heading"] or f"Clause {clause['clause_number']}"
        with st.expander(f"{clause['clause_number']}. {heading}", expanded=False):
            st.write(clause["text"])