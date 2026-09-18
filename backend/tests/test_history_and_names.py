"""The journal must name the product, not print a mockup UUID."""
import uuid
from datetime import datetime, timezone

import pytest_asyncio

from app.models.checks import CheckTask, CheckResult, TaskStatus, CheckStage, PipelineMode
from app.models.files import Mockup, FileType, PenDocument
from app.models.products import Product, ProductCategory


async def _seed(db, name: str, status=TaskStatus.COMPLETED, issues=None,
                created_at=None, **task_kw):
    product = Product(id=uuid.uuid4(), name=name, category=ProductCategory.bad)
    db.add(product)
    await db.flush()
    mockup = Mockup(id=uuid.uuid4(), product_id=product.id, version=3, file_type=FileType.pdf,
                    s3_key="k", original_name=f"{name}.pdf")
    pen = PenDocument(id=uuid.uuid4(), product_id=product.id, version=1, s3_key="p",
                      original_name="pen.docx")
    db.add_all([mockup, pen])
    await db.flush()
    task = CheckTask(id=uuid.uuid4(), mockup_id=mockup.id, pen_id=pen.id, status=status,
                     mode=PipelineMode.hybrid, **task_kw)
    if created_at is not None:
        task.created_at = created_at
    db.add(task)
    await db.flush()
    if issues:
        db.add(CheckResult(id=uuid.uuid4(), task_id=task.id, stage=CheckStage.spelling,
                           issues=issues, created_at=datetime.now(timezone.utc)))
    await db.commit()
    return product, mockup, task


class TestHistory:
    async def test_row_carries_the_full_product_name(self, client, spec_headers, db):
        await _seed(db, "Витамин D3 форте Импловит 2000 МЕ")
        resp = await client.get("/api/v1/checks/history", headers=spec_headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["product_name"] == "Витамин D3 форте Импловит 2000 МЕ"

    async def test_row_also_carries_file_and_version(self, client, spec_headers, db):
        await _seed(db, "Куркумин форте")
        row = (await client.get("/api/v1/checks/history", headers=spec_headers)).json()[0]
        assert row["mockup_name"] == "Куркумин форте.pdf"
        assert row["mockup_version"] == 3
        assert row["category"] == "bad"

    async def test_issue_count_is_reported(self, client, spec_headers, db):
        await _seed(db, "Нутрисорб", issues=[
            {"module": "spelling", "type": "error", "description": "опечатка"},
            {"module": "spelling", "type": "warning", "description": "стиль"},
        ])
        row = (await client.get("/api/v1/checks/history", headers=spec_headers)).json()[0]
        assert row["issues_count"] == 2

    async def test_filter_by_product_name(self, client, spec_headers, db):
        await _seed(db, "Коллоидное серебро")
        await _seed(db, "Магний B6")
        resp = await client.get("/api/v1/checks/history",
                                params={"product_name": "Магний"}, headers=spec_headers)
        names = [r["product_name"] for r in resp.json()]
        assert names == ["Магний B6"]

    async def test_filter_is_case_insensitive(self, client, spec_headers, db):
        # The filter uses ILIKE. On PostgreSQL (production) that is case-insensitive
        # for Cyrillic too; SQLite's LIKE only folds ASCII, so this test asserts the
        # portable half of the behaviour.
        await _seed(db, "Магний B6")
        resp = await client.get("/api/v1/checks/history",
                                params={"product_name": "b6"}, headers=spec_headers)
        assert [r["product_name"] for r in resp.json()] == ["Магний B6"]

    async def test_partial_match(self, client, spec_headers, db):
        await _seed(db, "Витамин Д3 К2 форте")
        resp = await client.get("/api/v1/checks/history",
                                params={"product_name": "Д3 К2"}, headers=spec_headers)
        assert len(resp.json()) == 1

    async def test_filter_by_status(self, client, spec_headers, db):
        await _seed(db, "Готовая", status=TaskStatus.COMPLETED)
        await _seed(db, "Упавшая", status=TaskStatus.FAILED)
        resp = await client.get("/api/v1/checks/history",
                                params={"status": "FAILED"}, headers=spec_headers)
        assert [r["product_name"] for r in resp.json()] == ["Упавшая"]

    async def test_failed_row_exposes_the_error_code_and_hint(self, client, spec_headers, db):
        await _seed(db, "Сломанная", status=TaskStatus.FAILED,
                    error="Selectel: доступ приостановлен",
                    error_code="STORAGE_PAYMENT_REQUIRED",
                    error_details={"code": "STORAGE_PAYMENT_REQUIRED", "title": "t",
                                   "hint": "оплатите счёт", "provider": "selectel"})
        row = (await client.get("/api/v1/checks/history", headers=spec_headers)).json()[0]
        assert row["error_code"] == "STORAGE_PAYMENT_REQUIRED"
        assert row["error_details"]["hint"] == "оплатите счёт"

    async def test_newest_first(self, client, spec_headers, db):
        # Explicit timestamps: SQLite's CURRENT_TIMESTAMP has one-second resolution,
        # so two rows created back to back would tie.
        await _seed(db, "Первая", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        await _seed(db, "Вторая", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
        rows = (await client.get("/api/v1/checks/history", headers=spec_headers)).json()
        assert rows[0]["product_name"] == "Вторая"

    async def test_requires_auth(self, client):
        assert (await client.get("/api/v1/checks/history")).status_code == 401


class TestSingleCheck:
    async def test_detail_endpoint_includes_product_name(self, client, spec_headers, db):
        _, _, task = await _seed(db, "ОфтальмоПРО")
        resp = await client.get(f"/api/v1/checks/{task.id}", headers=spec_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["product_name"] == "ОфтальмоПРО"

    async def test_quality_report_is_returned_when_present(self, client, spec_headers, db):
        _, _, task = await _seed(db, "ZMA", quality={"ok": True, "level": "excellent", "score": 96})
        body = (await client.get(f"/api/v1/checks/{task.id}", headers=spec_headers)).json()
        assert body["quality"]["level"] == "excellent"

    async def test_missing_check_is_404(self, client, spec_headers):
        resp = await client.get(f"/api/v1/checks/{uuid.uuid4()}", headers=spec_headers)
        assert resp.status_code == 404


class TestOrphanedRows:
    async def test_check_without_a_product_still_appears(self, client, spec_headers, db):
        # The journal must not silently drop a check because its product row is gone.
        import uuid as _uuid
        from app.models.checks import CheckTask as _T
        db.add(_T(id=_uuid.uuid4(), mockup_id=_uuid.uuid4(), pen_id=_uuid.uuid4(),
                  status=TaskStatus.FAILED, mode=PipelineMode.hybrid, error="упало"))
        await db.commit()

        rows = (await client.get("/api/v1/checks/history", headers=spec_headers)).json()
        assert len(rows) == 1
        assert rows[0]["product_name"].startswith("без названия")
        assert rows[0]["error"] == "упало"
