"""
Splits raw contract text into ClauseState units.

Primary strategy: contracts are usually numbered ("1. Definitions", "2) Term",
"3. Indemnification..."), so we find those markers and slice the text between
them. If no numbering is found (e.g. a loosely formatted doc), we fall back
to splitting on blank lines.
"""
from __future__ import annotations

import re

from app.core.state import ClauseState

CLAUSE_START = re.compile(r"(?m)^\s*(\d{1,3})[\.\)]\s+(.*)")
# Matches a short title-like phrase right after the number, ending at the first
# ". " or ":" — e.g. "Definitions. In this Agreement..." -> "Definitions"
_HEADING_RE = re.compile(r"^([A-Z][A-Za-z0-9 ,/&'\-]{1,60}?)[.:]\s")


def segment_clauses(raw_text: str) -> list[ClauseState]:
    matches = list(CLAUSE_START.finditer(raw_text))

    if not matches:
        return _segment_by_paragraph(raw_text)

    clauses: list[ClauseState] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        block = raw_text[start:end].strip()
        if not block:
            continue
        heading_line = m.group(2).split("\n")[0].strip()
        heading_match = _HEADING_RE.match(heading_line)
        heading = heading_match.group(1).strip() if heading_match else None
        clauses.append(ClauseState(
            clause_number=len(clauses) + 1,
            heading=heading,
            text=block,
            start_char=start,
            end_char=end,
        ))
    return clauses


def _segment_by_paragraph(raw_text: str) -> list[ClauseState]:
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    return [ClauseState(clause_number=i + 1, text=p) for i, p in enumerate(paragraphs)]