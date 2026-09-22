from app.core.embeddings import get_embedding_client
from app.core.regulations import find_relevant_regulations, format_regulation_context
from app.db.models import RegulationSection


def _seed(db):
    embed_client = get_embedding_client()
    sections = [
        ("DPDP Act 2023, Section 8(6)",
         "In the event of a personal data breach, the Data Fiduciary shall notify the Board and each affected Data Principal."),
        ("DPDP Act 2023, Section 5",
         "The Data Fiduciary must give notice describing personal data collected and the purpose of processing."),
    ]
    vectors = embed_client.embed([t for _, t in sections])
    for (name, text), vec in zip(sections, vectors):
        db.add(RegulationSection(section=name, text=text, embedding=vec))
    db.flush()  # same-transaction visibility, no commit needed


def test_find_relevant_regulations_returns_rows(db):
    _seed(db)
    results = find_relevant_regulations(db, "The Vendor shall report any data breach within 5 days.", top_k=2)
    assert len(results) > 0
    assert all(isinstance(r, RegulationSection) for r in results)


def test_find_relevant_regulations_respects_top_k(db):
    _seed(db)
    results = find_relevant_regulations(db, "data breach notification requirements", top_k=1)
    assert len(results) <= 1


def test_format_regulation_context_empty_list_returns_empty_string():
    assert format_regulation_context([]) == ""


def test_format_regulation_context_includes_section_name_and_text(db):
    _seed(db)
    results = find_relevant_regulations(db, "data breach notification", top_k=1)
    formatted = format_regulation_context(results)

    assert "Relevant regulation text" in formatted
    assert results[0].section in formatted
    assert results[0].text in formatted