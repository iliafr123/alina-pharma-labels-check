import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import mapped_column, Mapped
from app.core.database import Base
from app.core.types import GUID, JSONType


class ErrorLog(Base):
    """Every failure the app catches, kept so the admin screen can show what broke.

    Separate from `audit_log` (who did what) on purpose: this table is what
    the operator reads when a check fails and the cause is not obvious.
    """

    __tablename__ = "error_log"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)   # redacted technical message
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subsystem: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="api")  # api | worker
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
