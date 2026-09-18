"""Regression tests for the error classifier.

The bug these guard against: an unpaid Selectel account produced a failed check
whose stored error said nothing at all. Every mapping below must keep producing a
code, a Russian title, and an actionable hint.
"""
import httpx
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from app.core.errors import AppError, classify, provider_error, redact, storage_error


def _client_error(code: str, status: int, message: str = "denied") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message},
         "ResponseMetadata": {"HTTPStatusCode": status}},
        "GetObject",
    )


def _http_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.com/v1/x")
    response = httpx.Response(status, text=body, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


SELECTEL = "https://s3.selectel.ru"


class TestStorageErrors:
    def test_payment_required_is_named_as_billing(self):
        err = storage_error(_client_error("PaymentRequired", 402), endpoint=SELECTEL, bucket="b")
        assert err.code == "STORAGE_PAYMENT_REQUIRED"
        assert "оплат" in err.title.lower() or "оплат" in err.hint.lower()
        assert "selectel" in err.hint.lower()
        assert err.http_status == 402

    def test_http_402_without_aws_code_still_maps_to_billing(self):
        err = storage_error(_client_error("", 402), endpoint=SELECTEL, bucket="b")
        assert err.code == "STORAGE_PAYMENT_REQUIRED"

    def test_403_mentions_unpaid_account_as_a_candidate_cause(self):
        # Selectel blocks an unpaid account with a plain 403, so the hint has to
        # raise billing even though the status alone looks like a permissions issue.
        err = storage_error(_client_error("AccessDenied", 403), endpoint=SELECTEL, bucket="labels")
        assert err.code == "STORAGE_FORBIDDEN"
        assert "не оплачен" in err.hint
        assert "labels" in err.hint

    def test_bad_credentials(self):
        err = storage_error(_client_error("InvalidAccessKeyId", 403), endpoint=SELECTEL)
        assert err.code == "STORAGE_BAD_CREDENTIALS"

    def test_missing_bucket(self):
        err = storage_error(_client_error("NoSuchBucket", 404), endpoint=SELECTEL, bucket="nope")
        assert err.code == "STORAGE_NO_BUCKET"
        assert "nope" in err.hint or "nope" in err.title

    def test_missing_object(self):
        err = storage_error(_client_error("NoSuchKey", 404), endpoint=SELECTEL)
        assert err.code == "STORAGE_FILE_MISSING"

    def test_server_error(self):
        err = storage_error(_client_error("InternalError", 500), endpoint=SELECTEL)
        assert err.code == "STORAGE_UNAVAILABLE"

    def test_no_credentials(self):
        err = storage_error(NoCredentialsError(), endpoint=SELECTEL)
        assert err.code == "STORAGE_NOT_CONFIGURED"

    def test_unreachable_endpoint(self):
        err = storage_error(EndpointConnectionError(endpoint_url=SELECTEL), endpoint=SELECTEL)
        assert err.code == "STORAGE_UNREACHABLE"

    def test_non_selectel_endpoint_gets_generic_wording(self):
        err = storage_error(_client_error("AccessDenied", 403), endpoint="https://s3.amazonaws.com")
        assert "selectel" not in err.hint.lower()


class TestProviderErrors:
    @pytest.mark.parametrize("status,expected", [
        (401, "LLM_AUTH"),
        (403, "LLM_AUTH"),
        (402, "LLM_PAYMENT_REQUIRED"),
        (404, "LLM_MODEL_NOT_FOUND"),
        (500, "LLM_UNAVAILABLE"),
        (503, "LLM_UNAVAILABLE"),
    ])
    def test_status_mapping(self, status, expected):
        err = provider_error(_http_error(status), provider="gemini")
        assert err.code == expected
        assert err.title.startswith("Google Gemini")
        assert err.hint

    def test_429_quota_vs_rate_limit_are_different_advice(self):
        quota = provider_error(_http_error(429, "Quota exceeded for this project"), provider="gemini")
        rate = provider_error(_http_error(429, "too many requests"), provider="gemini")
        assert quota.code == "LLM_QUOTA"
        assert rate.code == "LLM_RATE_LIMIT"
        assert quota.hint != rate.hint

    def test_400_invalid_api_key_is_reported_as_auth(self):
        err = provider_error(_http_error(400, '{"error":"API key not valid"}'), provider="gemini")
        assert err.code == "LLM_AUTH"

    def test_timeout(self):
        err = provider_error(httpx.ReadTimeout("slow"), provider="openai")
        assert err.code == "LLM_TIMEOUT"

    def test_network(self):
        err = provider_error(httpx.ConnectError("no route"), provider="anthropic")
        assert err.code == "LLM_NETWORK"

    def test_stage_is_carried_through(self):
        err = provider_error(_http_error(500), provider="grok", subsystem="ocr", stage="ocr")
        assert err.stage == "ocr"
        assert err.subsystem == "ocr"


class TestClassify:
    def test_app_error_passes_through_untouched(self):
        original = AppError("X", "title", "hint")
        assert classify(original) is original

    def test_app_error_gains_stage_if_missing(self):
        original = AppError("X", "title")
        assert classify(original, stage="pen").stage == "pen"

    def test_boto_error_routes_to_storage(self):
        err = classify(_client_error("AccessDenied", 403), endpoint=SELECTEL, bucket="b")
        assert err.subsystem == "storage"

    def test_httpx_error_routes_to_provider(self):
        err = classify(_http_error(401), provider="gemini", subsystem="llm")
        assert err.code == "LLM_AUTH"

    def test_unknown_exception_is_still_actionable(self):
        err = classify(ValueError("something odd"))
        assert err.code == "INTERNAL_ERROR"
        assert err.title and err.hint
        assert "ValueError" in err.detail

    def test_memory_error(self):
        assert classify(MemoryError()).code == "PIPELINE_OOM"

    def test_celery_soft_timeout(self):
        from celery.exceptions import SoftTimeLimitExceeded
        assert classify(SoftTimeLimitExceeded()).code == "PIPELINE_TIMEOUT"


class TestRedaction:
    @pytest.mark.parametrize("text,secret", [
        ('{"api_key": "AIzaSyDverySecretValue123"}', "AIzaSyDverySecretValue123"),
        ("Authorization: Bearer abcdef1234567890xyz", "abcdef1234567890xyz"),
        ("key sk-proj-abcdef1234567890", "sk-proj-abcdef1234567890"),
        ('secret="hunter2hunter2"', "hunter2hunter2"),
    ])
    def test_secrets_never_reach_the_log(self, text, secret):
        assert secret not in redact(text)

    def test_app_error_redacts_on_construction(self):
        err = AppError("C", "t", detail='{"api_key": "AIzaSyDverySecretValue123"}')
        assert "AIzaSyDverySecretValue123" not in err.detail

    def test_ordinary_text_survives(self):
        assert redact("бакет labels не найден") == "бакет labels не найден"


class TestErrorShape:
    def test_message_joins_title_and_hint(self):
        err = AppError("C", "Что-то сломалось.", "Сделайте вот это.")
        assert "Что-то сломалось." in err.message
        assert "Сделайте вот это." in err.message

    def test_to_dict_has_everything_the_ui_needs(self):
        err = AppError("C", "t", "h", "d", provider="gemini", subsystem="llm", stage="ocr")
        d = err.to_dict()
        assert set(d) >= {"code", "title", "hint", "detail", "provider", "subsystem", "stage"}

    def test_detail_is_truncated(self):
        assert len(AppError("C", "t", detail="x" * 9000).detail) <= 2000
