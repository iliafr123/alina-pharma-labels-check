import io
import csv
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from datetime import datetime, timezone
from app.models.references import DictionaryEntry, BrandWhitelist, ChecklistRule, RuleCategory
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.users import User
from app.models.audit_log import AuditLog
from app.models.checks import CheckTask, TaskStatus
from app.services import config_service, error_service
from app.pipeline.providers import get_ocr_provider, get_llm_provider
from app.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/admin", tags=["admin"])

# Quality-gate settings an admin may override (defaults in quality_service.THRESHOLDS).
QUALITY_KEYS = {"px_per_mm_good", "px_per_mm_min", "sharpness_good", "sharpness_min",
                "contrast_min", "jpg_side_good", "jpg_side_min"}


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    api_keys = await config_service.get_masked_api_keys(db)
    pipeline = await config_service.get_pipeline_config(db)
    s3_endpoint = await config_service.get_config(db, "s3_endpoint_url") or ""
    s3_bucket = await config_service.get_config(db, "s3_bucket") or ""
    extras = await config_service.get_extras(db)
    debug_mode = (await config_service.get_config(db, "debug_mode")) == "true"
    providers_available = {}
    for p in config_service.API_KEY_PROVIDERS:
        providers_available[p] = bool(await config_service.get_config(db, f"api_key_{p}"))
    from app.services import quality_service
    quality = await quality_service.load_thresholds(db)
    return {"api_keys": api_keys, "pipeline": pipeline,
            "s3": {"endpoint_url": s3_endpoint, "bucket": s3_bucket}, "extras": extras,
            "debug_mode": debug_mode, "providers_available": providers_available,
            "quality": quality, "quality_defaults": quality_service.THRESHOLDS}


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

    if "debug_mode" in payload:
        await config_service.set_config(db, "debug_mode", "true" if payload["debug_mode"] else "false", updated_by_id=current_user.id)

    extras = payload.get("extras", {})
    if "yandex_folder_id" in extras:
        await config_service.set_config(db, "yandex_folder_id", extras.get("yandex_folder_id") or "", updated_by_id=current_user.id)
    if "abbyy_url" in extras and extras.get("abbyy_url"):
        await config_service.set_config(db, "abbyy_url", extras["abbyy_url"], updated_by_id=current_user.id)
    if extras.get("abbyy_password") and not extras["abbyy_password"].startswith("****"):
        await config_service.set_config(db, "abbyy_password", extras["abbyy_password"], is_encrypted=True, updated_by_id=current_user.id)
    if extras.get("selectel_api_token") and not extras["selectel_api_token"].startswith("****"):
        await config_service.set_config(db, "selectel_api_token", extras["selectel_api_token"], is_encrypted=True, updated_by_id=current_user.id)

    # Quality gate thresholds (blank value = keep the calibrated default).
    for k, v in (payload.get("quality") or {}).items():
        if k in QUALITY_KEYS:
            await config_service.set_config(db, f"quality_{k}", str(v) if v not in ("", None) else "",
                                            updated_by_id=current_user.id)

    return {"message": "Конфигурация сохранена"}


