import base64
import json
import httpx
from app.pipeline.base import BaseLLMProvider, BaseOCRProvider, OCRResult, TextBlock
from app.pipeline.providers.openai_provider import SPELLING_SYSTEM, PEN_SYSTEM, REGULATORY_SYSTEM, LAYOUT_SYSTEM


class AnthropicLLMProvider(BaseLLMProvider):
    _API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def _message(self, system: str, messages: list) -> dict:
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": self._model, "max_tokens": 4096, "system": system, "messages": messages}
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(self._API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"]
            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end]) if start != -1 else {"issues": []}

    async def check_spelling(self, text: str, dictionary_terms: list[str], brand_whitelist: list[str]) -> dict:
        user = f"Словарь: {', '.join(dictionary_terms[:100])}\nБренды: {', '.join(brand_whitelist[:50])}\n\nТекст:\n{text[:8000]}"
        return await self._message(SPELLING_SYSTEM, [{"role": "user", "content": user}])

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
        try:
            result = await self._message("Ответь одним словом: OK", [{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False


class AnthropicVisionProvider(BaseOCRProvider):
    """Use Claude for OCR on images."""
    _API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic_vision"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {
            "model": self._model, "max_tokens": 4096,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}},
                {"type": "text", "text": f"Извлеки весь текст с этого изображения. Язык: {hint_lang}. Верни только текст без пояснений."},
            ]}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"]
        block = TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})
        return OCRResult(blocks=[block], full_text=text)

    async def test_connection(self) -> bool:
        try:
            await self.extract_text(b"", "ru")
            return True
        except Exception:
            return False
