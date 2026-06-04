import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.models.base import TimestampMixin


class DictionaryEntry(Base, TimestampMixin):
    __tablename__ = "dictionary_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    term: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class BrandWhitelist(Base, TimestampMixin):
    __tablename__ = "brand_whitelist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_name: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class RuleCategory(str, enum.Enum):
    all = "all"
    bad = "bad"
    sport = "sport"
    grocery = "grocery"


class ChecklistRule(Base):
    __tablename__ = "checklist_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RuleCategory] = mapped_column(Enum(RuleCategory), nullable=False, default=RuleCategory.all)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
