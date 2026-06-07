import asyncio
import httpx
from app.pipeline.base import BaseOCRProvider, OCRResult, TextBlock


class ABBYYProvider(BaseOCRProvider):
    """ABBYY Cloud OCR SDK v2 — async OCR (submit image, poll task, download text)."""

    def __init__(self, app_id: str, password: str, base_url: str = "https://cloud.ocrsdk.com"):
        self._auth = (app_id or "", password or "")
        self._base = (base_url or "https://cloud.ocrsdk.com").rstrip("/")

    @property
    def provider_name(self) -> str:
        return "abbyy"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        async with httpx.AsyncClient(timeout=120, auth=self._auth) as client:
            r = await client.post(
                f"{self._base}/v2/processImage",
                params={"language": "Russian,English", "exportFormat": "txtUnstructured"},
                content=image_bytes,
                headers={"Content-Type": "application/octet-stream"},
            )
            r.raise_for_status()
            tid = r.json().get("taskId")
            for _ in range(40):
                s = await client.get(f"{self._base}/v2/getTaskStatus", params={"taskId": tid})
                s.raise_for_status()
                st = s.json()
                status = st.get("status")
                if status == "Completed":
                    urls = st.get("resultUrls") or []
                    if not urls:
                        return OCRResult(full_text="")
                    txt = await client.get(urls[0])
                    txt.raise_for_status()
                    text = txt.text
                    return OCRResult(blocks=[TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})], full_text=text)
                if status in ("ProcessingFailed", "NotEnoughCredits", "Deleted"):
                    raise RuntimeError(f"ABBYY: задача {status} {st.get('error', '')}")
                await asyncio.sleep(2)  # Submitted / Queued / InProgress
            raise RuntimeError("ABBYY: превышено время ожидания результата")

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient(timeout=20, auth=self._auth) as client:
            resp = await client.get(f"{self._base}/v2/getApplicationInfo")
            resp.raise_for_status()
            return True
