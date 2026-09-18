"""Regression tests for the mockup-quality gate.

Fixtures are built to sit either side of the calibrated thresholds documented in
app/services/quality_service.py, so a threshold change that would start rejecting
real artwork (or start accepting unreadable files) fails here.
"""
import io

import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.core.errors import AppError
from app.services import quality_service as q

PT_PER_MM = 72.0 / 25.4


def _textured(width: int, height: int) -> Image.Image:
    """White field with fine dark strokes - stands in for printed text: plenty of
    high-frequency edges, so a sharp version scores high and a blurred one low."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    step = max(4, height // 60)
    for y in range(step, height - step, step):
        d.line([(10, y), (width - 10, y)], fill=(15, 15, 15), width=1)
    for x in range(step, width - step, step * 3):
        d.line([(x, 10), (x, height - 10)], fill=(40, 40, 40), width=1)
    return img


def _bold(width: int, height: int) -> Image.Image:
    """Thick dark bars. Heavy blur softens their edges (low sharpness) while the
    field stays high-contrast - which is how real label artwork degrades, and what
    separates "blurred" from "blank". The thin-stroke _textured() fixture washes
    out to a flat grey under the same blur.
    """
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    bar = max(8, height // 24)
    for i, y in enumerate(range(bar, height - bar, bar * 2)):
        d.rectangle([20, y, width - 20, y + bar], fill=(20, 20, 20) if i % 2 == 0 else (60, 60, 60))
    return img


def jpg_bytes(img: Image.Image, dpi: tuple[int, int] | None = None) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, **({"dpi": dpi} if dpi else {}))
    return buf.getvalue()


def vector_pdf(width_mm: float = 100, height_mm: float = 50) -> bytes:
    """A real print PDF: vector page with a genuine text layer."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=width_mm * PT_PER_MM, height=height_mm * PT_PER_MM)
    y = 12
    while y < height_mm * PT_PER_MM - 8:
        page.insert_text((8, y), "Состав: витамин D3 2000 МЕ, ТР ТС 022/2011", fontsize=5)
        y += 8
    out = doc.tobytes()
    doc.close()
    return out


