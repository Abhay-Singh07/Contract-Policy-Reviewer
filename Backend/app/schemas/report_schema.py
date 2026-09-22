from pydantic import BaseModel

from app.schemas.finding_schema import FindingOut


class ReportOut(BaseModel):
    overall_score: int
    overall_risk: str
    summary: str
    top_issues: list[str]
    findings: list[FindingOut]