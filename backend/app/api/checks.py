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
from app.services.export_service import generate_excel_report, generate_word_report
from app.schemas.checks import CheckCreate, CheckTaskResponse
import io

router = APIRouter(prefix="/checks", tags=["checks"])


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


@router.get("/history", response_model=list[CheckTaskResponse])
async def check_history(
    product_name: str = "",
    status: str = "",
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_specialist),
):
    q = select(CheckTask).order_by(CheckTask.created_at.desc())
    if status:
        q = q.where(CheckTask.status == status)
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


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
    return task


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
    word_bytes = generate_word_report(str(task_id), "Продукт", issues)
    return StreamingResponse(
        io.BytesIO(word_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report_{task_id}.docx"},
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
