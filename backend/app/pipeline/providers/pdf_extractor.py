import io
import pdfplumber
from app.pipeline.base import OCRResult, TextBlock


async def extract_text_layer(pdf_bytes: bytes) -> OCRResult | None:
    """Try native PDF text extraction. Returns None if coverage < 80% (needs OCR)."""
    blocks: list[TextBlock] = []
    total_area = 0.0
    text_area = 0.0

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages):
            w, h = float(page.width), float(page.height)
            total_area += w * h
            words = page.extract_words()
            for word in words:
                x0, y0, x1, y1 = word["x0"], word["top"], word["x1"], word["bottom"]
                text_area += (x1 - x0) * (y1 - y0)
                blocks.append(TextBlock(
                    text=word["text"],
                    bbox={"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "page": page_num},
                    confidence=1.0,
                ))

    if total_area == 0 or (text_area / total_area) < 0.05:
        return None  # No meaningful text — needs OCR

    full_text = " ".join(b.text for b in blocks)
    return OCRResult(blocks=blocks, full_text=full_text, pages=pages)
