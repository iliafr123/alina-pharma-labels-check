"""Grok uses OpenAI-compatible API."""
from app.pipeline.providers.openai_provider import OpenAILLMProvider


class GrokLLMProvider(OpenAILLMProvider):
    def __init__(self, api_key: str, model: str = "grok-2-latest"):
        super().__init__(api_key, model)
        self._base_url = "https://api.x.ai/v1"

    @property
    def provider_name(self) -> str:
        return "grok"

    async def _chat(self, system: str, user: str) -> dict:
        import json
        import httpx
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json={"model": self._model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "response_format": {"type": "json_object"}, "max_tokens": 4096},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])