def raster_pdf(width_mm: float, height_mm: float, px_w: int, px_h: int) -> bytes:
    """A scan: one image stretched across a page of a known physical size."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=width_mm * PT_PER_MM, height=height_mm * PT_PER_MM)
    page.insert_image(page.rect, stream=jpg_bytes(_textured(px_w, px_h)))
    out = doc.tobytes()
    doc.close()
    return out


class TestGoodArtwork:
    def test_vector_pdf_is_excellent(self):
        rep = q.assess(vector_pdf(), filename="label.pdf")
        assert rep.ok is True
        assert rep.level == "excellent"
        assert rep.metrics["has_text_layer"] is True
        assert rep.score >= 90

    def test_vector_pdf_is_not_judged_on_sharpness(self):
        # We render it ourselves, so it cannot be blurry - no blur complaint allowed.
        rep = q.assess(vector_pdf(), filename="label.pdf")
        assert not any(p["code"] in ("BLURRY", "SOFT_FOCUS") for p in rep.problems)

    def test_high_res_scan_passes(self):
        # 100x50 mm at ~600 dpi.
        rep = q.assess(raster_pdf(100, 50, 2362, 1181), filename="scan.pdf")
        assert rep.ok is True
        assert rep.metrics["effective_px_per_mm"] >= q.THRESHOLDS["px_per_mm_min"]

    def test_large_jpg_with_print_dpi_passes(self):
        img = _textured(2400, 1200)
        rep = q.assess(jpg_bytes(img, dpi=(600, 600)), filename="label.jpg")
        assert rep.ok is True
        assert rep.metrics["declared_dpi"] == 600

    def test_large_jpg_without_dpi_passes_on_pixel_size(self):
        rep = q.assess(jpg_bytes(_textured(2400, 1200)), filename="label.jpg")
        assert rep.ok is True
        assert rep.metrics["effective_px_per_mm"] is None  # judged by pixels instead


class TestBadArtwork:
    def test_low_resolution_scan_is_blocked(self):
        # 100x50 mm carried by a 300x150 px image: ~76 dpi.
        rep = q.assess(raster_pdf(100, 50, 300, 150), filename="scan.pdf")
        assert rep.ok is False
        assert rep.level == "poor"
        assert any(p["code"] == "LOW_RESOLUTION" for p in rep.problems)

    def test_small_jpg_is_blocked(self):
        rep = q.assess(jpg_bytes(_textured(500, 250), dpi=(150, 150)), filename="label.jpg")
        assert rep.ok is False

    def test_tiny_jpg_without_dpi_is_blocked(self):
        rep = q.assess(jpg_bytes(_textured(800, 400)), filename="label.jpg")
        assert rep.ok is False
        assert any(p["code"] == "LOW_PIXEL_SIZE" for p in rep.problems)

    def test_blurred_image_is_blocked(self):
        blurred = _bold(2400, 1200).filter(ImageFilter.GaussianBlur(radius=4))
        rep = q.assess(jpg_bytes(blurred, dpi=(600, 600)), filename="label.jpg")
        assert rep.ok is False
        assert any(p["code"] == "BLURRY" for p in rep.problems)

    def test_blank_page_is_blocked_and_scores_near_zero(self):
        blank = Image.new("RGB", (2400, 1200), (253, 253, 253))
        rep = q.assess(jpg_bytes(blank, dpi=(600, 600)), filename="label.jpg")
        assert rep.ok is False
        assert any(p["code"] == "LOW_CONTRAST" for p in rep.problems)
        assert rep.score <= 10

    def test_blank_page_is_diagnosed_as_blank_not_as_blurred(self):
        # A blank page has no edges, so the sharpness metric also reads as "blurred".
        # The headline problem must still be the true one.
        blank = Image.new("RGB", (2400, 1200), (253, 253, 253))
        rep = q.assess(jpg_bytes(blank, dpi=(600, 600)), filename="label.jpg")
        assert rep.problems[0]["code"] == "LOW_CONTRAST"
        assert not any(p["code"] == "BLURRY" for p in rep.problems)

    def test_a_blurred_but_contrasty_label_is_still_called_blurred(self):
        blurred = _bold(2400, 1200).filter(ImageFilter.GaussianBlur(radius=4))
        rep = q.assess(jpg_bytes(blurred, dpi=(600, 600)), filename="label.jpg")
        assert rep.metrics["contrast"] > q.THRESHOLDS["contrast_min"]   # not blank
        assert rep.problems[0]["code"] == "BLURRY"
        assert rep.ok is False

    def test_blocking_report_converts_to_an_actionable_error(self):
        rep = q.assess(raster_pdf(100, 50, 300, 150), filename="scan.pdf")
        err = rep.as_error()
        assert isinstance(err, AppError)
        assert err.code == "MOCKUP_QUALITY_TOO_LOW"
        assert err.hint
        assert err.http_status == 422


class TestBrokenFiles:
    def test_empty_file(self):
        with pytest.raises(AppError) as e:
            q.assess(b"", filename="x.pdf")
        assert e.value.code == "FILE_EMPTY"

    def test_corrupt_pdf(self):
        with pytest.raises(AppError) as e:
            q.assess(b"%PDF-1.4 this is not really a pdf", filename="x.pdf")
        assert e.value.code == "FILE_UNREADABLE"

    def test_corrupt_image(self):
        with pytest.raises(AppError) as e:
            q.assess(b"\xff\xd8\xff not a jpeg at all", filename="x.jpg")
        assert e.value.code == "FILE_UNREADABLE"

    def test_content_wins_over_a_wrong_extension(self):
        # A JPEG named .pdf must be measured as an image, not opened as a document.
        rep = q.assess(jpg_bytes(_textured(2400, 1200)), filename="mislabelled.pdf")
        assert rep.metrics["kind"] == "image"


class TestMeasurementRules:
    def test_small_embedded_logo_does_not_condemn_a_vector_page(self):
        # Regression: a 64x64 logo on a vector layout used to be treated as the
        # resolution ceiling for the whole page, reporting ~20 dpi for good artwork.
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=100 * PT_PER_MM, height=50 * PT_PER_MM)
        page.insert_text((10, 20), "Состав: витамин D3", fontsize=6)
        page.insert_image(fitz.Rect(5, 5, 20, 20), stream=jpg_bytes(_textured(64, 64)))
        content = doc.tobytes()
        doc.close()

        rep = q.assess(content, filename="label.pdf")
        assert rep.ok is True
        assert rep.metrics["effective_px_per_mm"] > q.THRESHOLDS["px_per_mm_good"]

    def test_implausible_declared_dpi_is_ignored(self):
        # A 2400 px crop tagged 96 dpi is not a 63 cm label; fall back to pixels.
        rep = q.assess(jpg_bytes(_textured(2400, 1200), dpi=(96, 96)), filename="crop.png")
        assert rep.metrics["declared_dpi"] is None
        assert rep.metrics["declared_dpi_trusted"] is False
        assert rep.ok is True

    def test_thresholds_are_overridable(self):
        good = jpg_bytes(_textured(2400, 1200), dpi=(600, 600))
        assert q.assess(good, filename="a.jpg").ok is True
        strict = q.assess(good, filename="a.jpg", thresholds={"px_per_mm_min": 99.0})
        assert strict.ok is False

    def test_multipage_pdf_is_flagged(self):
        import fitz
        doc = fitz.open()
        for _ in range(5):
            page = doc.new_page(width=100 * PT_PER_MM, height=50 * PT_PER_MM)
            page.insert_text((10, 20), "Состав: витамин D3 2000 МЕ", fontsize=6)
        content = doc.tobytes()
        doc.close()

        rep = q.assess(content, filename="multi.pdf")
        assert any(p["code"] == "MANY_PAGES" for p in rep.problems)

    def test_report_is_json_serialisable(self):
        import json
        rep = q.assess(vector_pdf(), filename="label.pdf")
        json.dumps(rep.to_dict())  # stored as JSONB on check_tasks.quality

    def test_summary_is_in_russian_for_each_level(self):
        for content, name in [(vector_pdf(), "a.pdf"), (raster_pdf(100, 50, 300, 150), "b.pdf")]:
            rep = q.assess(content, filename=name)
            assert rep.summary
            assert q.LEVEL_LABELS[rep.level]
