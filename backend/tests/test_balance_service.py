"""Balances: real readings where an API exists, an honest "no API" otherwise."""
import httpx
import pytest

from app.services import balance_service as b
from app.services import config_service


@pytest.fixture(autouse=True)
def fixed_rates(monkeypatch):
    """Pin the CBR rates so conversions are deterministic and no network is touched."""
    async def fake_rates():
        return {"RUB": 1.0, "USD": 90.0, "EUR": 100.0, "ILS": 24.0}
    monkeypatch.setattr(b, "get_rates", fake_rates)


class _FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.example.com")
            raise httpx.HTTPStatusError("err", request=request,
                                        response=httpx.Response(self.status_code, request=request))


def _patch_get(monkeypatch, response):
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(b.httpx, "AsyncClient", FakeClient)


class TestConversion:
    def test_to_rub(self):
        rates = {"RUB": 1.0, "ILS": 24.0}
        assert b.to_rub(58, "ILS", rates) == 1392.0
        assert b.to_rub(100, "RUB", rates) == 100.0

    def test_unknown_currency_yields_no_rouble_figure(self):
        assert b.to_rub(10, "XYZ", {"RUB": 1.0}) is None

    def test_none_amount(self):
        assert b.to_rub(None, "USD", {"USD": 90.0}) is None


class TestSelectel:
    async def test_not_configured(self):
        entry = await b.fetch_selectel("")
        assert entry["status"] == "not_configured"
        assert "токен" in entry["hint"].lower()

    async def test_balance_is_converted_from_kopecks(self, monkeypatch):
        _patch_get(monkeypatch, _FakeResponse(200, {"info": {"balance": {"primary": 123456}}}))
        entry = await b.fetch_selectel("token")
        assert entry["status"] == "ok"
        assert entry["amount"] == 1234.56
        assert entry["currency"] == "RUB"
        assert entry["amount_rub"] == 1234.56

    async def test_bad_token_says_so(self, monkeypatch):
        _patch_get(monkeypatch, _FakeResponse(401, {}))
        entry = await b.fetch_selectel("bad")
        assert entry["status"] == "error"
        assert "токен" in entry["hint"].lower()

    async def test_unrecognised_payload_is_reported_not_invented(self, monkeypatch):
        # If Selectel changes its schema we must say we could not read it rather
        # than display a confident wrong number.
        _patch_get(monkeypatch, _FakeResponse(200, {"something": "else"}))
        entry = await b.fetch_selectel("token")
        assert entry["status"] == "error"
        assert entry["amount"] is None

    async def test_network_failure_is_contained(self, monkeypatch):
        _patch_get(monkeypatch, httpx.ConnectError("no route"))
        entry = await b.fetch_selectel("token")
        assert entry["status"] == "error"


class TestAbbyy:
    async def test_pages_remaining(self, monkeypatch):
        _patch_get(monkeypatch, _FakeResponse(200, {"pages": 1500, "fields": 0, "credits": 12}))
        entry = await b.fetch_abbyy("app", "pass", "https://cloud.ocrsdk.com")
        assert entry["status"] == "ok"
        assert entry["units"]["pages"] == 1500
        assert entry["amount"] is None  # a page quota is not money

    async def test_not_configured(self):
        entry = await b.fetch_abbyy("", "", "")
        assert entry["status"] == "not_configured"


class TestProvidersWithoutAnApi:
    async def test_gemini_is_reported_as_unsupported_not_zero(self, db):
        entries = await b.get_balances(db, ["gemini"])
        entry = entries[0]
        assert entry["status"] == "unsupported"
        assert entry["amount"] is None
        assert "не предоставляет" in entry["message"]
        assert entry["console_url"]

    @pytest.mark.parametrize("provider", ["openai", "anthropic", "grok", "yandex_vision"])
    async def test_each_says_why(self, db, provider):
        entry = (await b.get_balances(db, [provider]))[0]
        assert entry["status"] == "unsupported"
        assert entry["message"]


