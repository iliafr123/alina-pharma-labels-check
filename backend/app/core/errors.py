"""Typed, user-facing application errors + a classifier that turns raw provider
exceptions into them.

Why this exists: a failure deep in the pipeline (unpaid Selectel account, revoked
LLM key, exhausted quota) used to surface as a bare `str(exc)` - often empty or
cryptic - so the operator could not tell *what* was wrong. Every error raised or
caught by the app is mapped to an AppError carrying:

  code     stable machine code (also stored on the task and in the error log)
  title    short Russian sentence shown to the user
  hint     what the operator should actually do about it
  detail   the redacted technical message, for the admin error log
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# --- key redaction -----------------------------------------------------------
# Provider error bodies and boto URLs can echo credentials. Never persist them.
_SECRET_PATTERNS = [
    # Order matters: the specific forms run first. "Authorization: Bearer <token>"
    # otherwise matches the generic key/value rule, which masks the word "Bearer"
    # and leaves the token itself in the message.
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(r"(?i)\b(sk-|xai-|AIza|SG\.)[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?key|secret|token|password|authorization)"
               r"(\"?\s*[:=]\s*\"?)([^\s\"',&}]{6,})"),
]


def redact(text: str) -> str:
    """Mask anything that looks like a credential inside a message."""
    s = text or ""
    for pat in _SECRET_PATTERNS:
        if pat.groups >= 3:
            s = pat.sub(lambda m: f"{m.group(1)}{m.group(2)}***", s)
        else:
            s = pat.sub("***", s)
    return s


@dataclass
class AppError(Exception):
    """A failure the user is allowed to see, in plain Russian."""

    code: str
    title: str
    hint: str = ""
    detail: str = ""
    provider: str = ""          # gemini / selectel / abbyy / ...
    subsystem: str = ""         # storage / llm / ocr / file / pipeline
    stage: str = ""             # ocr / spelling / pen / regulatory / report
    http_status: int = 400
    context: dict = field(default_factory=dict)

    def __post_init__(self):
        self.detail = redact(str(self.detail or ""))[:2000]
        super().__init__(self.title)

    @property
    def message(self) -> str:
        """One-line message for places that only have room for a string."""
        parts = [self.title]
        if self.hint:
            parts.append(self.hint)
        return " - ".join(parts)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "hint": self.hint,
            "detail": self.detail,
            "provider": self.provider,
            "subsystem": self.subsystem,
            "stage": self.stage,
            "context": self.context,
        }


# --- provider display names --------------------------------------------------
PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "anthropic": "Anthropic Claude",
    "anthropic_vision": "Anthropic Claude (vision)",
    "grok": "xAI Grok",
    "yandex_vision": "Yandex Vision",
    "abbyy": "ABBYY Cloud OCR",
    "selectel": "Selectel Object Storage",
    "storage": "Объектное хранилище",
}


def label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider or "провайдер")


# --- console links, so the hint is actionable --------------------------------
CONSOLE_URLS = {
    "gemini": "https://aistudio.google.com/app/apikey",
    "openai": "https://platform.openai.com/settings/organization/billing",
    "anthropic": "https://console.anthropic.com/settings/billing",
    "grok": "https://console.x.ai/",
    "yandex_vision": "https://console.cloud.yandex.ru/billing",
    "abbyy": "https://cloud.ocrsdk.com/",
    "selectel": "https://my.selectel.ru/billing",
}


def _is_selectel(endpoint: str) -> bool:
    return "selectel" in (endpoint or "").lower()


# --- storage -----------------------------------------------------------------
def storage_error(exc: Exception, *, endpoint: str = "", bucket: str = "", key: str = "") -> AppError:
    """Map a boto3/botocore failure to an AppError with a billing-aware hint."""
    provider = "selectel" if _is_selectel(endpoint) else "storage"
    name = label(provider)
    ctx = {"endpoint": endpoint, "bucket": bucket, "s3_key": key}
    detail = str(exc)

    try:
        from botocore.exceptions import (
            ClientError, EndpointConnectionError, ConnectTimeoutError,
            NoCredentialsError, PartialCredentialsError, ParamValidationError,
            SSLError, ReadTimeoutError,
        )
    except Exception:  # botocore missing - should not happen, stay defensive
        return AppError("STORAGE_ERROR", f"{name}: ошибка обращения к хранилищу.",
                        "Проверьте настройки хранилища в админке.", detail,
                        provider=provider, subsystem="storage", http_status=502, context=ctx)

    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return AppError(
            "STORAGE_NOT_CONFIGURED", f"{name}: не заданы ключи доступа.",
            "Администрирование → Хранилище (Selectel): заполните Access Key и Secret Key и сохраните.",
            detail, provider=provider, subsystem="storage", http_status=503, context=ctx)

    if isinstance(exc, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, SSLError)):
        return AppError(
            "STORAGE_UNREACHABLE", f"{name}: сервер хранилища недоступен.",
            f"Проверьте Endpoint URL ({endpoint or 'не задан'}) и сетевую доступность. "
            "Если адрес верный — возможно, идут работы на стороне провайдера.",
            detail, provider=provider, subsystem="storage", http_status=503, context=ctx)

    if isinstance(exc, ParamValidationError):
        return AppError(
            "STORAGE_BAD_PARAMS", f"{name}: некорректные параметры запроса к хранилищу.",
            "Проверьте имя бакета и регион в админке.", detail,
            provider=provider, subsystem="storage", http_status=400, context=ctx)

    if isinstance(exc, ClientError):
        err = (exc.response or {}).get("Error", {}) or {}
        aws_code = str(err.get("Code", ""))
        aws_msg = str(err.get("Message", ""))
        status = int(((exc.response or {}).get("ResponseMetadata", {}) or {}).get("HTTPStatusCode", 0) or 0)
        ctx.update({"aws_code": aws_code, "http_status": status})
        detail = f"{aws_code} ({status}): {aws_msg}" if aws_code else detail

        billing_hint = (
            "Откройте биллинг Selectel — при неоплаченном счёте хранилище блокируется "
            f"и все загрузки падают именно так: {CONSOLE_URLS['selectel']}"
            if provider == "selectel" else
            "Проверьте состояние аккаунта и оплату у провайдера хранилища."
        )

        # Payment / suspension. Selectel answers 402, and also 403 on a blocked account.
        if status == 402 or aws_code in ("PaymentRequired", "AccountProblem", "SubscriptionRequired"):
            return AppError(
                "STORAGE_PAYMENT_REQUIRED", f"{name}: доступ к хранилищу приостановлен (требуется оплата).",
                billing_hint, detail, provider=provider, subsystem="storage",
                http_status=402, context=ctx)

        if aws_code in ("InvalidAccessKeyId", "SignatureDoesNotMatch", "InvalidAccessKey",
                        "AuthorizationHeaderMalformed"):
            return AppError(
                "STORAGE_BAD_CREDENTIALS", f"{name}: неверный Access Key или Secret Key.",
                "Администрирование → Хранилище: перевыпустите ключ S3 в панели провайдера и вставьте заново.",
                detail, provider=provider, subsystem="storage", http_status=401, context=ctx)

        if status == 403 or aws_code in ("AccessDenied", "AllAccessDisabled", "Forbidden"):
            return AppError(
                "STORAGE_FORBIDDEN", f"{name}: доступ запрещён (403).",
                "Три обычные причины, проверьте по порядку: 1) не оплачен счёт — аккаунт заблокирован; "
                f"2) у ключа нет прав на бакет «{bucket}»; 3) ключ отозван. {billing_hint}",
                detail, provider=provider, subsystem="storage", http_status=403, context=ctx)

        if aws_code == "NoSuchBucket":
            return AppError(
                "STORAGE_NO_BUCKET", f"{name}: бакет «{bucket}» не найден.",
                "Проверьте имя бакета в админке — оно должно совпадать с панелью провайдера.",
                detail, provider=provider, subsystem="storage", http_status=404, context=ctx)

        if aws_code in ("NoSuchKey", "404") or status == 404:
            return AppError(
                "STORAGE_FILE_MISSING", f"{name}: файл не найден в хранилище.",
                "Файл был удалён из бакета или загрузка не завершилась. Загрузите макет заново.",
                detail, provider=provider, subsystem="storage", http_status=404, context=ctx)

        if aws_code in ("QuotaExceeded", "EntityTooLarge", "ServiceQuotaExceededException"):
            return AppError(
                "STORAGE_QUOTA", f"{name}: превышена квота хранилища.",
                "Освободите место в бакете или расширьте тариф у провайдера.",
                detail, provider=provider, subsystem="storage", http_status=507, context=ctx)

        if status >= 500:
            return AppError(
                "STORAGE_UNAVAILABLE", f"{name}: сервис хранилища вернул ошибку {status}.",
                "Временный сбой на стороне провайдера — повторите проверку через несколько минут.",
                detail, provider=provider, subsystem="storage", http_status=503, context=ctx)

    return AppError(
        "STORAGE_ERROR", f"{name}: ошибка обращения к хранилищу.",
        "Проверьте настройки в разделе Администрирование → Хранилище и повторите.",
        detail, provider=provider, subsystem="storage", http_status=502, context=ctx)


# --- LLM / OCR providers -----------------------------------------------------
def provider_error(exc: Exception, *, provider: str, subsystem: str = "llm", stage: str = "") -> AppError:
    """Map an httpx/SDK failure from an LLM or OCR provider to an AppError."""
    name = label(provider)
    console = CONSOLE_URLS.get(provider, "")
    where = f" ({console})" if console else ""
    detail = str(exc)
    ctx = {"provider": provider}

    def build(code, title, hint, http_status=502, det=None):
        return AppError(code, title, hint, det if det is not None else detail, provider=provider,
                        subsystem=subsystem, stage=stage, http_status=http_status, context=ctx)

    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = ""
        try:
            body = exc.response.text[:600]
        except Exception:
            pass
        detail = f"HTTP {status}: {body}"
        ctx["http_status"] = status
        low = body.lower()

        if status in (401, 403):
            return build("LLM_AUTH", f"{name}: ключ отклонён (HTTP {status}).",
                         "Ключ неверный, отозван или у него нет доступа к модели. "
                         f"Перевыпустите ключ и вставьте его в Администрирование → Провайдеры AI/OCR{where}.",
                         401)
        if status == 402:
            return build("LLM_PAYMENT_REQUIRED", f"{name}: на счёте недостаточно средств.",
                         f"Пополните баланс провайдера{where} — до пополнения запросы будут отклоняться.",
                         402)
        if status == 429:
            quota = "quota" in low or "exceeded" in low or "billing" in low
            return build(
                "LLM_QUOTA" if quota else "LLM_RATE_LIMIT",
                f"{name}: {'исчерпана квота' if quota else 'превышен лимит частоты запросов'} (HTTP 429).",
                (f"Проверьте баланс и лимиты в консоли провайдера{where}. "
                 "Бесплатный тариф Gemini ограничен и по запросам в минуту, и по числу запросов в сутки."
                 if quota else
                 "Слишком много запросов подряд. Подождите минуту и повторите; "
                 "при пакетной проверке уменьшите число этикеток за раз."),
                429)
        if status == 404:
            return build("LLM_MODEL_NOT_FOUND", f"{name}: запрошенная модель недоступна (HTTP 404).",
                         "Модель переименована или недоступна для вашего ключа. "
                         "Выберите другого провайдера в Конфигурации пайплайна либо обновите доступ у провайдера.",
                         404)
        if status == 400:
            if "api key" in low or "api_key" in low:
                return build("LLM_AUTH", f"{name}: ключ не принят (HTTP 400, invalid API key).",
                             f"Проверьте ключ в Администрирование → Провайдеры AI/OCR{where}.", 401)
            if "too large" in low or ("size" in low and "exceed" in low):
                return build("LLM_PAYLOAD_TOO_LARGE", f"{name}: изображение слишком велико для модели.",
                             "Уменьшите разрешение макета или разбейте PDF на страницы.", 413)
            return build("LLM_BAD_REQUEST", f"{name}: запрос отклонён (HTTP 400).",
                         "Обычно это неподдерживаемый формат изображения или слишком длинный текст. "
                         "Попробуйте другой макет или другого провайдера.", 400)
        if status >= 500:
            return build("LLM_UNAVAILABLE", f"{name}: сервис провайдера временно недоступен (HTTP {status}).",
                         "Сбой на стороне провайдера. Повторите проверку через несколько минут "
                         "или временно переключитесь на другого провайдера.", 503)
        return build("LLM_HTTP_ERROR", f"{name}: ошибка HTTP {status}.",
                     "Подробности — в техническом описании ниже.", 502)

    if isinstance(exc, httpx.TimeoutException):
        return build("LLM_TIMEOUT", f"{name}: превышено время ожидания ответа.",
                     "Модель не ответила вовремя. Повторите проверку; если повторяется — "
                     "выберите более быструю модель в Конфигурации пайплайна.", 504)

    if isinstance(exc, (httpx.ConnectError, httpx.TransportError)):
        return build("LLM_NETWORK", f"{name}: нет сетевого соединения с провайдером.",
                     "Сервер не может достучаться до API провайдера — проверьте доступность "
                     "(для российских площадок часть провайдеров заблокирована по региону).", 503)

    return build("LLM_ERROR", f"{name}: ошибка при обращении к провайдеру.",
                 "Подробности — в техническом описании ниже.", 502)


def not_configured(provider: str, subsystem: str = "llm") -> AppError:
    name = label(provider)
    console = CONSOLE_URLS.get(provider, "")
    return AppError(
        "PROVIDER_NOT_CONFIGURED", f"{name}: не задан API-ключ.",
        "Администрирование → Провайдеры AI/OCR: вставьте ключ и нажмите «Сохранить ключи»."
        + (f" Получить ключ: {console}" if console else ""),
        provider=provider, subsystem=subsystem, http_status=503)


# --- generic entry point -----------------------------------------------------
def classify(exc: Exception, *, provider: str = "", subsystem: str = "", stage: str = "",
             endpoint: str = "", bucket: str = "") -> AppError:
    """Turn any exception into an AppError. Never raises."""
    if isinstance(exc, AppError):
        if stage and not exc.stage:
            exc.stage = stage
        return exc

    # Celery hard/soft time limits.
    try:
        from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
        if isinstance(exc, (SoftTimeLimitExceeded, TimeLimitExceeded)):
            return AppError(
                "PIPELINE_TIMEOUT", "Проверка прервана по таймауту.",
                "Обработка заняла больше отведённого времени (обычно из-за медленного ответа модели "
                "или очень большого PDF). Повторите проверку или уменьшите размер макета.",
                str(exc), subsystem="pipeline", stage=stage, http_status=504)
    except Exception:
        pass

    try:
        from botocore.exceptions import BotoCoreError, ClientError
        if isinstance(exc, (BotoCoreError, ClientError)):
            err = storage_error(exc, endpoint=endpoint, bucket=bucket)
            err.stage = stage or err.stage
            return err
    except Exception:
        pass

    try:
        import httpx
        if isinstance(exc, httpx.HTTPError):
            return provider_error(exc, provider=provider, subsystem=subsystem or "llm", stage=stage)
    except Exception:
        pass

    if isinstance(exc, MemoryError):
        return AppError("PIPELINE_OOM", "Не хватило памяти при обработке макета.",
                        "PDF слишком тяжёлый для текущего worker'а. Уменьшите размер файла "
                        "или разбейте его на отдельные страницы.", str(exc),
                        subsystem="pipeline", stage=stage, http_status=507)

    return AppError("INTERNAL_ERROR", "Внутренняя ошибка приложения.",
                    "Техническое описание сохранено в Администрирование → Ошибки. "
                    "Повторите операцию; если повторяется — передайте код ошибки разработчику.",
                    f"{type(exc).__name__}: {exc}", provider=provider,
                    subsystem=subsystem or "app", stage=stage, http_status=500)
