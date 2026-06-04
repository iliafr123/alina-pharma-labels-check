import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.files import FileType
from app.models.products import ProductCategory


class ProductCreate(BaseModel):
    name: str
    category: ProductCategory


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: ProductCategory
    created_at: datetime
    model_config = {"from_attributes": True}


class MockupResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    version: int
    file_type: FileType
    original_name: str
    created_at: datetime
    model_config = {"from_attributes": True}


class PenDocumentResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    version: int
    original_name: str
    parsed_fields: dict | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ZipPreviewItem(BaseModel):
    name: str
    mockup: str | None = None
    pen: str | None = None
    product_name: str | None = None


class ZipUploadRequest(BaseModel):
    mapping: list[ZipPreviewItem]
    category: ProductCategory = ProductCategory.bad
