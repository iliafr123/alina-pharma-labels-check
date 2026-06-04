import uuid
import enum
from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.models.base import TimestampMixin


class ProductCategory(str, enum.Enum):
    bad = "bad"
    sport = "sport"
    grocery = "grocery"


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[ProductCategory] = mapped_column(Enum(ProductCategory), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    mockups: Mapped[list["Mockup"]] = relationship("Mockup", back_populates="product", lazy="selectin")
    pen_documents: Mapped[list["PenDocument"]] = relationship("PenDocument", back_populates="product", lazy="selectin")
