import asyncio
import uuid
from datetime import datetime, timezone
from celery.utils.log import get_task_logger
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


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

        try:
            # Load files
            mockup_res = await db.execute(select(Mockup).where(Mockup.id == task.mockup_id))
            mockup = mockup_res.scalar_one()
            pen_res = await db.execute(select(PenDocument).where(PenDocument.id == task.pen_id))
            pen = pen_res.scalar_one()

            storage = await get_storage_service(db)
            mockup_bytes = storage.download_file(mockup.s3_key)
            pen_bytes = storage.download_file(pen.s3_key)

            # Load product category
            product_res = await db.execute(select(Product).where(Product.id == mockup.product_id))
            product = product_res.scalar_one()
            category = product.category.value

            # Pipeline config from the admin panel (system_config); decryption handled by config_service.
            pipeline_cfg = await config_service.get_pipeline_config(db)
            mode = pipeline_cfg.get("pipeline_mode") or task.mode.value

            async def get_key(provider: str) -> str:
                return (await config_service.get_config(db, f"api_key_{provider}")) or ""

            if mode == "unified":
                llm_name = pipeline_cfg.get("unified_llm") or "anthropic"
                key = await get_key(llm_name)
                ocr_provider = get_ocr_provider(llm_name, key)
                llm_provider = get_llm_provider(llm_name, key)
            else:
                ocr_name = pipeline_cfg.get("ocr_provider") or "anthropic_vision"
                llm_name = pipeline_cfg.get("llm_provider") or "anthropic"
                ocr_provider = get_ocr_provider(ocr_name, await get_key(ocr_name.replace("_vision", "")))
                llm_provider = get_llm_provider(llm_name, await get_key(llm_name))

            # Stage 1: OCR
            # Render PDF pages to images and OCR via vision model — design PDFs have
            # text "в кривых"/scrambled text layers, so pdfplumber output is unreliable.
            import fitz
            from app.pipeline.base import OCRResult as _OCRResult
            image_for_layout = None
            if mockup.file_type.value == "pdf":
                pdfdoc = fitz.open(stream=mockup_bytes, filetype="pdf")
                page_texts = []
                for pno in range(min(len(pdfdoc), 3)):
                    img = pdfdoc[pno].get_pixmap(dpi=170).tobytes("jpeg")
                    if image_for_layout is None:
                        image_for_layout = img
                    page_texts.append((await ocr_provider.extract_text(img)).full_text)
                npages = len(pdfdoc)
                pdfdoc.close()
                ocr_result = _OCRResult(full_text="\n".join(page_texts), pages=npages)
            else:
                image_for_layout = mockup_bytes
                ocr_result = await ocr_provider.extract_text(mockup_bytes)

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

            # Parse PEN
            pen_fields = pen.parsed_fields or parse_pen_document(pen_bytes)

            all_issues: list[dict] = []

            # Stage 2: Spelling
            spelling_issues = await run_spelling_check(ocr_result.full_text, dictionary_terms, brand_whitelist, llm_provider)
            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.spelling, issues=spelling_issues, created_at=datetime.now(timezone.utc)))
            all_issues.extend(spelling_issues)

            # Stage 3: PEN comparison
            pen_issues = await run_pen_comparison(ocr_result.full_text, pen_fields, llm_provider, category)
            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.pen, issues=pen_issues, created_at=datetime.now(timezone.utc)))
            all_issues.extend(pen_issues)

            # Stage 4: Regulatory
            reg_issues = await run_regulatory_check(ocr_result.full_text, image_for_layout, category, rules, llm_provider)
            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.regulatory, issues=reg_issues, created_at=datetime.now(timezone.utc)))
            all_issues.extend(reg_issues)

            # Stage 5: Annotated PDF
            annotated_pdf_key = None
            if mockup.file_type.value == "pdf":
                annotated_bytes = generate_annotated_pdf(mockup_bytes, all_issues)
                annotated_pdf_key = f"reports/{task.id}/annotated.pdf"
                storage.upload_file(annotated_bytes, annotated_pdf_key, "application/pdf")

            db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.report, issues=[], annotated_pdf_s3_key=annotated_pdf_key, created_at=datetime.now(timezone.utc)))

            # Optional benchmark: compare against manual-review reference, if provided.
            benchmark = None
            if task.reference_text:
                benchmark = await run_benchmark(task.reference_text, all_issues, llm_provider)

            await db.execute(update(CheckTask).where(CheckTask.id == task.id).values(
                status=TaskStatus.COMPLETED, completed_at=datetime.now(timezone.utc), benchmark=benchmark
            ))
            await db.commit()
            logger.info(f"Task {task_id} completed with {len(all_issues)} issues")

        except Exception as exc:
            logger.error(f"Task {task_id} failed: {exc}", exc_info=True)
            await db.execute(update(CheckTask).where(CheckTask.id == task.id).values(
                status=TaskStatus.FAILED, completed_at=datetime.now(timezone.utc), error=str(exc)
            ))
            await db.commit()
            raise
