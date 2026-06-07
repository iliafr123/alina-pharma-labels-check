import io
import uuid
import zipfile
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.files import Mockup, PenDocument, FileType
from app.models.products import Product, ProductCategory
from app.models.audit_log import AuditLog
from app.services.storage import storage_service, get_storage_service

ALLOWED_MOCKUP_TYPES = {"application/pdf", "image/jpeg", "image/jpg"}
ALLOWED_PEN_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
MAX_MOCKUP_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_PEN_SIZE = 20 * 1024 * 1024       # 20 MB


def _detect_file_type(filename: str, content_type: str) -> FileType:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf" or "pdf" in content_type:
        return FileType.pdf
    return FileType.jpg


async def _next_version(db: AsyncSession, model, product_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.max(model.version)).where(model.product_id == product_id)
    )
    current = result.scalar_one_or_none()
    return (current or 0) + 1


async def upload_mockup(
    db: AsyncSession,
    product_id: uuid.UUID,
    file: UploadFile,
    uploaded_by_id: uuid.UUID,
) -> Mockup:
    content = await file.read()
    if len(content) > MAX_MOCKUP_SIZE:
        raise HTTPException(400, "Файл макета превышает максимальный размер 100 МБ")
    file_type = _detect_file_type(file.filename or "", file.content_type or "")
    version = await _next_version(db, Mockup, product_id)
    storage = await get_storage_service(db)
    s3_key = storage.generate_s3_key(str(product_id), "mockups", file.filename or "mockup")
    content_type = "application/pdf" if file_type == FileType.pdf else "image/jpeg"
    storage.upload_file(content, s3_key, content_type)
    mockup = Mockup(
        product_id=product_id, version=version, file_type=file_type,
        s3_key=s3_key, original_name=file.filename or "mockup",
        uploaded_by=uploaded_by_id,
    )
    db.add(mockup)
    db.add(AuditLog(user_id=uploaded_by_id, action="upload_mockup", resource_type="mockup"))
    await db.commit()
    await db.refresh(mockup)
    return mockup


async def upload_pen(
    db: AsyncSession,
    product_id: uuid.UUID,
    file: UploadFile,
    uploaded_by_id: uuid.UUID,
) -> PenDocument:
    content = await file.read()
    if len(content) > MAX_PEN_SIZE:
        raise HTTPException(400, "Файл ПЭН превышает максимальный размер 20 МБ")
    version = await _next_version(db, PenDocument, product_id)
    storage = await get_storage_service(db)
    s3_key = storage.generate_s3_key(str(product_id), "pen", file.filename or "pen.docx")
    storage.upload_file(content, s3_key, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    pen = PenDocument(
        product_id=product_id, version=version, s3_key=s3_key,
        original_name=file.filename or "pen.docx", uploaded_by=uploaded_by_id,
    )
    db.add(pen)
    db.add(AuditLog(user_id=uploaded_by_id, action="upload_pen", resource_type="pen_document"))
    await db.commit()
    await db.refresh(pen)
    return pen


async def process_zip(zip_bytes: bytes) -> list[dict]:
    """Parse ZIP and return list of {name, mockup_filename, pen_filename}."""
    groups: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            basename = name.rsplit("/", 1)[-1]
            stem = basename.rsplit(".", 1)[0]
            ext = basename.rsplit(".", 1)[-1].lower()
            if ext in ("pdf", "jpg", "jpeg"):
                groups.setdefault(stem, {})["mockup"] = name
            elif ext == "docx":
                groups.setdefault(stem, {})["pen"] = name
    return [{"name": k, "mockup": v.get("mockup"), "pen": v.get("pen")} for k, v in groups.items()]


async def confirm_zip_upload(
    db: AsyncSession,
    zip_bytes: bytes,
    mapping: list[dict],
    uploaded_by_id: uuid.UUID,
    category: ProductCategory,
) -> list[dict]:
    results = []
    storage = await get_storage_service(db)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for item in mapping:
            product_name = item.get("product_name") or item["name"]
            result = await db.execute(select(Product).where(Product.name == product_name))
            product = result.scalar_one_or_none()
            if not product:
                product = Product(name=product_name, category=category, created_by=uploaded_by_id)
                db.add(product)
                await db.flush()

            uploads = {"product": product_name, "mockup": None, "pen": None}
            if item.get("mockup"):
                data = zf.read(item["mockup"])
                fname = item["mockup"].rsplit("/", 1)[-1]
                ft = _detect_file_type(fname, "")
                ver = await _next_version(db, Mockup, product.id)
                key = storage.generate_s3_key(str(product.id), "mockups", fname)
                ct = "application/pdf" if ft == FileType.pdf else "image/jpeg"
                storage.upload_file(data, key, ct)
                db.add(Mockup(product_id=product.id, version=ver, file_type=ft, s3_key=key, original_name=fname, uploaded_by=uploaded_by_id))
                uploads["mockup"] = fname

            if item.get("pen"):
                data = zf.read(item["pen"])
                fname = item["pen"].rsplit("/", 1)[-1]
                ver = await _next_version(db, PenDocument, product.id)
                key = storage.generate_s3_key(str(product.id), "pen", fname)
                storage.upload_file(data, key, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                db.add(PenDocument(product_id=product.id, version=ver, s3_key=key, original_name=fname, uploaded_by=uploaded_by_id))
                uploads["pen"] = fname

            results.append(uploads)
        await db.commit()
    return results