@router.post("/config/test-connection")
async def test_connection(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    provider_type = payload.get("provider_type", "llm")
    provider_name = payload.get("provider_name", "")
    try:
        if provider_type == "storage":
            ok = (await get_storage_service(db)).test_connection()
        elif provider_type == "ocr":
            ok = await (await config_service.build_ocr_provider(db, provider_name)).test_connection()
        else:
            ok = await (await config_service.build_llm_provider(db, provider_name)).test_connection()
        return {"success": ok, "message": "Подключение успешно" if ok else "Ошибка подключения"}
    except Exception as e:
        # Report the real cause (unpaid account, revoked key, wrong bucket) instead
        # of whatever str() the SDK happened to produce.
        err = await error_service.log_exception(
            db, e, provider=provider_name,
            subsystem="storage" if provider_type == "storage" else provider_type,
            path="/admin/config/test-connection", severity="warning")
        return {"success": False, "message": err.message, "error": err.to_dict()}


@router.post("/purge-queue")
async def purge_queue(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """Clear the broker queue and mark stale PENDING checks as FAILED (drains zombie backlog)."""
    from app.workers.celery_app import celery_app
    purged = None
    try:
        with celery_app.connection_for_write() as conn:
            purged = conn.default_channel.queue_purge("celery")
    except Exception as e:
        purged = f"err: {e}"
    res = await db.execute(update(CheckTask).where(CheckTask.status == TaskStatus.PENDING).values(
        status=TaskStatus.FAILED, error="stale/purged", completed_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"purged_messages": purged, "pending_marked_failed": res.rowcount}


def _parse_rows(filename: str, content: bytes) -> list[list[str]]:
    """Return rows (list of cell-string lists) from .xlsx or .csv content."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        return [[("" if c is None else str(c)).strip() for c in row] for row in ws.iter_rows(values_only=True)]
    text = content.decode("utf-8-sig", errors="replace")
    delim = ";" if text.count(";") > text.count(",") else ","
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), delimiter=delim)]


@router.post("/import/{kind}")
async def import_reference(
    kind: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Import dictionary terms / brands / checklist rules from .xlsx or .csv (skips duplicates)."""
    if kind not in ("dictionary", "brands", "checklist"):
        raise HTTPException(400, "kind: dictionary | brands | checklist")
    rows = _parse_rows(file.filename or "f.csv", await file.read())
    # Drop a header row if the first cell looks like a header.
    if rows and rows[0] and rows[0][0].lower() in ("term", "термин", "слово", "brand", "бренд", "rule_key", "ключ"):
        rows = rows[1:]
    added = 0
    for r in rows:
        if not r or not r[0]:
            continue
        try:
            if kind == "dictionary":
                term = r[0]
                if not (await db.execute(select(DictionaryEntry).where(DictionaryEntry.term == term))).scalar_one_or_none():
                    db.add(DictionaryEntry(term=term, category=(r[1] if len(r) > 1 and r[1] else "general"))); added += 1
            elif kind == "brands":
                if not (await db.execute(select(BrandWhitelist).where(BrandWhitelist.brand_name == r[0]))).scalar_one_or_none():
                    db.add(BrandWhitelist(brand_name=r[0])); added += 1
            else:  # checklist: rule_key, description, [category]
                key = r[0]
                desc = r[1] if len(r) > 1 else r[0]
                cat = (r[2].lower() if len(r) > 2 and r[2] else "all")
                cat = cat if cat in RuleCategory._value2member_map_ else "all"
                if not (await db.execute(select(ChecklistRule).where(ChecklistRule.rule_key == key))).scalar_one_or_none():
                    db.add(ChecklistRule(rule_key=key, description=desc, category=RuleCategory(cat))); added += 1
        except Exception:
            continue
    await db.commit()
    return {"kind": kind, "rows": len(rows), "added": added}


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


@router.get("/errors")
async def list_errors(
    code: str = "",
    subsystem: str = "",
    provider: str = "",
    source: str = "",
    search: str = "",
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Everything that failed, newest first - the screen the operator opens when a
    check dies and the cause is not obvious from the check itself."""
    from app.models.error_log import ErrorLog
    from sqlalchemy import or_

    q = select(ErrorLog).order_by(ErrorLog.created_at.desc())
    if code:
        q = q.where(ErrorLog.code == code)
    if subsystem:
        q = q.where(ErrorLog.subsystem == subsystem)
    if provider:
        q = q.where(ErrorLog.provider == provider)
    if source:
        q = q.where(ErrorLog.source == source)
    if search:
        like = f"%{search}%"
        q = q.where(or_(ErrorLog.title.ilike(like), ErrorLog.detail.ilike(like),
                        ErrorLog.code.ilike(like)))
    rows = (await db.execute(q.offset(skip).limit(min(limit, 500)))).scalars().all()
    return [{
        "id": str(r.id), "code": r.code, "title": r.title, "hint": r.hint,
        "detail": r.detail, "provider": r.provider, "subsystem": r.subsystem,
        "stage": r.stage, "source": r.source, "severity": r.severity,
        "http_status": r.http_status, "path": r.path, "task_id": r.task_id,
        "context": r.context, "traceback": r.traceback,
        "created_at": r.created_at.isoformat(),
    } for r in rows]


@router.get("/errors/summary")
async def errors_summary(hours: int = 24, db: AsyncSession = Depends(get_db),
                         _: User = Depends(require_admin)):
    """Counts per code over a window - shows at a glance whether one cause dominates."""
    from datetime import timedelta
    from app.models.error_log import ErrorLog

    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 24 * 30)))
    rows = (await db.execute(
        select(ErrorLog.code, ErrorLog.subsystem, ErrorLog.provider, func.count(ErrorLog.id))
        .where(ErrorLog.created_at >= since)
        .group_by(ErrorLog.code, ErrorLog.subsystem, ErrorLog.provider)
        .order_by(func.count(ErrorLog.id).desc())
    )).all()
    total = sum(r[3] for r in rows)
    return {"hours": hours, "total": total,
            "by_code": [{"code": c, "subsystem": s, "provider": p, "count": n}
                        for c, s, p, n in rows]}


@router.delete("/errors")
async def clear_errors(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    from sqlalchemy import delete
    from app.models.error_log import ErrorLog

    res = await db.execute(delete(ErrorLog))
    db.add(AuditLog(user_id=current_user.id, action="clear_error_log", resource_type="error_log"))
    await db.commit()
    return {"deleted": res.rowcount}


@router.get("/balances")
async def get_balances(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """Per-provider balance/quota. Providers without a balance API are reported as
    such rather than guessed at - see app/services/balance_service.py."""
    from app.services import balance_service

    entries = await balance_service.get_balances(db)
    rates = await balance_service.get_rates()
    return {"balances": entries,
            "rates": {k: v for k, v in rates.items() if k in ("USD", "EUR", "ILS", "RUB")},
            "rates_source": "ЦБ РФ (cbr-xml-daily.ru)"}


@router.put("/balances/{provider}")
async def set_manual_balance(
    provider: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Record a balance by hand for providers that expose no API (Gemini, OpenAI,
    Anthropic, Grok). Stored with its own timestamp and always shown as manual."""
    from app.services import balance_service

    if provider not in balance_service.ALL_PROVIDERS:
        raise HTTPException(400, f"Неизвестный провайдер: {provider}")
    amount = payload.get("amount")
    if amount in ("", None):
        await balance_service.set_manual(db, provider, None, "", user_id=current_user.id)
        return {"message": "Ручное значение удалено"}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise HTTPException(400, "Сумма должна быть числом")
    saved = await balance_service.set_manual(
        db, provider, amount, str(payload.get("currency") or "RUB"),
        str(payload.get("note") or ""), user_id=current_user.id)
    db.add(AuditLog(user_id=current_user.id, action="set_manual_balance",
                    resource_type="balance", resource_id=provider))
    await db.commit()
    return {"message": "Сохранено", "balance": saved}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    total = (await db.execute(select(func.count(CheckTask.id)))).scalar_one()
    completed = (await db.execute(select(func.count(CheckTask.id)).where(CheckTask.status == TaskStatus.COMPLETED))).scalar_one()
    failed = (await db.execute(select(func.count(CheckTask.id)).where(CheckTask.status == TaskStatus.FAILED))).scalar_one()

    # Surface the dominant failure cause on the dashboard, not just a count.
    from datetime import timedelta
    from app.models.error_log import ErrorLog
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_errors = (await db.execute(
        select(func.count(ErrorLog.id)).where(ErrorLog.created_at >= since))).scalar_one()
    top = (await db.execute(
        select(ErrorLog.code, ErrorLog.title, func.count(ErrorLog.id).label("n"))
        .where(ErrorLog.created_at >= since)
        .group_by(ErrorLog.code, ErrorLog.title)
        .order_by(func.count(ErrorLog.id).desc()).limit(1))).first()
    return {"total_checks": total, "completed": completed, "failed": failed,
            "pending": total - completed - failed,
            "errors_24h": recent_errors,
            "top_error": ({"code": top[0], "title": top[1], "count": top[2]} if top else None)}
