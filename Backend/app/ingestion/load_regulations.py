"""Loads data/regulations/*.json into the static regulation_sections table.
Run with: python -m app.ingestion.load_regulations

Requires the schema to already exist — run `alembic upgrade head` first.
This deliberately does NOT call Base.metadata.create_all(): doing so would
create tables outside Alembic's tracking (no alembic_version stamp), which
is exactly the inconsistency removed from app/main.py's old startup event.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import inspect

from app.core.embeddings import get_embedding_client
from app.db.database import SessionLocal, engine
from app.db.models import RegulationSection

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "regulations"


def run() -> None:
    if not inspect(engine).has_table(RegulationSection.__tablename__):
        sys.exit(
            "regulation_sections table doesn't exist yet. Run `alembic upgrade head` "
            "from backend/ first, then re-run this script."
        )

    db = SessionLocal()
    embed_client = get_embedding_client()

    for file in DATA_DIR.glob("*.json"):
        sections = json.loads(file.read_text())
        texts = [s["text"] for s in sections]
        vectors = embed_client.embed(texts)
        for section, vec in zip(sections, vectors):
            db.add(RegulationSection(section=section["section"], text=section["text"], embedding=vec))
        print(f"Loaded {len(sections)} sections from {file.name}")

    db.commit()
    db.close()


if __name__ == "__main__":
    run()