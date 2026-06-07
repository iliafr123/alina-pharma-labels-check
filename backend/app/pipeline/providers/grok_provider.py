"""Grok (xAI) uses an OpenAI-compatible API."""
import json
import httpx
from app.pipeline.providers.openai_provider import OpenAILLMProvider

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
