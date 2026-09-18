import asyncio
import uuid
from datetime import datetime, timezone
from celery.utils.log import get_task_logger
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)

# Failures that a retry cannot help with: retrying only wastes provider quota and
# hides the real message behind three more identical errors.
_NO_RETRY_CODES = {
    "MOCKUP_QUALITY_TOO_LOW", "FILE_UNREADABLE", "FILE_EMPTY", "FILE_TOO_LARGE",
    "FILE_UNSUPPORTED", "PROVIDER_NOT_CONFIGURED", "LLM_AUTH", "LLM_PAYMENT_REQUIRED",
    "LLM_MODEL_NOT_FOUND", "LLM_QUOTA", "STORAGE_NOT_CONFIGURED", "STORAGE_BAD_CREDENTIALS",
    "STORAGE_PAYMENT_REQUIRED", "STORAGE_FORBIDDEN", "STORAGE_NO_BUCKET", "STORAGE_FILE_MISSING",
}


@celery_app.task(bind=True, name="run_check_pipeline", max_retries=3, default_retry_delay=10)
def run_check_pipeline(self, task_id: str):
    asyncio.run(_run_pipeline(task_id))


async def _run_pipeline(task_id: str):
    from sqlalchemy import select, update
    from app.core.database import AsyncSessionLocal
    from app.models.checks import CheckTask, CheckResult, TaskStatus, CheckStage
    from app.models.files import Mockup, PenDocument
    from app.models.references import DictionaryEntry, BrandWhitelist, ChecklistRule
    from app.models.config import SystemConfig
    from app.models.products import Product
    from app.services.storage import get_storage_service
    from app.pipeline.providers.pdf_extractor import extract_text_layer
    from app.pipeline.providers import get_ocr_provider, get_llm_provider
    from app.pipeline.pen_parser import parse_pen_document
    from app.pipeline.stages.spelling_check import run_spelling_check
    from app.pipeline.stages.pen_comparison import run_pen_comparison
    from app.pipeline.stages.regulatory_check import run_regulatory_check
    from app.pipeline.stages.benchmark import run_benchmark
    from app.pipeline.report_generator import generate_annotated_pdf
    from app.services import config_service

    async with AsyncSessionLocal() as db:
        # Load task
        result = await db.execute(select(CheckTask).where(CheckTask.id == uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        await db.execute(update(CheckTask).where(CheckTask.id == task.id).values(
            status=TaskStatus.RUNNING, started_at=datetime.now(timezone.utc)
        ))
        await db.commit()

        # Tracked so a failure can say which stage and which provider broke.
        stage_name = "init"
        llm_name = ocr_name = ""
        try:
            # Load files
            mockup_res = await db.execute(select(Mockup).where(Mockup.id == task.mockup_id))
            mockup = mockup_res.scalar_one()
            pen_res = await db.execute(select(PenDocument).where(PenDocument.id == task.pen_id))
            pen = pen_res.scalar_one()

            storage = await get_storage_service(db)
            stage_name = "storage"
            mockup_bytes = storage.download_file(mockup.s3_key)
            pen_bytes = storage.download_file(pen.s3_key)

            # Quality gate: refuse to spend a model call on a file whose text cannot
            # be read. The report is stored either way so the UI can explain itself.
            from app.services import quality_service
            stage_name = "quality"
            thresholds = await quality_service.load_thresholds(db)
            quality_report = quality_service.assess(
                mockup_bytes, filename=mockup.original_name,
                content_type="application/pdf" if mockup.file_type.value == "pdf" else "image/jpeg",
                thresholds=thresholds)
            await db.execute(update(CheckTask).where(CheckTask.id == task.id).values(
                quality=quality_report.to_dict()))
            await db.commit()
            if not quality_report.ok:
                raise quality_report.as_error()
            if quality_report.level == "acceptable":
                logger.warning(f"Task {task_id}: mockup quality is borderline "
                               f"({quality_report.metrics.get('effective_px_per_mm')} px/mm)")

            # Load product category
            product_res = await db.execute(select(Product).where(Product.id == mockup.product_id))
            product = product_res.scalar_one()
            category = product.category.value

            # Pipeline config: admin panel (system_config) is the base; a per-check
            # pipeline_config overrides it (used for A/B provider comparison).
            admin_cfg = await config_service.get_pipeline_config(db)
            override = task.pipeline_config or {}
            pipeline_cfg = {**admin_cfg, **{k: v for k, v in override.items() if v}}
            mode = pipeline_cfg.get("pipeline_mode") or task.mode.value

            stage_name = "config"
            if mode == "unified":
                llm_name = ocr_name = pipeline_cfg.get("unified_llm") or "anthropic"
            else:
                ocr_name = pipeline_cfg.get("ocr_provider") or "anthropic_vision"
                llm_name = pipeline_cfg.get("llm_provider") or "anthropic"

            # Fail with a clear reason instead of letting the provider reject an empty key.
            from app.core.errors import not_configured
            ocr_key_name = "anthropic" if ocr_name in ("anthropic", "anthropic_vision") else ocr_name
            if not await config_service.get_config(db, f"api_key_{ocr_key_name}"):
                raise not_configured(ocr_name, "ocr")
            if not await config_service.get_config(db, f"api_key_{llm_name}"):
                raise not_configured(llm_name, "llm")
            ocr_provider = await config_service.build_ocr_provider(db, ocr_name)
            llm_provider = await config_service.build_llm_provider(db, llm_name)

            # Optional per-check focus instruction → steers the analysis LLM (not OCR).
            focus = (task.focus_prompt or "").strip()
            if focus:
                llm_provider._focus = focus

            stage_name = "ocr"
            # Stage 1: OCR
            # Render PDF pages to images and OCR via vision model — design PDFs have
            # text "в кривых"/scrambled text layers, so pdfplumber output is unreliable.
            import fitz, io as _io
            from PIL import Image, ImageChops
            from app.pipeline.base import OCRResult as _OCRResult

            def _prep_image(raw: bytes) -> bytes:
                """Crop empty (white) margins and cap long side to 2400px → crisp OCR input.
                Print PDFs are often an A4 sheet with a small label; cropping makes text large."""
                try:
                    im = Image.open(_io.BytesIO(raw)).convert("RGB")
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bbox = ImageChops.difference(im, bg).getbbox()
                    if bbox:
                        im = im.crop(bbox)
                    w, h = im.size
                    if max(w, h) > 2400:
                        s = 2400 / max(w, h)
                        im = im.resize((int(w * s), int(h * s)))
                    out = _io.BytesIO(); im.save(out, "JPEG", quality=90)
                    return out.getvalue()
                except Exception:
                    return raw

            image_for_layout = None
            if mockup.file_type.value == "pdf":
                pdfdoc = fitz.open(stream=mockup_bytes, filetype="pdf")
                page_texts = []
                for pno in range(min(len(pdfdoc), 3)):
                    # Render at high DPI then crop whitespace — small labels on A4 sheets were
                    # rendered too small at low DPI, garbling OCR. Pixmap freed each page (memory).
                    pix = pdfdoc[pno].get_pixmap(dpi=340)
                    img = _prep_image(pix.tobytes("png"))
                    pix = None
                    if image_for_layout is None:
                        image_for_layout = img
                    page_texts.append((await ocr_provider.extract_text(img)).full_text)
                npages = len(pdfdoc)
                pdfdoc.close()
                ocr_result = _OCRResult(full_text="\n".join(page_texts), pages=npages)
            else:
                image_for_layout = _prep_image(mockup_bytes)
                ocr_result = await ocr_provider.extract_text(image_for_layout)

            # An empty OCR result means every later stage is analysing nothing - fail
            # here with a cause rather than returning a confidently empty report.
            if len((ocr_result.full_text or "").strip()) < 20:
                from app.core.errors import AppError
                raise AppError(
                    "OCR_EMPTY", "Текст на макете не распознан.",
                    "Модель не увидела текста. Обычные причины: макет состоит из "
                    "кривых без растра нужного разрешения, файл перевёрнут/пустой, "
                    "или выбран OCR-провайдер без поддержки vision. "
                    "Проверьте макет и связку OCR в Конфигурации пайплайна.",
                    detail=f"ocr_provider={ocr_name}, chars={len(ocr_result.full_text or '')}",
                    provider=ocr_name, subsystem="ocr", stage="ocr", http_status=422)

            ocr_cr = CheckResult(
                id=uuid.uuid4(), task_id=task.id, stage=CheckStage.ocr,
                issues=[{"full_text": ocr_result.full_text[:2000]}],
                created_at=datetime.now(timezone.utc),
            )
            db.add(ocr_cr)

            # Load references
            dict_res = await db.execute(select(DictionaryEntry))
            dictionary_terms = [r.term for r in dict_res.scalars().all()]
            brand_res = await db.execute(select(BrandWhitelist))
            brand_whitelist = [r.brand_name for r in brand_res.scalars().all()]
            rule_res = await db.execute(select(ChecklistRule).where(ChecklistRule.is_active == True))
            rules = [{"rule_key": r.rule_key, "description": r.description, "category": r.category.value} for r in rule_res.scalars().all()]

            stage_name = "pen_parse"
            # Parse PEN
            pen_fields = pen.parsed_fields or parse_pen_document(pen_bytes)

            all_issues: list[dict] = []

            stage_name = "spelling"
            # Stage 2: Spelling
            spelling_issues = await run_spelling_check(ocr_result.full_text, dictionary_terms, brand_whitelist, llm_provider)
            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.spelling, issues=spelling_issues, created_at=datetime.now(timezone.utc)))
            all_issues.extend(spelling_issues)

            stage_name = "pen"
            # Stage 3: PEN comparison
            pen_issues = await run_pen_comparison(ocr_result.full_text, pen_fields, llm_provider, category)
            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.pen, issues=pen_issues, created_at=datetime.now(timezone.utc)))
            all_issues.extend(pen_issues)

            stage_name = "regulatory"
            # Stage 4: Regulatory
            reg_issues = await run_regulatory_check(ocr_result.full_text, image_for_layout, category, rules, llm_provider)
            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.regulatory, issues=reg_issues, created_at=datetime.now(timezone.utc)))
            all_issues.extend(reg_issues)

            stage_name = "report"
            # Stage 5: Annotated PDF
            annotated_pdf_key = None
            if mockup.file_type.value == "pdf":
                annotated_bytes = generate_annotated_pdf(mockup_bytes, all_issues)
                annotated_pdf_key = f"reports/{task.id}/annotated.pdf"
                storage.upload_file(annotated_bytes, annotated_pdf_key, "application/pdf")

            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.report, issues=[], annotated_pdf_s3_key=annotated_pdf_key, created_at=datetime.now(timezone.utc)))

            # Structured checklist (доп. требования): per mandatory element ✓/✗ + explanation.
            checklist = []
            try:
                from app.pipeline.providers.openai_provider import CHECKLIST_ITEMS
                cl = await llm_provider.build_checklist(ocr_result.full_text, pen_fields, CHECKLIST_ITEMS)
                checklist = (cl or {}).get("checklist") or []
            except Exception as ce:
                # Non-fatal: the check still has its issues list. Record it so an empty
                # checklist on the result screen has a visible explanation.
                from app.core.errors import classify
                from app.services.error_service import log_error
                cerr = classify(ce, provider=llm_name, subsystem="llm", stage="checklist")
                cerr.title = f"Чек-лист обязательных элементов не построен. {cerr.title}"
                logger.error(f"checklist failed: [{cerr.code}] {cerr.detail[:200]}")
                await log_error(db, cerr, source="worker", task_id=task_id,
                                exc=ce, severity="warning")

            # Optional benchmark: compare against manual-review reference, if provided.
            benchmark = None
            if task.reference_text:
                benchmark = await run_benchmark(task.reference_text, all_issues, llm_provider)

            await db.execute(update(CheckTask).where(CheckTask.id == task.id).values(
                status=TaskStatus.COMPLETED, completed_at=datetime.now(timezone.utc),
                benchmark=benchmark, checklist=checklist
            ))
            await db.commit()
            logger.info(f"Task {task_id} completed with {len(all_issues)} issues")

        except Exception as exc:
            # Turn the raw failure into something the operator can act on, store it on
            # the task (shown on the result screen) and in the error log (admin screen).
            from app.core.errors import classify
            from app.services.error_service import log_error

            provider = ocr_name if stage_name == "ocr" else llm_name
            endpoint = bucket = ""
            try:
                endpoint = (await config_service.get_config(db, "s3_endpoint_url")) or ""
                bucket = (await config_service.get_config(db, "s3_bucket")) or ""
            except Exception:
                pass

            err = classify(exc, provider=provider, stage=stage_name,
                           subsystem="ocr" if stage_name == "ocr" else "llm",
                           endpoint=endpoint, bucket=bucket)
            logger.error(f"Task {task_id} failed at stage={stage_name}: "
                         f"[{err.code}] {err.title} | {err.detail[:300]}", exc_info=True)
            try:
                await db.rollback()
            except Exception:
                pass
            await db.execute(update(CheckTask).where(CheckTask.id == task.id).values(
                status=TaskStatus.FAILED, completed_at=datetime.now(timezone.utc),
                error=err.message, error_code=err.code, error_details=err.to_dict(),
            ))
            await db.commit()
            await log_error(db, err, source="worker", task_id=task_id, exc=exc)

            # A configuration or quality problem will not fix itself on retry, and a
            # retry storm just burns provider quota.
            if err.code in _NO_RETRY_CODES:
                return
            raise
