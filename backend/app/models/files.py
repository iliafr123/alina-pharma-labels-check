import uuid
import enum
from sqlalchemy import String, Integer, Enum, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
from app.models.base import TimestampMixin


class FileType(str, enum.Enum):
    pdf = "pdf"
    jpg = "jpg"


class Mockup(Base, TimestampMixin):
    __tablename__ = "mockups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="mockups")


class PenDocument(Base, TimestampMixin):
    __tablename__ = "pen_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    s3_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    parsed_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="pen_documents")
