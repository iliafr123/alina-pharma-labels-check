import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.checks import TaskStatus, PipelineMode


class CheckCreate(BaseModel):
    mockup_id: uuid.UUID
    pen_id: uuid.UUID
    mode: PipelineMode = PipelineMode.hybrid
    pipeline_config: dict | None = None
    reference_text: str | None = None  # optional manual-review "Замечание" content
    focus_prompt: str | None = None    # optional instruction to focus the LLM on specific checks


class BatchItem(BaseModel):
    mockup_id: uuid.UUID
    pen_id: uuid.UUID


class BatchCreate(BaseModel):
    items: list[BatchItem]                 # up to 20 label pairs
    pipeline_config: dict | None = None    # shared across the batch
    focus_prompt: str | None = None


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


class CheckHistoryItem(BaseModel):
    """Journal row. Carries the product's full name - the раньше-shown mockup UUID
    told the operator nothing about which БАД was checked."""
    id: uuid.UUID
    product_name: str
    category: str | None = None
    mockup_name: str | None = None
    mockup_version: int | None = None
    status: TaskStatus
    mode: PipelineMode
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    error_code: str | None = None
    error_details: dict | None = None
    issues_count: int = 0
    batch_id: str | None = None


class CheckTaskResponse(BaseModel):
    id: uuid.UUID
    mockup_id: uuid.UUID
    pen_id: uuid.UUID
    product_name: str | None = None
    status: TaskStatus
    mode: PipelineMode
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    error_code: str | None = None
    error_details: dict | None = None
    quality: dict | None = None
    benchmark: dict | None = None  # verdict vs manual review (matched / missing / extra)
    checklist: list | None = None  # per-item ✓/✗ verdict over mandatory marking elements
    results: list[CheckResultResponse] = []
    model_config = {"from_attributes": True}
