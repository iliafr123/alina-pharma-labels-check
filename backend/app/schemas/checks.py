import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.checks import TaskStatus, PipelineMode


class CheckCreate(BaseModel):
    mockup_id: uuid.UUID
    pen_id: uuid.UUID
    mode: PipelineMode = PipelineMode.hybrid
    pipeline_config: dict | None = None


class IssueResponse(BaseModel):
    type: str
    module: str
    description: str
    suggestion: str | None = None
    bbox: dict | None = None
    meta: dict | None = None


class CheckResultResponse(BaseModel):
    id: uuid.UUID
    stage: str
    issues: list | None = None
    annotated_pdf_s3_key: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class CheckTaskResponse(BaseModel):
    id: uuid.UUID
    mockup_id: uuid.UUID
    pen_id: uuid.UUID
    status: TaskStatus
    mode: PipelineMode
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    results: list[CheckResultResponse] = []
    model_config = {"from_attributes": True}
