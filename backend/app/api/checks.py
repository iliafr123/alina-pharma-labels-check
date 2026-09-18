import uuid
import difflib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import get_db
from app.core.deps import require_specialist
from app.models.users import User
from app.models.checks import CheckTask, CheckResult, TaskStatus
from app.models.files import Mockup, PenDocument
from app.models.products import Product
from app.models.audit_log import AuditLog
from app.services.storage import storage_service, get_storage_service
from app.services.export_service import (generate_excel_report, generate_word_report, generate_md_report,
                                         generate_batch_md, generate_batch_word)
from app.services import config_service
from app.schemas.checks import CheckCreate, CheckTaskResponse, BatchCreate, CheckHistoryItem
import io

router = APIRouter(prefix="/checks", tags=["checks"])

# LLM analyzers and OCR providers the pipeline supports (vision-capable LLMs double as OCR).
_LLM_PROVIDERS = ["gemini", "grok", "openai", "anthropic"]
_OCR_PROVIDERS = ["yandex_vision", "gemini", "openai", "anthropic", "abbyy"]


@router.get("/pipeline-options")
async def pipeline_options(db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    """For the check screen: whether DEBUG MODE is on + which providers have a configured key."""
    debug = (await config_service.get_config(db, "debug_mode")) == "true"
    llm = [p for p in _LLM_PROVIDERS if await config_service.get_config(db, f"api_key_{p}")]
    ocr = []
    for p in _OCR_PROVIDERS:
        key_name = "anthropic" if p in ("anthropic", "anthropic_vision") else p
        if await config_service.get_config(db, f"api_key_{key_name}"):
            ocr.append(p)
    # The check screen needs to explain *why* the Run button is disabled, so it has
    # to know whether the pipeline is actually configured at all.
    cfg = await config_service.get_pipeline_config(db)
    mode = cfg.get("pipeline_mode") or "hybrid"
    if mode == "unified":
        active_llm = cfg.get("unified_llm") or ""
        active_ocr = active_llm
    else:
        active_llm = cfg.get("llm_provider") or ""
        active_ocr = cfg.get("ocr_provider") or ""
    return {"debug_mode": debug, "llm_providers": llm, "ocr_providers": ocr,
            "pipeline_mode": mode, "active_llm": active_llm, "active_ocr": active_ocr,
            "configured": bool(active_llm and active_ocr and llm)}


@router.get("/provider-balance")
async def provider_balance(db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    """Balance/quota of the provider this pipeline is set to use, in roubles where a
    figure exists. Shown on the check screen so a specialist notices an empty account
    before starting a run rather than after it fails."""
    from app.services import balance_service

    entry = await balance_service.get_active_balance(db)
    if not entry:
        return {"balance": None, "message": "Провайдер LLM не выбран в конфигурации пайплайна."}
    return {"balance": entry}


@router.post("", response_model=CheckTaskResponse, status_code=201)
async def create_check(
    data: CheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_specialist),
):
    task = CheckTask(
        mockup_id=data.mockup_id,
        pen_id=data.pen_id,
        mode=data.mode,
        pipeline_config=data.pipeline_config,
        reference_text=data.reference_text,
        focus_prompt=data.focus_prompt,
        created_by=current_user.id,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    db.add(AuditLog(user_id=current_user.id, action="create_check", resource_type="check_task"))
    await db.commit()
    await db.refresh(task)

    from app.workers.tasks import run_check_pipeline
    run_check_pipeline.delay(str(task.id))
    return task


@router.post("/batch", status_code=201)
async def create_batch(
    data: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_specialist),
):
    """Batch check: up to 20 label pairs sharing config/focus, grouped by a batch_id."""
    if not data.items or len(data.items) > 20:
        raise HTTPException(400, "От 1 до 20 этикеток за раз")
    batch_id = uuid.uuid4().hex
    ids = []
    for it in data.items:
        task = CheckTask(mockup_id=it.mockup_id, pen_id=it.pen_id, pipeline_config=data.pipeline_config,
                         focus_prompt=data.focus_prompt, batch_id=batch_id, created_by=current_user.id,
                         status=TaskStatus.PENDING)
        db.add(task)
        await db.flush()
        ids.append(str(task.id))
    db.add(AuditLog(user_id=current_user.id, action="create_batch", resource_type="batch", resource_id=batch_id))
    await db.commit()
    from app.workers.tasks import run_check_pipeline
    for tid in ids:
        run_check_pipeline.delay(tid)
    return {"batch_id": batch_id, "count": len(ids), "task_ids": ids}


@router.get("/batch/{batch_id}", response_model=list[CheckTaskResponse])
async def get_batch(batch_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    res = await db.execute(select(CheckTask).where(CheckTask.batch_id == batch_id).order_by(CheckTask.created_at))
    return res.scalars().all()


async def _product_name(db: AsyncSession, mockup_id: uuid.UUID) -> str:
    """Full product name for a mockup; falls back to a short id if the row is gone."""
    row = (await db.execute(
        select(Product.name).join(Mockup, Mockup.product_id == Product.id)
        .where(Mockup.id == mockup_id)
    )).scalar_one_or_none()
    return row or f"без названия ({str(mockup_id)[:8]})"


async def _task_product_name(db: AsyncSession, task_id: uuid.UUID) -> str:
    row = (await db.execute(
        select(Product.name)
        .join(Mockup, Mockup.product_id == Product.id)
        .join(CheckTask, CheckTask.mockup_id == Mockup.id)
        .where(CheckTask.id == task_id)
    )).scalar_one_or_none()
    return row or "Продукт"


async def _batch_items(db: AsyncSession, batch_id: str) -> list[dict]:
    res = await db.execute(select(CheckTask).where(CheckTask.batch_id == batch_id).order_by(CheckTask.created_at))
    items = []
    for t in res.scalars().all():
        name = await _product_name(db, t.mockup_id)
        issues = [i for cr in t.results if cr.issues for i in cr.issues if isinstance(i, dict) and i.get("module")]
        items.append({"name": name, "status": t.status.value, "issues": issues})
    return items


@router.get("/batch/{batch_id}/export/{fmt}")
async def export_batch(batch_id: str, fmt: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    items = await _batch_items(db, batch_id)
    if fmt == "word":
        data = generate_batch_word(batch_id, items)
        mt = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"; ext = "docx"
    else:
        data = generate_batch_md(batch_id, items); mt = "text/markdown"; ext = "md"
    return StreamingResponse(io.BytesIO(data), media_type=mt,
                             headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.{ext}"})


@router.get("/history", response_model=list[CheckHistoryItem])
async def check_history(
    product_name: str = "",
    status: str = "",
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    """Journal rows joined through to the product, so each line names the БАД
    that was checked instead of a mockup UUID."""
    # Outer joins on purpose: a check whose mockup or product row was removed must
    # still appear in the journal (with a placeholder name) rather than disappear.
    q = (
        select(CheckTask, Product.name, Product.category, Mockup.original_name, Mockup.version)
        .outerjoin(Mockup, Mockup.id == CheckTask.mockup_id)
        .outerjoin(Product, Product.id == Mockup.product_id)
        .order_by(CheckTask.created_at.desc())
    )
    if status:
        q = q.where(CheckTask.status == status)
    if product_name:
        q = q.where(Product.name.ilike(f"%{product_name}%"))

    rows = (await db.execute(q.offset(skip).limit(limit))).all()
    items = []
    for task, name, category, mockup_name, version in rows:
        issues = [i for cr in task.results if cr.issues
                  for i in cr.issues if isinstance(i, dict) and i.get("module")]
        items.append(CheckHistoryItem(
            id=task.id,
            product_name=name or f"без названия ({str(task.mockup_id)[:8]})",
            category=category.value if category is not None else None,
            mockup_name=mockup_name,
            mockup_version=version,
            status=task.status,
            mode=task.mode,
            created_at=task.created_at,
            completed_at=task.completed_at,
            error=task.error,
            error_code=task.error_code,
            error_details=task.error_details,
            issues_count=len(issues),
            batch_id=task.batch_id,
        ))
    return items


@router.get("/{task_id}", response_model=CheckTaskResponse)
async def get_check(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    result = await db.execute(select(CheckTask).where(CheckTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Проверка не найдена")
    resp = CheckTaskResponse.model_validate(task)
    resp.product_name = await _product_name(db, task.mockup_id)
    return resp


@router.get("/{task_id}/issues")
async def get_issues(
    task_id: uuid.UUID,
    issue_type: str = "",
    module: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    result = await db.execute(select(CheckResult).where(CheckResult.task_id == task_id))
    results = result.scalars().all()
    all_issues = []
    for cr in results:
        if cr.issues:
            for issue in cr.issues:
                if isinstance(issue, dict):
                    if issue_type and issue.get("type") != issue_type:
                        continue
                    if module and issue.get("module") != module:
                        continue
                    all_issues.append(issue)
    return {"issues": all_issues, "total": len(all_issues)}


@router.get("/{task_id}/report/pdf")
async def get_report_pdf(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    result = await db.execute(
        select(CheckResult).where(CheckResult.task_id == task_id, CheckResult.stage == "report")
    )
    report = result.scalar_one_or_none()
    if not report or not report.annotated_pdf_s3_key:
        raise HTTPException(404, "Аннотированный PDF не найден")
    storage = await get_storage_service(db)
    url = storage.generate_presigned_url(report.annotated_pdf_s3_key)
    return {"url": url}


@router.get("/{task_id}/export/excel")
async def export_excel(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    result = await db.execute(select(CheckResult).where(CheckResult.task_id == task_id))
    results = result.scalars().all()
    issues = [i for cr in results if cr.issues for i in cr.issues if isinstance(i, dict) and i.get("module")]
    excel_bytes = generate_excel_report(str(task_id), issues)
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=report_{task_id}.xlsx"},
    )


@router.get("/{task_id}/export/word")
async def export_word(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    result = await db.execute(select(CheckResult).where(CheckResult.task_id == task_id))
    results = result.scalars().all()
    issues = [i for cr in results if cr.issues for i in cr.issues if isinstance(i, dict) and i.get("module")]
    word_bytes = generate_word_report(str(task_id), await _task_product_name(db, task_id), issues)
    return StreamingResponse(
        io.BytesIO(word_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report_{task_id}.docx"},
    )


@router.get("/{task_id}/export/md")
async def export_md(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    result = await db.execute(select(CheckResult).where(CheckResult.task_id == task_id))
    results = result.scalars().all()
    issues = [i for cr in results if cr.issues for i in cr.issues if isinstance(i, dict) and i.get("module")]
    md_bytes = generate_md_report(str(task_id), await _task_product_name(db, task_id), issues)
    return StreamingResponse(
        io.BytesIO(md_bytes), media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=report_{task_id}.md"},
    )


@router.post("/{task_id}/approve")
async def approve_check(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_specialist),
):
    result = await db.execute(select(CheckTask).where(CheckTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Проверка не найдена")
    await db.execute(update(CheckTask).where(CheckTask.id == task_id).values(
        approved_by=current_user.id, approved_at=datetime.now(timezone.utc)
    ))
    db.add(AuditLog(user_id=current_user.id, action="approve_check", resource_type="check_task", resource_id=str(task_id)))
    await db.commit()
    return {"message": "Макет согласован для отправки в типографию"}


@router.post("/{task_id}/cancel")
async def cancel_check(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_specialist),
):
    await db.execute(update(CheckTask).where(CheckTask.id == task_id).values(status=TaskStatus.CANCELLED))
    await db.commit()
    return {"message": "Задача отменена"}


@router.get("/diff/{mockup_id_a}/{mockup_id_b}")
async def diff_mockups(
    mockup_id_a: uuid.UUID,
    mockup_id_b: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    async def get_text(mockup_id: uuid.UUID) -> str:
        result = await db.execute(
            select(CheckTask).where(CheckTask.mockup_id == mockup_id).order_by(CheckTask.created_at.desc())
        )
        task = result.scalars().first()
        if not task:
            return ""
        ocr_res = await db.execute(
            select(CheckResult).where(CheckResult.task_id == task.id, CheckResult.stage == "ocr")
        )
        ocr = ocr_res.scalar_one_or_none()
        if ocr and ocr.issues:
            return ocr.issues[0].get("full_text", "") if isinstance(ocr.issues[0], dict) else ""
        return ""

    text_a = (await get_text(mockup_id_a)).splitlines()
    text_b = (await get_text(mockup_id_b)).splitlines()
    diff = list(difflib.unified_diff(text_a, text_b, lineterm="", n=3))
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    return {"added": added, "removed": removed, "unified": diff}
