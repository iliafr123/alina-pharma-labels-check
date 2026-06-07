"""Grok (xAI) uses an OpenAI-compatible API."""
import base64
import json
import httpx
from app.pipeline.base import BaseOCRProvider, OCRResult, TextBlock
from app.pipeline.providers.openai_provider import OpenAILLMProvider

# Vision-capable Grok models, preferred order (multimodal grok-4 or dedicated vision model).
_VISION_PREFERRED = ("grok-2-vision-1212", "grok-2-vision", "grok-4", "grok-4-latest", "grok-4-fast")

# Preference order when the configured model is unavailable — resolved against the
# account's actual /models list so we never hardcode a model that may be retired.
_PREFERRED = ("grok-4", "grok-4-latest", "grok-3", "grok-3-latest", "grok-2-1212", "grok-beta")


class GrokLLMProvider(OpenAILLMProvider):
    def __init__(self, api_key: str, model: str = "grok-3"):
        super().__init__(api_key, model)
        self._base_url = "https://api.x.ai/v1"
        self._model_resolved = False

    @property
    def provider_name(self) -> str:
        return "grok"

    async def _resolve_model(self, client: httpx.AsyncClient) -> str:
        if self._model_resolved:
            return self._model
        try:
            r = await client.get(f"{self._base_url}/models", headers={"Authorization": f"Bearer {self._api_key}"})
            ids = [m.get("id") for m in (r.json().get("data") or [])]
            chat = [i for i in ids if i and i.startswith("grok") and "vision" not in i and "image" not in i]
            picked = next((p for p in _PREFERRED if p in ids), None) or (chat[0] if chat else self._model)
            self._model = picked
        except Exception:
            pass
        self._model_resolved = True
        return self._model

    async def _chat(self, system: str, user: str) -> dict:
        async with httpx.AsyncClient(timeout=90) as client:
            model = await self._resolve_model(client)
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "response_format": {"type": "json_object"}, "max_tokens": 4096},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Grok {resp.status_code} (model={model}): {resp.text[:300]}")
            return json.loads(resp.json()["choices"][0]["message"]["content"])


class GrokVisionProvider(BaseOCRProvider):
    """Grok (xAI) as a vision OCR provider — lets 'LLM-only grok' read the mockup itself."""
    _BASE = "https://api.x.ai/v1"

    def __init__(self, api_key: str, model: str = "grok-2-vision-1212"):
        self._api_key = api_key
        self._model = model
        self._resolved = False
        self._ids: list = []

    @property
    def provider_name(self) -> str:
        return "grok"

    async def _resolve(self, client: httpx.AsyncClient) -> str:
        if self._resolved:
            return self._model
        try:
            r = await client.get(f"{self._BASE}/models", headers={"Authorization": f"Bearer {self._api_key}"})
            ids = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
            self._ids = ids
            vis = [i for i in ids if "vision" in i or "image" in i]
            g4 = [i for i in ids if i.startswith("grok-4")]  # grok-4 family is multimodal
            self._model = (next((p for p in _VISION_PREFERRED if p in ids), None)
                           or (vis[0] if vis else None) or (g4[0] if g4 else None) or self._model)
        except Exception:
            pass
        self._resolved = True
        return self._model

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        async with httpx.AsyncClient(timeout=90) as client:
            model = await self._resolve(client)
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": f"Извлеки весь текст с этого изображения. Язык: {hint_lang}. Верни только текст, без пояснений."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ]}],
                "max_tokens": 4096,
            }
            resp = await client.post(f"{self._BASE}/chat/completions", json=payload, headers={"Authorization": f"Bearer {self._api_key}"})
            if resp.status_code >= 400:
                raise RuntimeError(f"GrokVision {resp.status_code} (model={model}, available={self._ids}): {resp.text[:200]}")
            text = resp.json()["choices"][0]["message"]["content"]
        return OCRResult(blocks=[TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})], full_text=text)

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._BASE}/models", headers={"Authorization": f"Bearer {self._api_key}"})
            resp.raise_for_status()
            return True
