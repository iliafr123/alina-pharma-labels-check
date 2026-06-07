import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, ForeignKey, Text, DateTime
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.core.types import GUID, JSONType
from app.models.base import TimestampMixin


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineMode(str, enum.Enum):
    hybrid = "hybrid"
    unified = "unified"


class CheckStage(str, enum.Enum):
    ocr = "ocr"
    spelling = "spelling"
    pen = "pen"
    regulatory = "regulatory"
    report = "report"


class CheckTask(Base, TimestampMixin):
    __tablename__ = "check_tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    mockup_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("mockups.id"), nullable=False)
    pen_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("pen_documents.id"), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    mode: Mapped[PipelineMode] = mapped_column(Enum(PipelineMode), nullable=False, default=PipelineMode.hybrid)
    pipeline_config: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # manual-review "Замечание" text
    benchmark: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # comparison verdict vs manual review
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list["CheckResult"]] = relationship("CheckResult", back_populates="task", lazy="selectin")


class CheckResult(Base):
    __tablename__ = "check_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("check_tasks.id"), nullable=False)
    stage: Mapped[CheckStage] = mapped_column(Enum(CheckStage), nullable=False)
    issues: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    annotated_pdf_s3_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped["CheckTask"] = relationship("CheckTask", back_populates="results")
