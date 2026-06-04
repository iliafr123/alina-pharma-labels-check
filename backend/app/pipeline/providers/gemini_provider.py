import base64
import json
import httpx
from app.pipeline.base import BaseLLMProvider, BaseOCRProvider, OCRResult, TextBlock
from app.pipeline.providers.openai_provider import SPELLING_SYSTEM, PEN_SYSTEM, REGULATORY_SYSTEM, LAYOUT_SYSTEM


class GeminiProvider(BaseLLMProvider, BaseOCRProvider):
    _API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def _generate(self, parts: list) -> str:
        url = f"{self._API_BASE}/{self._model}:generateContent?key={self._api_key}"
        payload = {"contents": [{"parts": parts}], "generationConfig": {"maxOutputTokens": 4096}}
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

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
        raw = await self._generate([{"text": prompt}])
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end]) if start != -1 else {"issues": []}

    async def compare_with_pen(self, ocr_text: str, pen_fields: dict, category: str) -> dict:
        prompt = f"{PEN_SYSTEM}\n\nКатегория: {category}\nПЭН:\n{json.dumps(pen_fields, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}\n\nВерни только JSON."
        raw = await self._generate([{"text": prompt}])
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end]) if start != -1 else {"issues": []}

    async def check_regulatory(self, ocr_text: str, category: str, checklist_rules: list[dict]) -> dict:
        prompt = f"{REGULATORY_SYSTEM}\n\nКатегория: {category}\nЧек-лист:\n{json.dumps(checklist_rules, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}\n\nВерни только JSON."
        raw = await self._generate([{"text": prompt}])
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end]) if start != -1 else {"issues": []}

    async def analyze_layout(self, image_bytes: bytes, category: str) -> dict:
        encoded = base64.b64encode(image_bytes).decode()
        prompt = f"{LAYOUT_SYSTEM}\n\nКатегория продукта: {category}. Верни только JSON."
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": encoded}}, {"text": prompt}]
        raw = await self._generate(parts)
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end]) if start != -1 else {"issues": []}

    async def test_connection(self) -> bool:
        try:
            await self._generate([{"text": "ping"}])
            return True
        except Exception:
            return False