class TestManualBalance:
    async def test_manual_value_is_shown_with_its_rouble_equivalent(self, db):
        await b.set_manual(db, "gemini", 58, "ILS", note="из консоли Google")
        entry = (await b.get_balances(db, ["gemini"]))[0]
        assert entry["status"] == "manual"
        assert entry["source"] == "manual"
        assert entry["amount"] == 58
        assert entry["currency"] == "ILS"
        assert entry["amount_rub"] == 1392.0
        assert entry["as_of"]

    async def test_manual_value_never_masquerades_as_live(self, db, monkeypatch):
        # Selectel answers for real -> the manual note is kept alongside but the
        # displayed status stays "ok" from the API.
        await b.set_manual(db, "selectel", 999, "RUB")
        await config_service.set_config(db, "selectel_api_token", "tok", is_encrypted=True)
        _patch_get(monkeypatch, _FakeResponse(200, {"balance": 500000}))
        entry = (await b.get_balances(db, ["selectel"]))[0]
        assert entry["status"] == "ok"
        assert entry["source"] == "api"
        assert entry["amount"] == 5000.0
        assert entry["manual"]["amount"] == 999

    async def test_manual_value_can_be_cleared(self, db):
        await b.set_manual(db, "gemini", 58, "ILS")
        await b.set_manual(db, "gemini", None, "")
        entry = (await b.get_balances(db, ["gemini"]))[0]
        assert entry["status"] == "unsupported"

    async def test_stored_encrypted_config_roundtrip(self, db):
        await b.set_manual(db, "openai", 12.5, "USD")
        manual = await b.get_manual(db, "openai")
        assert manual["amount"] == 12.5 and manual["currency"] == "USD"


class TestActiveProvider:
    async def test_follows_the_admin_pipeline_setting(self, db):
        await config_service.set_config(db, "pipeline_mode", "hybrid")
        await config_service.set_config(db, "llm_provider", "gemini")
        entry = await b.get_active_balance(db)
        assert entry["provider"] == "gemini"

    async def test_unified_mode_uses_the_unified_model(self, db):
        await config_service.set_config(db, "pipeline_mode", "unified")
        await config_service.set_config(db, "unified_llm", "anthropic")
        entry = await b.get_active_balance(db)
        assert entry["provider"] == "anthropic"

    async def test_nothing_configured(self, db):
        assert await b.get_active_balance(db) is None


class TestBalanceApi:
    async def test_admin_sees_every_provider(self, client, admin_headers):
        body = (await client.get("/api/v1/admin/balances", headers=admin_headers)).json()
        assert {e["provider"] for e in body["balances"]} == set(b.ALL_PROVIDERS)
        assert body["rates_source"]

    async def test_admin_can_record_a_manual_figure(self, client, admin_headers):
        resp = await client.put("/api/v1/admin/balances/gemini", headers=admin_headers,
                                json={"amount": 58, "currency": "ILS", "note": "AI Studio"})
        assert resp.status_code == 200, resp.text
        body = (await client.get("/api/v1/admin/balances", headers=admin_headers)).json()
        gemini = next(e for e in body["balances"] if e["provider"] == "gemini")
        assert gemini["amount"] == 58 and gemini["source"] == "manual"

    async def test_rejects_an_unknown_provider(self, client, admin_headers):
        resp = await client.put("/api/v1/admin/balances/whatever", headers=admin_headers,
                                json={"amount": 1})
        assert resp.status_code == 400

    async def test_rejects_a_non_numeric_amount(self, client, admin_headers):
        resp = await client.put("/api/v1/admin/balances/gemini", headers=admin_headers,
                                json={"amount": "много"})
        assert resp.status_code == 400

    async def test_specialist_sees_the_active_provider_balance(self, client, spec_headers, db):
        await config_service.set_config(db, "llm_provider", "gemini")
        await b.set_manual(db, "gemini", 58, "ILS")
        body = (await client.get("/api/v1/checks/provider-balance", headers=spec_headers)).json()
        assert body["balance"]["provider"] == "gemini"
        assert body["balance"]["amount_rub"] == 1392.0

    async def test_specialist_cannot_reach_the_admin_balance_screen(self, client, spec_headers):
        assert (await client.get("/api/v1/admin/balances", headers=spec_headers)).status_code == 403
