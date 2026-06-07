import base64
import httpx
from app.pipeline.base import BaseOCRProvider, OCRResult, TextBlock


class YandexVisionProvider(BaseOCRProvider):
    _API_URL = "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze"

    def __init__(self, api_key: str, folder_id: str | None = None):
        self._api_key = api_key
        self._folder_id = folder_id or ""

    @property
    def provider_name(self) -> str:
        return "yandex_vision"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        payload = {
            "folderId": self._folder_id,
            "analyzeSpecs": [{
                "content": encoded,
                "features": [{"type": "TEXT_DETECTION", "textDetectionConfig": {"languageCodes": [hint_lang, "en"]}}],
            }]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self._API_URL,
                json=payload,
                headers={"Authorization": f"Api-Key {self._api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        blocks: list[TextBlock] = []
        try:
            pages = data["results"][0]["results"][0]["textDetection"]["pages"]
            for page_num, page in enumerate(pages):
                for block in page.get("blocks", []):
                    for line in block.get("lines", []):
                        text = " ".join(w.get("text", "") for w in line.get("words", []))
                        verts = line.get("boundingBox", {}).get("vertices", [])
                        if verts and text.strip():
                            xs = [v.get("x", 0) for v in verts]
                            ys = [v.get("y", 0) for v in verts]
                            blocks.append(TextBlock(
                                text=text,
                                bbox={"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys), "page": page_num},
                                confidence=line.get("confidence", 0.9),
                            ))
        except (KeyError, IndexError):
            pass

        return OCRResult(blocks=blocks, full_text="\n".join(b.text for b in blocks), pages=len(pages) if "pages" in locals() else 1)

    async def test_connection(self) -> bool:
        # 1x1 white pixel PNG — validates key + folderId; errors propagate to admin for a real message.
        pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg==")
        await self.extract_text(pixel)
        return True
