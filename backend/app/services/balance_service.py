"""Remaining balance / quota per provider, converted to roubles.

Honest scope - not every provider exposes a balance:

  Selectel   real API (account balance).           status "ok"
  ABBYY      real API (remaining pages/credits).   status "ok"
  Gemini, OpenAI, Anthropic, Grok, Yandex Vision
             no public "how much money is left" endpoint exists for an API key.
             Google/OpenAI/Anthropic expose usage and invoices in their consoles
             only. For these the admin records the figure by hand in
             Администрирование → Балансы; it is shown with the date it was entered
             and clearly marked as a manual figure, never as a live reading.

Conversion to RUB uses the Bank of Russia daily rates (cbr-xml-daily.ru, no key
required), cached for an hour.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import httpx

from app.core.errors import CONSOLE_URLS, label

# Providers whose balance genuinely cannot be read through an API key.
NO_BALANCE_API = {
    "gemini": "Google не предоставляет API остатка средств — смотрите биллинг Google Cloud / AI Studio.",
    "openai": "OpenAI закрыл публичный доступ к остатку по API-ключу — смотрите Billing в консоли.",
    "anthropic": "Anthropic не предоставляет API остатка — смотрите Billing в консоли.",
    "grok": "xAI не предоставляет API остатка — смотрите консоль xAI.",
    "yandex_vision": "Остаток Yandex Cloud доступен только через Billing API с IAM-токеном "
                     "(отдельно от ключа Vision) — смотрите консоль.",
}

ALL_PROVIDERS = ["gemini", "openai", "anthropic", "grok", "yandex_vision", "abbyy", "selectel"]

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
# The Bank of Russia quotes 54 currencies and the shekel is not among them, so a
# balance held in ILS gets its rouble figure through a USD cross-rate instead.
CROSS_FX_URL = "https://open.er-api.com/v6/latest/USD"
# Currencies the app offers for a manual balance; anything missing from CBR is
# filled in from the cross-rate source.
OFFERED_CURRENCIES = ("USD", "EUR", "ILS")
_RATE_CACHE: dict = {"at": 0.0, "rates": {}, "cross": []}
RATE_TTL = 3600


async def _cbr_rates() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(CBR_URL)
        resp.raise_for_status()
        out = {}
        for code, v in (resp.json().get("Valute") or {}).items():
            nominal = float(v.get("Nominal") or 1)
            value = float(v.get("Value") or 0)
            if nominal > 0 and value > 0:
                out[code.upper()] = value / nominal
        return out


async def _cross_rates(missing: list[str], usd_rub: float) -> dict:
    """Roubles per unit for currencies CBR does not quote, via USD."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(CROSS_FX_URL)
        resp.raise_for_status()
        per_usd = (resp.json() or {}).get("rates") or {}
    out = {}
    for code in missing:
        rate = per_usd.get(code)
        if rate:
            try:
                out[code] = usd_rub / float(rate)   # RUB per USD / units per USD
            except (TypeError, ValueError, ZeroDivisionError):
                continue
    return out


async def get_rates() -> dict:
    """{'USD': 84.2, 'ILS': 25.4, 'RUB': 1.0} - roubles per one unit. Cached 1 h.

    A failure anywhere here degrades to "no rouble figure" rather than a wrong one:
    callers render the original currency untouched when a rate is absent.
    """
    now = time.time()
    if _RATE_CACHE["rates"] and now - _RATE_CACHE["at"] < RATE_TTL:
        return _RATE_CACHE["rates"]

    rates = {"RUB": 1.0}
    cross: list[str] = []
    try:
        rates.update(await _cbr_rates())
    except Exception:
        return _RATE_CACHE["rates"] or rates    # stale rates beat no rates

    missing = [c for c in OFFERED_CURRENCIES if c not in rates]
    if missing and rates.get("USD"):
        try:
            filled = await _cross_rates(missing, rates["USD"])
            rates.update(filled)
            cross = sorted(filled)
        except Exception:
            pass    # the currency simply gets no rouble figure

    _RATE_CACHE.update({"at": now, "rates": rates, "cross": cross})
    return rates


