import base64
import json
import httpx
from app.pipeline.base import BaseLLMProvider, BaseOCRProvider, OCRResult, TextBlock
from app.pipeline.providers.openai_provider import SPELLING_SYSTEM, PEN_SYSTEM, REGULATORY_SYSTEM, LAYOUT_SYSTEM, BENCHMARK_SYSTEM, _benchmark_user

_MODELS_URL = "https://api.anthropic.com/v1/models"


def _pick_claude(ids: list):
    """Choose a current Claude model from the account's /v1/models (sonnet > haiku > non-opus > opus)."""
    ids = [i for i in ids if i]
    return (next((i for i in ids if "sonnet" in i), None)
            or next((i for i in ids if "haiku" in i), None)
            or next((i for i in ids if i.startswith("claude") and "opus" not in i), None)
            or (ids[0] if ids else None))


def _loads(text: str) -> dict:
    """Tolerant JSON extraction from a model reply (handles ``` fences, prose, truncation)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    s, e = t.find("{"), t.rfind("}") + 1
    cand = t[s:e] if s != -1 and e > s else t
    for attempt in (cand, cand + "]}", cand + "}", cand + '"}]}'):
        try:
            return json.loads(attempt, strict=False)
        except Exception:
            continue
    return {"issues": []}


async def _resolve_model(client, api_key: str, current: str) -> str:
    try:
        r = await client.get(_MODELS_URL, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        ids = [m.get("id") for m in (r.json().get("data") or [])]
        return _pick_claude(ids) or current
    except Exception:
        return current


class AnthropicLLMProvider(BaseLLMProvider):
    _API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest"):
        self._api_key = api_key
        self._model = model
        self._resolved = False

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def _message(self, system: str, messages: list) -> dict:
        if getattr(self, "_focus", ""):
            system = f"ОСОБЫЙ ФОКУС ПРОВЕРКИ (высокий приоритет): {self._focus}\n\n" + system
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=90) as client:
            if not self._resolved:
                self._model = await _resolve_model(client, self._api_key, self._model)
                self._resolved = True
            payload = {"model": self._model, "max_tokens": 8192, "system": system, "messages": messages}
            resp = await client.post(self._API_URL, json=payload, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"Anthropic {resp.status_code} (model={self._model}): {resp.text[:200]}")
            return _loads(resp.json()["content"][0]["text"])

    async def check_spelling(self, text: str, dictionary_terms: list[str], brand_whitelist: list[str]) -> dict:
        user = f"Словарь: {', '.join(dictionary_terms[:100])}\nБренды: {', '.join(brand_whitelist[:50])}\n\nТекст:\n{text[:8000]}"
        return await self._message(SPELLING_SYSTEM, [{"role": "user", "content": user}])

    async def compare_benchmark(self, reference_text: str, issues: list) -> dict:
        return await self._message(BENCHMARK_SYSTEM, [{"role": "user", "content": _benchmark_user(reference_text, issues)}])

    async def compare_with_pen(self, ocr_text: str, pen_fields: dict, category: str) -> dict:
        user = f"Категория: {category}\nПЭН:\n{json.dumps(pen_fields, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}"
        return await self._message(PEN_SYSTEM, [{"role": "user", "content": user}])

    async def check_regulatory(self, ocr_text: str, category: str, checklist_rules: list[dict]) -> dict:
        user = f"Категория: {category}\nЧек-лист:\n{json.dumps(checklist_rules, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}"
        return await self._message(REGULATORY_SYSTEM, [{"role": "user", "content": user}])

    async def analyze_layout(self, image_bytes: bytes, category: str) -> dict:
        encoded = base64.b64encode(image_bytes).decode()
        messages = [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}},
            {"type": "text", "text": f"Категория продукта: {category}. Проанализируй макет."},
        ]}]
        return await self._message(LAYOUT_SYSTEM, messages)

    async def test_connection(self) -> bool:
        # GET /v1/models validates the key without depending on a specific model ID.
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.anthropic.com/v1/models", headers=headers)
            resp.raise_for_status()
            return True


class AnthropicVisionProvider(BaseOCRProvider):
    """Use Claude for OCR on images."""
    _API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest"):
        self._api_key = api_key
        self._model = model
        self._resolved = False

    @property
    def provider_name(self) -> str:
        return "anthropic_vision"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=60) as client:
            if not self._resolved:
                self._model = await _resolve_model(client, self._api_key, self._model)
                self._resolved = True
            payload = {
                "model": self._model, "max_tokens": 4096,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}},
                    {"type": "text", "text": f"Извлеки весь текст с этого изображения. Язык: {hint_lang}. Верни только текст без пояснений."},
                ]}],
            }
            resp = await client.post(self._API_URL, json=payload, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"Anthropic vision {resp.status_code} (model={self._model}): {resp.text[:200]}")
            text = resp.json()["content"][0]["text"]
        block = TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})
        return OCRResult(blocks=[block], full_text=text)

    async def test_connection(self) -> bool:
        try:
            await self.extract_text(b"", "ru")
            return True
        except Exception:
            return False
