from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.users import User
from app.models.audit_log import AuditLog
from app.models.checks import CheckTask, TaskStatus
from app.services import config_service
from app.pipeline.providers import get_ocr_provider, get_llm_provider
from app.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    api_keys = await config_service.get_masked_api_keys(db)
    pipeline = await config_service.get_pipeline_config(db)
    s3_endpoint = await config_service.get_config(db, "s3_endpoint_url") or ""
    s3_bucket = await config_service.get_config(db, "s3_bucket") or ""
    return {"api_keys": api_keys, "pipeline": pipeline, "s3": {"endpoint_url": s3_endpoint, "bucket": s3_bucket}}


@router.put("/config")
async def update_config(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    api_keys = payload.get("api_keys", {})
    for provider, key_value in api_keys.items():
        if key_value and not key_value.startswith("****"):
            await config_service.set_config(db, f"api_key_{provider}", key_value, is_encrypted=True, updated_by_id=current_user.id)

    pipeline = payload.get("pipeline", {})
    for k, v in pipeline.items():
        await config_service.set_config(db, k, v or "", updated_by_id=current_user.id)

    s3 = payload.get("s3", {})
    for k, v in s3.items():
        encrypted = k in ("access_key", "secret_key")
        await config_service.set_config(db, f"s3_{k}", v or "", is_encrypted=encrypted, updated_by_id=current_user.id)

    return {"message": "Конфигурация сохранена"}


@router.post("/config/test-connection")
async def test_connection(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    provider_type = payload.get("provider_type", "llm")
    provider_name = payload.get("provider_name", "")
    api_key = await config_service.get_config(db, f"api_key_{provider_name}") or ""
    try:
        if provider_type == "storage":
            svc = await get_storage_service(db)
            ok = svc.test_connection()
        elif provider_type == "ocr":
            provider = get_ocr_provider(provider_name, api_key)
            ok = await provider.test_connection()
        else:
            provider = get_llm_provider(provider_name, api_key)
            ok = await provider.test_connection()
        return {"success": ok, "message": "Подключение успешно" if ok else "Ошибка подключения"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/logs")
async def get_logs(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
    logs = result.scalars().all()
    return [{"id": str(l.id), "user_id": str(l.user_id) if l.user_id else None, "action": l.action, "resource_type": l.resource_type, "resource_id": l.resource_id, "ip": l.ip_address, "created_at": l.created_at.isoformat()} for l in logs]


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    total = (await db.execute(select(func.count(CheckTask.id)))).scalar_one()
    completed = (await db.execute(select(func.count(CheckTask.id)).where(CheckTask.status == TaskStatus.COMPLETED))).scalar_one()
    failed = (await db.execute(select(func.count(CheckTask.id)).where(CheckTask.status == TaskStatus.FAILED))).scalar_one()
    return {"total_checks": total, "completed": completed, "failed": failed, "pending": total - completed - failed}
