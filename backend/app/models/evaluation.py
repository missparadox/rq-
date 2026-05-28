from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


EvaluationStatus = Literal["pending", "running", "succeeded", "failed"]


class EvaluationDetail(BaseModel):
    evaluation_id: str
    status: EvaluationStatus
    filename: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    report_markdown: Optional[str] = None
    token_budget_path: Optional[str] = None
    token_budget_summary: Optional[dict[str, object]] = None
