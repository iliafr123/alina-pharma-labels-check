"""Broad smoke coverage: auth, roles, the quality endpoint, and the check screen's
readiness signal. These are the paths a deploy must not break."""
import io

from PIL import Image, ImageDraw


def _label_jpg(width=2400, height=1200, dpi=(600, 600)) -> bytes:
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(20, height - 20, max(4, height // 60)):
        d.line([(10, y), (width - 10, y)], fill=(10, 10, 10), width=1)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, dpi=dpi)
    return buf.getvalue()


class TestHealth:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuth:
    async def test_login_and_me(self, client):
        from tests.conftest import ADMIN_EMAIL, PASSWORD
        resp = await client.post("/api/v1/auth/login",
                                 json={"email": ADMIN_EMAIL, "password": PASSWORD})
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    async def test_wrong_password_is_401(self, client):
        from tests.conftest import ADMIN_EMAIL
        resp = await client.post("/api/v1/auth/login",
                                 json={"email": ADMIN_EMAIL, "password": "nope"})
        assert resp.status_code == 401

    async def test_refresh_issues_a_new_token(self, client):
        from tests.conftest import ADMIN_EMAIL, PASSWORD
        tokens = (await client.post("/api/v1/auth/login",
                                    json={"email": ADMIN_EMAIL, "password": PASSWORD})).json()
        resp = await client.post("/api/v1/auth/refresh",
                                 json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    async def test_admin_routes_reject_a_specialist(self, client, spec_headers):
        assert (await client.get("/api/v1/admin/config", headers=spec_headers)).status_code == 403

    async def test_admin_routes_reject_anonymous(self, client):
        assert (await client.get("/api/v1/admin/config")).status_code == 401


class TestQualityEndpoint:
    async def test_good_label_is_accepted(self, client, spec_headers):
        resp = await client.post("/api/v1/uploads/quality-check", headers=spec_headers,
                                 files={"file": ("label.jpg", _label_jpg(), "image/jpeg")})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["level"] in ("excellent", "acceptable")
        assert body["summary"]
        assert body["metrics"]["effective_dpi"]

    async def test_low_resolution_label_is_refused_with_a_reason(self, client, spec_headers):
        resp = await client.post("/api/v1/uploads/quality-check", headers=spec_headers,
                                 files={"file": ("small.jpg", _label_jpg(500, 250, (150, 150)),
                                                 "image/jpeg")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["problems"]
        assert body["advice"]
        assert "разрешение" in body["problems"][0]["message"].lower()

    async def test_corrupt_file_returns_a_typed_error(self, client, spec_headers):
        resp = await client.post("/api/v1/uploads/quality-check", headers=spec_headers,
                                 files={"file": ("x.pdf", b"%PDF-1.4 broken", "application/pdf")})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "FILE_UNREADABLE"

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/uploads/quality-check",
                                 files={"file": ("label.jpg", _label_jpg(), "image/jpeg")})
        assert resp.status_code == 401

    async def test_nothing_is_stored(self, client, spec_headers, db):
        from sqlalchemy import select, func
        from app.models.files import Mockup
        await client.post("/api/v1/uploads/quality-check", headers=spec_headers,
                          files={"file": ("label.jpg", _label_jpg(), "image/jpeg")})
        assert (await db.execute(select(func.count(Mockup.id)))).scalar_one() == 0


class TestPipelineOptions:
    async def test_reports_that_nothing_is_configured(self, client, spec_headers):
        body = (await client.get("/api/v1/checks/pipeline-options", headers=spec_headers)).json()
        assert body["configured"] is False
        assert body["llm_providers"] == []

    async def test_reports_the_active_pair_once_configured(self, client, spec_headers, db):
        from app.services import config_service
        await config_service.set_config(db, "api_key_gemini", "k", is_encrypted=True)
        await config_service.set_config(db, "llm_provider", "gemini")
        await config_service.set_config(db, "ocr_provider", "gemini")
        await config_service.set_config(db, "pipeline_mode", "hybrid")

        body = (await client.get("/api/v1/checks/pipeline-options", headers=spec_headers)).json()
        assert body["active_llm"] == "gemini"
        assert body["active_ocr"] == "gemini"
        assert body["configured"] is True

    async def test_unified_mode_reports_the_single_model(self, client, spec_headers, db):
        from app.services import config_service
        await config_service.set_config(db, "api_key_anthropic", "k", is_encrypted=True)
        await config_service.set_config(db, "pipeline_mode", "unified")
        await config_service.set_config(db, "unified_llm", "anthropic")

        body = (await client.get("/api/v1/checks/pipeline-options", headers=spec_headers)).json()
        assert body["active_llm"] == body["active_ocr"] == "anthropic"


class TestUploadGuards:
    async def test_pen_must_be_a_docx(self, client, spec_headers, db):
        import uuid as _uuid
        from app.models.products import Product, ProductCategory
        product = Product(id=_uuid.uuid4(), name="Тест", category=ProductCategory.bad)
        db.add(product)
        await db.commit()

        resp = await client.post("/api/v1/uploads/pen", headers=spec_headers,
                                 files={"file": ("pen.txt", b"hello", "text/plain")},
                                 data={"product_id": str(product.id)})
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "FILE_UNSUPPORTED"

    async def test_storage_misconfiguration_is_named(self, client, spec_headers, db):
        # No S3 keys in the test environment: the upload must say exactly that
        # instead of failing with an opaque boto error.
        import uuid as _uuid
        from app.models.products import Product, ProductCategory
        product = Product(id=_uuid.uuid4(), name="Тест", category=ProductCategory.bad)
        db.add(product)
        await db.commit()

        resp = await client.post("/api/v1/uploads/mockup", headers=spec_headers,
                                 files={"file": ("label.jpg", _label_jpg(), "image/jpeg")},
                                 data={"product_id": str(product.id)})
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["code"] == "STORAGE_NOT_CONFIGURED"
        assert "Администрирование" in body["error"]["hint"]