def rates_source_note() -> str:
    cross = _RATE_CACHE.get("cross") or []
    note = "ЦБ РФ (cbr-xml-daily.ru)"
    if cross:
        note += f"; {', '.join(cross)} — кросс-курс через USD (open.er-api.com), ЦБ их не котирует"
    return note


def to_rub(amount: float | None, currency: str, rates: dict) -> float | None:
    if amount is None:
        return None
    rate = rates.get((currency or "RUB").upper())
    return round(amount * rate, 2) if rate else None


def _find_number(payload, keys: tuple[str, ...]):
    """Walk a JSON payload for the first numeric value under one of `keys`.

    Provider balance schemas are undocumented and change; searching by key name is
    more durable than hard-coding a path, and we report when nothing matched
    instead of inventing a number.
    """
    found = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                if k.lower() in keys and isinstance(v, (int, float)) and not isinstance(v, bool):
                    found.append((p, float(v)))
                walk(v, p)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(payload)
    return found


def _entry(provider: str, **kw) -> dict:
    base = {
        "provider": provider,
        "label": label(provider),
        "status": "unsupported",
        "amount": None,
        "currency": None,
        "amount_rub": None,
        "units": None,
        "source": None,
        "as_of": None,
        "message": "",
        "hint": "",
        "console_url": CONSOLE_URLS.get(provider, ""),
    }
    base.update(kw)
    return base


# --- providers with a real API ----------------------------------------------
async def fetch_selectel(token: str) -> dict:
    """Selectel account balance. Requires a Selectel API token (not the S3 key)."""
    if not token:
        return _entry("selectel", status="not_configured",
                      message="Не задан API-токен Selectel.",
                      hint="Администрирование → Хранилище: поле «API-токен Selectel». "
                           "Токен создаётся в панели Selectel (Профиль → Ключи API) и нужен "
                           "только для показа баланса — загрузку файлов он не затрагивает.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.selectel.ru/v2/account/info",
                                    headers={"X-token": token})
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        return _entry("selectel", status="error",
                      message=f"Selectel вернул HTTP {code} при запросе баланса.",
                      hint=("Токен неверен или отозван — перевыпустите его в панели Selectel."
                            if code in (401, 403) else
                            "Повторите позже; на загрузку файлов это не влияет."))
    except Exception as e:
        return _entry("selectel", status="error",
                      message=f"Не удалось получить баланс Selectel: {type(e).__name__}.",
                      hint="Проверьте сетевой доступ к api.selectel.ru.")

    hits = _find_number(payload, ("balance", "primary_balance", "main", "primary"))
    if not hits:
        return _entry("selectel", status="error",
                      message="Selectel ответил, но поле баланса в ответе не найдено.",
                      hint=f"Ключи ответа: {list(payload)[:10]}. "
                           "Формат ответа изменился — нужно обновить разбор.")
    path, raw = hits[0]
    # Selectel reports money in kopecks.
    amount = round(raw / 100.0, 2)
    return _entry("selectel", status="ok", amount=amount, currency="RUB", amount_rub=amount,
                  source="api", as_of=datetime.now(timezone.utc).isoformat(),
                  message=f"Баланс аккаунта Selectel (поле «{path}», пересчитано из копеек).")


