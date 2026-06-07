import base64
import httpx
from app.pipeline.base import BaseOCRProvider, OCRResult, TextBlock


class YandexVisionProvider(BaseOCRProvider):
    """Yandex Cloud OCR API (ocr/v1/recognizeText) — current OCR endpoint."""
    _API_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"

    def __init__(self, api_key: str, folder_id: str | None = None):
        self._api_key = api_key
        self._folder_id = folder_id or ""

    @property
    def provider_name(self) -> str:
        return "yandex_vision"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        payload = {
            "mimeType": "image/jpeg",
            "languageCodes": ["ru", "en"],
            "model": "page",
            "content": base64.b64encode(image_bytes).decode(),
        }
        headers = {
            "Authorization": f"Api-Key {self._api_key}",
            "x-folder-id": self._folder_id,
            "x-data-logging-enabled": "true",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        # recognizeText returns {"result": {"textAnnotation": {"fullText": "...", "blocks": [...]}}}
        ann = (data.get("result") or {}).get("textAnnotation") or {}
        full = ann.get("fullText", "") or ""
        blocks = []
        for b in ann.get("blocks", []):
            for line in b.get("lines", []):
                txt = line.get("text") or " ".join(w.get("text", "") for w in line.get("words", []))
                if txt.strip():
                    blocks.append(TextBlock(text=txt, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0}))
        return OCRResult(blocks=blocks, full_text=full or "\n".join(b.text for b in blocks))

    async def test_connection(self) -> bool:
        # Minimal request: 401/403 => bad key/folder; any other response means auth reached the service.
        try:
            await self.extract_text(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise
            return True
