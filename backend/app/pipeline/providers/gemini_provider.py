import asyncio
import base64
import json
import httpx
from app.pipeline.base import BaseLLMProvider, BaseOCRProvider, OCRResult, TextBlock
from app.pipeline.providers.openai_provider import SPELLING_SYSTEM, PEN_SYSTEM, REGULATORY_SYSTEM, LAYOUT_SYSTEM, BENCHMARK_SYSTEM, _benchmark_user, CHECKLIST_SYSTEM, _checklist_user


class GeminiProvider(BaseLLMProvider, BaseOCRProvider):
    _API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def _headers(self) -> dict:
        # Key in header (not URL) so it never leaks into logs/error messages.
        return {"x-goog-api-key": self._api_key}

    async def _generate(self, parts: list, json_output: bool = False) -> str:
        # Optional per-check focus instruction (set on the provider for analysis calls only).
        if json_output and getattr(self, "_focus", ""):
            parts = [{"text": f"ОСОБЫЙ ФОКУС ПРОВЕРКИ (высокий приоритет): {self._focus}"}] + parts
        url = f"{self._API_BASE}/{self._model}:generateContent"
        gen_cfg = {"maxOutputTokens": 8192}
        if json_output:
            gen_cfg["responseMimeType"] = "application/json"  # force valid JSON
            gen_cfg["maxOutputTokens"] = 16384  # 23-item checklist on hi-res OCR can be long
        payload = {"contents": [{"parts": parts}], "generationConfig": gen_cfg}
        last_exc = None
        # Retry transient errors (429/5xx) — Gemini Flash returns 503 under load.
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    resp = await client.post(url, json=payload, headers=self._headers)
                    resp.raise_for_status()
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_exc = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise last_exc

    @staticmethod
    def _loads(raw: str) -> dict:
        # Robust JSON parse: strip markdown fences, never crash the pipeline.
        s = (raw or "").strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s.lstrip().lower().startswith("json"):
                s = s.lstrip()[4:]
        start, end = s.find("{"), s.rfind("}") + 1
        if start == -1 or end <= start:
            return {"issues": []}
        try:
            return json.loads(s[start:end])
        except Exception:
            return {"issues": []}

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        parts = [
            {"inline_data": {"mime_type": "image/jpeg", "data": encoded}},
            {"text": f"Извлеки весь текст с этого изображения. Язык: {hint_lang}. Верни только текст."},
        ]
        text = await self._generate(parts)
        block = TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})
        return OCRResult(blocks=[block], full_text=text)

    async def check_spelling(self, text: str, dictionary_terms: list[str], brand_whitelist: list[str]) -> dict:
        prompt = f"{SPELLING_SYSTEM}\n\nСловарь: {', '.join(dictionary_terms[:100])}\nБренды: {', '.join(brand_whitelist[:50])}\n\nТекст:\n{text[:8000]}\n\nВерни только JSON."
        return self._loads(await self._generate([{"text": prompt}], json_output=True))

    async def compare_benchmark(self, reference_text: str, issues: list) -> dict:
        prompt = f"{BENCHMARK_SYSTEM}\n\n{_benchmark_user(reference_text, issues)}\n\nВерни только JSON."
        return self._loads(await self._generate([{"text": prompt}], json_output=True))

    async def compare_with_pen(self, ocr_text: str, pen_fields: dict, category: str) -> dict:
        prompt = f"{PEN_SYSTEM}\n\nКатегория: {category}\nПЭН:\n{json.dumps(pen_fields, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}\n\nВерни только JSON."
        return self._loads(await self._generate([{"text": prompt}], json_output=True))

    async def build_checklist(self, ocr_text: str, pen_fields: dict, items: list) -> dict:
        prompt = f"{CHECKLIST_SYSTEM}\n\n{_checklist_user(ocr_text, pen_fields, items)}\n\nВерни только JSON."
        return self._loads(await self._generate([{"text": prompt}], json_output=True))

    async def check_regulatory(self, ocr_text: str, category: str, checklist_rules: list[dict]) -> dict:
        prompt = f"{REGULATORY_SYSTEM}\n\nКатегория: {category}\nЧек-лист:\n{json.dumps(checklist_rules, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}\n\nВерни только JSON."
        return self._loads(await self._generate([{"text": prompt}], json_output=True))

    async def analyze_layout(self, image_bytes: bytes, category: str) -> dict:
        encoded = base64.b64encode(image_bytes).decode()
        prompt = f"{LAYOUT_SYSTEM}\n\nКатегория продукта: {category}. Верни только JSON."
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": encoded}}, {"text": prompt}]
        return self._loads(await self._generate(parts, json_output=True))

    async def test_connection(self) -> bool:
        # List models — validates the key without depending on a specific model name.
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self._API_BASE, headers=self._headers)
            resp.raise_for_status()
            return True
