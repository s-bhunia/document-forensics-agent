from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    risk_score: float | None
    label: str | None
    finding_count: int | None
    created_at: datetime
    completed_at: datetime | None
    error: str | None


class AnalysisDetail(AnalysisSummary):
    result: dict[str, Any] | None


class AnalysisPage(BaseModel):
    items: list[AnalysisSummary]
    total: int
    page: int
    page_size: int


class Health(BaseModel):
    status: str
    llm_enabled: bool
