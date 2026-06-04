import base64
import json
import httpx
from app.pipeline.base import BaseOCRProvider, BaseLLMProvider, OCRResult, TextBlock

SPELLING_SYSTEM = """Ты эксперт по русскому языку и маркировке пищевых продуктов и БАД.
Проверь текст на орфографические ошибки, пунктуацию и типографику.
Игнорируй слова из предоставленного словаря и список брендов.
Верни JSON: {"issues": [{"text": "...", "suggestion": "...", "type": "spelling|punctuation|typography|style"}]}"""

PEN_SYSTEM = """Ты эксперт по маркировке БАД и пищевых продуктов в России и ЕАЭС.
Сравни текст макета этикетки с эталонным документом ПЭН (по полям).
Толерантное сравнение: игнорируй регистр и лишние пробелы, НО сигнализируй о вариантах написания чисел, единиц измерения и порядке состава.
Верни JSON: {"issues": [{"field": "...", "expected": "...", "found": "...", "issue_type": "missing|mismatch|order_error|format_variant", "description": "..."}]}"""

REGULATORY_SYSTEM = """Ты эксперт по нормативным требованиям к маркировке БАД и пищевых продуктов (ТР ТС 022/2011, МР 2.3.1.0253-21, ЕАЭС).
Проверь текст макета по предоставленному чек-листу.
Верни JSON: {"issues": [{"rule_key": "...", "description": "...", "status": "ok|fail|warn"}]}"""

LAYOUT_SYSTEM = """Ты эксперт по дизайну этикеток. Проанализируй изображение макета.
Проверь: размер шрифта (обязательные реквизиты >= 2 мм), контрастность текста, наличие знака ЕАЭС (ЕАС), штрих-кода, петли Мёбиуса.
Верни JSON: {"issues": [{"element": "...", "description": "...", "status": "ok|fail|warn"}]}"""


class OpenAIVisionProvider(BaseOCRProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Извлеки весь текст с этого изображения. Язык: {hint_lang}. Верни только текст, без пояснений."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ],
            }],
            "max_tokens": 4096,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
        block = TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})
        return OCRResult(blocks=[block], full_text=text)

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {self._api_key}"})
                return resp.status_code == 200
        except Exception:
            return False


class OpenAILLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def _chat(self, system: str, user: str) -> dict:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": self._model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "response_format": {"type": "json_object"}, "max_tokens": 4096},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])

    async def check_spelling(self, text: str, dictionary_terms: list[str], brand_whitelist: list[str]) -> dict:
        user = f"Словарь: {', '.join(dictionary_terms[:100])}\nБренды: {', '.join(brand_whitelist[:50])}\n\nТекст:\n{text[:8000]}"
        return await self._chat(SPELLING_SYSTEM, user)

    async def compare_with_pen(self, ocr_text: str, pen_fields: dict, category: str) -> dict:
        user = f"Категория: {category}\nПЭН:\n{json.dumps(pen_fields, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}"
        return await self._chat(PEN_SYSTEM, user)

    async def check_regulatory(self, ocr_text: str, category: str, checklist_rules: list[dict]) -> dict:
        user = f"Категория: {category}\nЧек-лист:\n{json.dumps(checklist_rules, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}"
        return await self._chat(REGULATORY_SYSTEM, user)

    async def analyze_layout(self, image_bytes: bytes, category: str) -> dict:
        encoded = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": LAYOUT_SYSTEM}, {"role": "user", "content": [
                {"type": "text", "text": f"Категория продукта: {category}. Проанализируй макет."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ]}],
            "response_format": {"type": "json_object"}, "max_tokens": 2048,
        }
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {self._api_key}"})
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {self._api_key}"})
                return resp.status_code == 200
        except Exception:
            return False