async def fetch_abbyy(app_id: str, password: str, base_url: str) -> dict:
    """ABBYY Cloud OCR SDK reports remaining pages/credits, not money."""
    if not app_id or not password:
        return _entry("abbyy", status="not_configured",
                      message="Не заданы Application ID / Password для ABBYY.",
                      hint="Администрирование → Провайдеры AI/OCR.")
    url = (base_url or "https://cloud.ocrsdk.com").rstrip("/") + "/v2/getApplicationInfo"
    try:
        async with httpx.AsyncClient(timeout=15, auth=(app_id, password)) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as e:
        return _entry("abbyy", status="error",
                      message=f"ABBYY вернул HTTP {e.response.status_code}.",
                      hint="Проверьте Application ID и пароль.")
    except Exception as e:
        return _entry("abbyy", status="error",
                      message=f"Не удалось получить остаток ABBYY: {type(e).__name__}.")

    units = {}
    for key in ("pages", "fields", "credits"):
        hits = _find_number(payload, (key,))
        if hits:
            units[key] = hits[0][1]
    if not units:
        return _entry("abbyy", status="error",
                      message="ABBYY ответил, но остаток в ответе не найден.",
                      hint=f"Ключи ответа: {list(payload)[:10]}.")
    return _entry("abbyy", status="ok", units=units, source="api",
                  as_of=datetime.now(timezone.utc).isoformat(),
                  message="Остаток по тарифу ABBYY (страницы/поля), не деньги.")


# --- manual snapshots --------------------------------------------------------
def _manual_key(provider: str) -> str:
    return f"balance_manual_{provider}"


async def get_manual(db, provider: str) -> dict | None:
    from app.services import config_service
    raw = await config_service.get_config(db, _manual_key(provider))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def set_manual(db, provider: str, amount: float | None, currency: str,
                     note: str = "", user_id=None) -> dict:
    from app.services import config_service
    if amount is None:
        await config_service.set_config(db, _manual_key(provider), "", updated_by_id=user_id)
        return {}
    payload = {
        "amount": float(amount),
        "currency": (currency or "RUB").upper(),
        "note": note or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await config_service.set_config(db, _manual_key(provider),
                                    json.dumps(payload, ensure_ascii=False), updated_by_id=user_id)
    return payload


# --- aggregate ---------------------------------------------------------------
async def get_balances(db, providers: list[str] | None = None) -> list[dict]:
    from app.services import config_service

    names = providers or ALL_PROVIDERS
    rates = await get_rates()
    out: list[dict] = []

    for provider in names:
        if provider == "selectel":
            token = await config_service.get_config(db, "selectel_api_token")
            entry = await fetch_selectel(token or "")
        elif provider == "abbyy":
            entry = await fetch_abbyy(
                (await config_service.get_config(db, "api_key_abbyy")) or "",
                (await config_service.get_config(db, "abbyy_password")) or "",
                (await config_service.get_config(db, "abbyy_url")) or "https://cloud.ocrsdk.com",
            )
        else:
            configured = bool(await config_service.get_config(db, f"api_key_{provider}"))
            entry = _entry(provider, status="unsupported",
                           message=NO_BALANCE_API.get(provider, "Провайдер не отдаёт остаток по API."),
                           hint="Впишите остаток вручную ниже — он будет показан специалистам "
                                "с датой обновления."
                                + ("" if configured else " Ключ этого провайдера пока не задан."))

        # A manual figure fills in where the API cannot answer; it never overrides
        # a live reading, and it is always labelled as manual with its own date.
        manual = await get_manual(db, provider)
        if manual:
            entry["manual"] = {
                **manual,
                "amount_rub": to_rub(manual.get("amount"), manual.get("currency", "RUB"), rates),
            }
            if entry["status"] != "ok":
                entry.update({
                    "status": "manual",
                    "amount": manual.get("amount"),
                    "currency": manual.get("currency"),
                    "amount_rub": entry["manual"]["amount_rub"],
                    "source": "manual",
                    "as_of": manual.get("updated_at"),
                })
        out.append(entry)

    return out


async def get_active_balance(db) -> dict | None:
    """Balance for the provider the pipeline is currently configured to use.

    This is what the specialist sees on the check screen - they should not have to
    know which model the admin selected.
    """
    from app.services import config_service
    cfg = await config_service.get_pipeline_config(db)
    active = (cfg.get("unified_llm") if cfg.get("pipeline_mode") == "unified"
              else cfg.get("llm_provider")) or cfg.get("llm_provider") or cfg.get("unified_llm")
    if not active:
        return None
    entries = await get_balances(db, [active])
    return entries[0] if entries else None
