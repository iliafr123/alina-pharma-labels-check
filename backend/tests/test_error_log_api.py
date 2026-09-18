"""The admin error screen: failures must be recorded and readable there."""
import uuid

from app.core.errors import AppError, storage_error
from app.services import error_service


class TestErrorLogging:
    async def test_error_is_persisted_with_cause_and_hint(self, client, admin_headers, db):
        await error_service.log_error(
            db, AppError("STORAGE_PAYMENT_REQUIRED", "Selectel: доступ приостановлен.",
                         "Оплатите счёт в панели Selectel.", "402 PaymentRequired",
                         provider="selectel", subsystem="storage"),
            source="worker", task_id="abc")

        rows = (await client.get("/api/v1/admin/errors", headers=admin_headers)).json()
        assert len(rows) == 1
        assert rows[0]["code"] == "STORAGE_PAYMENT_REQUIRED"
        assert rows[0]["hint"] == "Оплатите счёт в панели Selectel."
        assert rows[0]["provider"] == "selectel"
        assert rows[0]["source"] == "worker"
        assert rows[0]["task_id"] == "abc"

    async def test_log_exception_classifies_before_storing(self, client, admin_headers, db):
        import httpx
        request = httpx.Request("POST", "https://example.com")
        exc = httpx.HTTPStatusError(
            "x", request=request, response=httpx.Response(429, text="quota exceeded", request=request))

        err = await error_service.log_exception(db, exc, provider="gemini", subsystem="llm")
        assert err.code == "LLM_QUOTA"

        rows = (await client.get("/api/v1/admin/errors", headers=admin_headers)).json()
        assert rows[0]["code"] == "LLM_QUOTA"

    async def test_traceback_is_captured_when_an_exception_is_given(self, client, admin_headers, db):
        try:
            raise ValueError("boom")
        except ValueError as e:
            await error_service.log_exception(db, e)
        rows = (await client.get("/api/v1/admin/errors", headers=admin_headers)).json()
        assert "ValueError" in (rows[0]["traceback"] or "")

    async def test_secrets_are_not_stored(self, client, admin_headers, db):
        await error_service.log_error(
            db, AppError("LLM_AUTH", "ключ отклонён",
                         detail='{"api_key": "AIzaSyDSuperSecretKey12345"}'))
        rows = (await client.get("/api/v1/admin/errors", headers=admin_headers)).json()
        assert "AIzaSyDSuperSecretKey12345" not in (rows[0]["detail"] or "")

    async def test_logging_failure_never_propagates(self, db):
        # A broken logging path must not replace the real error the user is chasing.
        bad = AppError("X", "t")
        bad.code = None  # violates the NOT NULL column
        await error_service.log_error(db, bad)  # must not raise


class TestErrorApi:
    async def _seed(self, db, n=3):
        for i in range(n):
            await error_service.log_error(
                db, AppError(f"CODE_{i}", f"Ошибка {i}", "подсказка",
                             provider="gemini" if i else "selectel",
                             subsystem="llm" if i else "storage"),
                source="worker" if i else "api")

    async def test_filter_by_code(self, client, admin_headers, db):
        await self._seed(db)
        rows = (await client.get("/api/v1/admin/errors", params={"code": "CODE_1"},
                                 headers=admin_headers)).json()
        assert [r["code"] for r in rows] == ["CODE_1"]

    async def test_filter_by_subsystem_and_provider(self, client, admin_headers, db):
        await self._seed(db)
        rows = (await client.get("/api/v1/admin/errors", params={"subsystem": "storage"},
                                 headers=admin_headers)).json()
        assert all(r["subsystem"] == "storage" for r in rows) and rows

        rows = (await client.get("/api/v1/admin/errors", params={"provider": "gemini"},
                                 headers=admin_headers)).json()
        assert all(r["provider"] == "gemini" for r in rows) and rows

    async def test_free_text_search(self, client, admin_headers, db):
        await self._seed(db)
        rows = (await client.get("/api/v1/admin/errors", params={"search": "Ошибка 2"},
                                 headers=admin_headers)).json()
        assert len(rows) == 1

    async def test_summary_groups_by_code(self, client, admin_headers, db):
        await error_service.log_error(db, AppError("LLM_QUOTA", "q"))
        await error_service.log_error(db, AppError("LLM_QUOTA", "q"))
        await error_service.log_error(db, AppError("LLM_AUTH", "a"))

        body = (await client.get("/api/v1/admin/errors/summary", headers=admin_headers)).json()
        assert body["total"] == 3
        top = body["by_code"][0]
        assert top["code"] == "LLM_QUOTA" and top["count"] == 2

    async def test_clear(self, client, admin_headers, db):
        await self._seed(db)
        assert (await client.delete("/api/v1/admin/errors", headers=admin_headers)).json()["deleted"] == 3
        assert (await client.get("/api/v1/admin/errors", headers=admin_headers)).json() == []

    async def test_specialist_cannot_read_the_error_log(self, client, spec_headers):
        assert (await client.get("/api/v1/admin/errors", headers=spec_headers)).status_code == 403

    async def test_dashboard_stats_surface_the_dominant_cause(self, client, admin_headers, db):
        await error_service.log_error(db, AppError("STORAGE_PAYMENT_REQUIRED", "Selectel не оплачен"))
        body = (await client.get("/api/v1/admin/stats", headers=admin_headers)).json()
        assert body["errors_24h"] == 1
        assert body["top_error"]["code"] == "STORAGE_PAYMENT_REQUIRED"


class TestHttpErrorShape:
    async def test_app_error_reaches_the_client_with_code_and_hint(self, client, spec_headers):
        # An empty upload is refused with a typed error, not a bare 400.
        resp = await client.post("/api/v1/uploads/quality-check", headers=spec_headers,
                                 files={"file": ("empty.pdf", b"", "application/pdf")})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "FILE_EMPTY"
        assert body["error"]["hint"]
        assert body["detail"]          # legacy field still readable

    async def test_that_error_is_also_recorded_for_the_admin(self, client, spec_headers, admin_headers):
        await client.post("/api/v1/uploads/quality-check", headers=spec_headers,
                          files={"file": ("empty.pdf", b"", "application/pdf")})
        rows = (await client.get("/api/v1/admin/errors", headers=admin_headers)).json()
        assert any(r["code"] == "FILE_EMPTY" and r["source"] == "api" for r in rows)
