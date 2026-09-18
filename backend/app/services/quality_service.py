"""Is this mockup good enough for OCR?

The gate measures the image *as the pipeline will actually see it* - rendered at
RENDER_DPI, white margins cropped, long side capped at MAX_SIDE_PX (see
app/workers/tasks.py) - because that, not the raw file, is what the vision model
reads.

The decisive number is `effective_px_per_mm`: rendered pixels per millimetre of
real artwork. It is bounded by the weakest link:

  * vector / text-layer PDF -> limited only by our own render DPI and the 2400 px
    cap, so it is always sharp;
  * scanned or image-only PDF -> limited by the resolution of the embedded image,
    since rendering a 72 dpi scan at 340 dpi only upsamples blur;
  * JPG -> limited by its pixel size (and its EXIF DPI when the file declares one).

Thresholds (see THRESHOLDS below) come from the calibration run in
scripts/calibrate_quality.py over the 19 real label files in the Алина Фарма test
corpus - all of which the pipeline OCR'd correctly - plus synthetic degradations
of them (downscale, Gaussian blur, JPEG crush, blank page).

Resolution, `effective_px_per_mm`:

  >= 12 px/mm (~305 dpi)  excellent - the smallest legal marking text (1.2 mm cap
                          height per ТР ТС 022/2011) lands on ~14 px, which is
                          the region where vision OCR is reliable;
  >=  8 px/mm (~203 dpi)  acceptable - readable, but small print may be misread;
  <   8 px/mm             blocked - OCR output cannot be trusted.

  Measured floor of the real corpus: 8.2 px/mm. Every downscaled variant landed
  at 1.9-3.9 px/mm, so the 8.0 line separates the two populations cleanly.

Sharpness (raster sources only - a vector PDF is rendered by us and is sharp by
construction):

  >= 0.120  excellent      real corpus range: 0.145 - 0.429
  >= 0.035  acceptable     Gaussian blur r1-r2: 0.021 - 0.089
  <  0.035  blocked        Gaussian blur r4: 0.004 - 0.010 (unreadable)

  The 0.035 line sits ~4x below the worst real file, so a genuine label is not
  going to trip it.

Known limitation: heavy JPEG compression (quality <= 30) is NOT detected - block
artefacts add high-frequency energy, so the sharpness metric stays high. The gate
catches low resolution, blur and blank pages; it does not catch over-compression.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field, asdict

from app.core.errors import AppError

# Must stay in sync with the rendering in app/workers/tasks.py.
RENDER_DPI = 340
MAX_SIDE_PX = 2400
PT_PER_MM = 72.0 / 25.4

# An embedded image must cover at least this share of the page before its own
# resolution is treated as the ceiling for the whole page.
COVER_FRACTION = 0.40

# A declared DPI is only believed when it is a printing resolution AND implies a
# label-sized object. Export tools stamp 96 dpi on large crops, which would
# otherwise "prove" the label is 80 cm wide and pass/fail for the wrong reason.
TRUSTED_DPI_RANGE = (150.0, 1200.0)
PLAUSIBLE_LABEL_MM = (20.0, 600.0)

# Defaults; each is overridable from the admin panel (system_config key in brackets).
THRESHOLDS = {
    "px_per_mm_good": 12.0,      # [quality_px_per_mm_good]
    "px_per_mm_min": 8.0,        # [quality_px_per_mm_min]
    "sharpness_good": 0.120,     # [quality_sharpness_good]
    "sharpness_min": 0.035,      # [quality_sharpness_min]
    "contrast_min": 12.0,        # [quality_contrast_min]  flat/blank page guard
    "jpg_side_good": 2000,       # [quality_jpg_side_good] used when no physical size is known
    "jpg_side_min": 1200,        # [quality_jpg_side_min]
    "max_pages": 3,              # pipeline only OCRs the first N pages
}

LEVEL_LABELS = {
    "excellent": "отличное",
    "acceptable": "приемлемое",
    "poor": "недостаточное",
}


@dataclass
class QualityReport:
    ok: bool                       # False -> refuse to run the check
    level: str                     # excellent | acceptable | poor
    score: int                     # 0..100, for the progress bar
    summary: str                   # one Russian line for the user
    metrics: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)   # [{code, message, hint}]
    advice: list = field(default_factory=list)     # what to send instead

    def to_dict(self) -> dict:
        return asdict(self)

    def as_error(self) -> AppError:
        first = self.problems[0] if self.problems else {}
        return AppError(
            "MOCKUP_QUALITY_TOO_LOW",
            first.get("message") or "Качество макета недостаточно для распознавания текста.",
            first.get("hint") or "; ".join(self.advice) or
            "Загрузите исходный PDF из редактора (векторный) или скан не ниже 300 dpi.",
            detail=f"metrics={self.metrics}",
            subsystem="file", stage="ocr", http_status=422,
            context={"quality": self.to_dict()},
        )


async def load_thresholds(db) -> dict:
    """Admin-panel overrides on top of the defaults."""
    from app.services import config_service
    out = dict(THRESHOLDS)
    for name in out:
        raw = await config_service.get_config(db, f"quality_{name}")
        if raw:
            try:
                out[name] = type(THRESHOLDS[name])(float(raw))
            except Exception:
                pass
    return out


# --- low-level image measurements -------------------------------------------
def _grayscale_stats(img) -> tuple[float, float]:
    """(contrast, sharpness) for a PIL image.

    sharpness = RMS of (image - its own 1px blur) normalised by the image's own
    contrast. Normalising by contrast keeps a pale label from scoring as "blurry"
    purely because it is low-contrast.

    Measured on the image at the size OCR will receive it - deliberately not on a
    normalised thumbnail. Downscaling to a fixed width before measuring undoes the
    very blur we are looking for: a 3000 px scan with a 4 px blur looks crisp once
    shrunk to 1000 px, but the model still reads it at 2400 px, where it is a smear.
    """
    from PIL import ImageFilter, ImageChops, ImageStat

    g = img.convert("L")
    contrast = ImageStat.Stat(g).stddev[0]
    blurred = g.filter(ImageFilter.GaussianBlur(radius=1))
    diff = ImageChops.difference(g, blurred)
    rms = ImageStat.Stat(diff).rms[0]
    sharpness = rms / contrast if contrast > 1e-6 else 0.0
    return contrast, sharpness


def _crop_margins(img):
    """Same whitespace crop the pipeline does before OCR."""
    from PIL import Image, ImageChops
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bbox = ImageChops.difference(img.convert("RGB"), bg).getbbox()
    return img.crop(bbox) if bbox else img


# --- PDF ---------------------------------------------------------------------
def _assess_pdf(content: bytes, th: dict) -> dict:
    import fitz
    from PIL import Image

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as e:
        raise AppError("FILE_UNREADABLE", "Не удалось открыть PDF-файл.",
                       "Файл повреждён, зашифрован или это не PDF. "
                       "Пересохраните макет из редактора и загрузите заново.",
                       str(e), subsystem="file", http_status=422)

    if doc.page_count == 0:
        doc.close()
        raise AppError("FILE_EMPTY", "PDF не содержит ни одной страницы.",
                       "Загрузите корректный файл макета.", subsystem="file", http_status=422)

    pages = min(doc.page_count, int(th["max_pages"]))
    per_page = []
    try:
        for pno in range(pages):
            page = doc[pno]
            rect = page.rect
            page_w_mm = rect.width / PT_PER_MM
            page_h_mm = rect.height / PT_PER_MM
            text_layer_chars = len((page.get_text("text") or "").strip())
            has_text_layer = text_layer_chars >= 40

            # Resolution actually available from embedded raster images. Only images
            # that actually cover the page bound the artwork's resolution - a small
            # logo or barcode placed on a vector layout says nothing about the text,
            # so measure each image against the rectangle it is really drawn into.
            source_px_per_mm = None
            page_area = float(rect.width * rect.height) or 1.0
            try:
                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    info = doc.extract_image(xref)
                    iw, ih = info.get("width", 0), info.get("height", 0)
                    if not iw or not ih:
                        continue
                    for r in page.get_image_rects(xref) or []:
                        if r.width <= 0 or r.height <= 0:
                            continue
                        if (r.width * r.height) / page_area < COVER_FRACTION:
                            continue  # decorative element, not the artwork itself
                        rw_mm = r.width / PT_PER_MM
                        rh_mm = r.height / PT_PER_MM
                        if rw_mm <= 0 or rh_mm <= 0:
                            continue
                        ppm = min(iw / rw_mm, ih / rh_mm)  # the weaker axis is the limit
                        source_px_per_mm = max(source_px_per_mm or 0.0, ppm)
            except Exception:
                pass

            # Render exactly like the pipeline, then crop + cap.
            pix = page.get_pixmap(dpi=RENDER_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            pix = None
            render_scale = RENDER_DPI / 72.0        # px per pt
            cropped = _crop_margins(img)
            cw, ch = cropped.size
            art_w_mm = (cw / render_scale) / PT_PER_MM
            art_h_mm = (ch / render_scale) / PT_PER_MM
            long_px = max(cw, ch)
            cap_scale = MAX_SIDE_PX / long_px if long_px > MAX_SIDE_PX else 1.0
            final_w, final_h = int(cw * cap_scale), int(ch * cap_scale)
            if cap_scale < 1.0:
                cropped = cropped.resize((max(1, final_w), max(1, final_h)))

            art_long_mm = max(art_w_mm, art_h_mm) or 1e-6
            render_px_per_mm = max(final_w, final_h) / art_long_mm

            if has_text_layer:
                effective = render_px_per_mm     # vector text: render as sharp as we like
            elif source_px_per_mm:
                effective = min(render_px_per_mm, source_px_per_mm)
            else:
                effective = render_px_per_mm

            contrast, sharpness = _grayscale_stats(cropped)
            per_page.append({
                "page": pno + 1,
                "page_mm": [round(page_w_mm, 1), round(page_h_mm, 1)],
                "artwork_mm": [round(art_w_mm, 1), round(art_h_mm, 1)],
                "render_px": [final_w, final_h],
                "has_text_layer": has_text_layer,
                "text_layer_chars": text_layer_chars,
                "source_px_per_mm": round(source_px_per_mm, 1) if source_px_per_mm else None,
                "effective_px_per_mm": round(effective, 1),
                "contrast": round(contrast, 1),
                "sharpness": round(sharpness, 4),
            })
    finally:
        total_pages = doc.page_count
        doc.close()

    worst = min(per_page, key=lambda p: p["effective_px_per_mm"])
    return {
        "kind": "pdf",
        "total_pages": total_pages,
        "pages_analyzed": len(per_page),
        "has_text_layer": any(p["has_text_layer"] for p in per_page),
        "effective_px_per_mm": worst["effective_px_per_mm"],
        "effective_dpi": round(worst["effective_px_per_mm"] * 25.4),
        "sharpness": min(p["sharpness"] for p in per_page),
        "contrast": min(p["contrast"] for p in per_page),
        "artwork_mm": worst["artwork_mm"],
        "pages": per_page,
    }


# --- JPG ---------------------------------------------------------------------
def _assess_image(content: bytes, th: dict) -> dict:
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(content))
        img.load()
    except Exception as e:
        raise AppError("FILE_UNREADABLE", "Не удалось открыть изображение.",
                       "Файл повреждён или это не JPG/PNG. Пересохраните и загрузите заново.",
                       str(e), subsystem="file", http_status=422)

    raw_dpi = None
    try:
        dpi = img.info.get("dpi")
        if dpi and dpi[0]:
            raw_dpi = float(dpi[0])
    except Exception:
        pass

    cropped = _crop_margins(img.convert("RGB"))
    cw, ch = cropped.size
    long_px = max(cw, ch)
    if long_px > MAX_SIDE_PX:
        s = MAX_SIDE_PX / long_px
        cropped = cropped.resize((max(1, int(cw * s)), max(1, int(ch * s))))
    fw, fh = cropped.size

    # Believe the file's DPI only if it is a print resolution implying a label-sized
    # object; otherwise judge the image by its pixel count alone (see TRUSTED_DPI_RANGE).
    declared_dpi = None
    effective = None
    artwork_mm = None
    if raw_dpi and TRUSTED_DPI_RANGE[0] <= raw_dpi <= TRUSTED_DPI_RANGE[1]:
        implied_long_mm = (max(cw, ch) / raw_dpi) * 25.4
        if PLAUSIBLE_LABEL_MM[0] <= implied_long_mm <= PLAUSIBLE_LABEL_MM[1]:
            declared_dpi = raw_dpi
            artwork_mm = [round((cw / raw_dpi) * 25.4, 1), round((ch / raw_dpi) * 25.4, 1)]
            effective = max(fw, fh) / implied_long_mm if implied_long_mm else None

    contrast, sharpness = _grayscale_stats(cropped)
    return {
        "kind": "image",
        "total_pages": 1,
        "pages_analyzed": 1,
        "has_text_layer": False,
        "declared_dpi": declared_dpi,
        "declared_dpi_raw": raw_dpi,
        "declared_dpi_trusted": declared_dpi is not None,
        "pixels": [cw, ch],
        "render_px": [fw, fh],
        "long_side_px": max(cw, ch),
        "effective_px_per_mm": round(effective, 1) if effective else None,
        "effective_dpi": round(effective * 25.4) if effective else None,
        "artwork_mm": artwork_mm,
        "sharpness": round(sharpness, 4),
        "contrast": round(contrast, 1),
    }


# --- verdict -----------------------------------------------------------------
def _verdict(m: dict, th: dict) -> QualityReport:
    problems: list[dict] = []
    advice: list[str] = []
    levels: list[str] = []

    ppm = m.get("effective_px_per_mm")
    if ppm is not None:
        dpi = round(ppm * 25.4)
        if ppm < th["px_per_mm_min"]:
            levels.append("poor")
            problems.append({
                "code": "LOW_RESOLUTION",
                "message": f"Низкое разрешение макета: {ppm} пикс/мм (~{dpi} dpi). "
                           f"Для надёжного распознавания нужно не меньше "
                           f"{th['px_per_mm_min']:.0f} пикс/мм (~{round(th['px_per_mm_min'] * 25.4)} dpi).",
                "hint": "Мелкий обязательный текст (состав, сроки, ТР ТС) в таком разрешении "
                        "читается неверно — часть строк будет пропущена или искажена.",
            })
            advice.append("выгрузите исходный PDF из редактора (векторный, не растр) "
                          "или пересканируйте макет на 300–600 dpi")
        elif ppm < th["px_per_mm_good"]:
            levels.append("acceptable")
            problems.append({
                "code": "MODERATE_RESOLUTION",
                "message": f"Разрешение на границе нормы: {ppm} пикс/мм (~{dpi} dpi).",
                "hint": "Крупный текст распознается, мелкий шрифт (менее 1,5 мм) может быть прочитан с ошибками.",
            })
        else:
            levels.append("excellent")
    elif m["kind"] == "image":
        # No physical size in the file - fall back to absolute pixel size.
        side = m.get("long_side_px") or 0
        if side < th["jpg_side_min"]:
            levels.append("poor")
            problems.append({
                "code": "LOW_PIXEL_SIZE",
                "message": f"Изображение слишком маленькое: {side} пикс по длинной стороне "
                           f"(минимум {int(th['jpg_side_min'])}).",
                "hint": "В файле не указано физическое разрешение (dpi), поэтому оценка по размеру в пикселях.",
            })
            advice.append(f"пришлите изображение не меньше {int(th['jpg_side_good'])} пикс "
                          f"по длинной стороне, лучше — исходный PDF")
        elif side < th["jpg_side_good"]:
            levels.append("acceptable")
            problems.append({
                "code": "MODERATE_PIXEL_SIZE",
                "message": f"Размер изображения на границе нормы: {side} пикс по длинной стороне.",
                "hint": f"Рекомендуется не меньше {int(th['jpg_side_good'])} пикс.",
            })
        else:
            levels.append("excellent")

    # Sharpness/contrast only mean something for raster sources: a vector PDF is
    # rendered by us and is sharp by construction.
    if not m.get("has_text_layer"):
        contrast = m.get("contrast")
        blank = contrast is not None and contrast < th["contrast_min"]
        # Checked first: a blank page has no edges, so the sharpness metric reads as
        # "blurred" and would otherwise headline the report with the wrong diagnosis.
        if blank:
            levels.append("poor")
            problems.append({
                "code": "LOW_CONTRAST",
                "message": f"Почти однотонное изображение (контраст {contrast:.1f}).",
                "hint": "Похоже на пустую страницу, заливку или очень бледный макет — "
                        "распознавать нечего.",
            })
            advice.append("проверьте, что загружен именно макет этикетки, а не пустая страница")

        sharp = m.get("sharpness")
        if sharp is not None and not blank:
            if sharp < th["sharpness_min"]:
                levels.append("poor")
                problems.append({
                    "code": "BLURRY",
                    "message": f"Изображение размыто или сильно сжато (резкость {sharp:.3f} "
                               f"при минимуме {th['sharpness_min']:.3f}).",
                    "hint": "Так выглядят фотографии макета, скриншоты и JPG с сильным сжатием — "
                            "буквы «плывут», и OCR читает их неверно.",
                })
                advice.append("не фотографируйте макет и не пересжимайте JPG — "
                              "выгрузите файл напрямую из редактора")
            elif sharp < th["sharpness_good"]:
                levels.append("acceptable")
                problems.append({
                    "code": "SOFT_FOCUS",
                    "message": f"Невысокая резкость ({sharp:.3f}).",
                    "hint": "Мелкий текст может распознаться с ошибками.",
                })

    if m.get("total_pages", 1) > th["max_pages"]:
        problems.append({
            "code": "MANY_PAGES",
            "message": f"В файле {m['total_pages']} страниц — проверяются только первые "
                       f"{int(th['max_pages'])}.",
            "hint": "Разделите многостраничный файл, если проверить нужно все этикетки.",
        })

    level = "poor" if "poor" in levels else ("acceptable" if "acceptable" in levels else "excellent")
    ok = level != "poor"

    # Score: resolution is the dominant term, sharpness modulates it.
    if ppm:
        res_score = min(1.0, ppm / th["px_per_mm_good"])
    elif m["kind"] == "image":
        res_score = min(1.0, (m.get("long_side_px") or 0) / th["jpg_side_good"])
    else:
        res_score = 1.0
    sharp_score = 1.0 if m.get("has_text_layer") else min(
        1.0, (m.get("sharpness") or 0) / th["sharpness_good"])
    score = int(round(100 * (0.7 * res_score + 0.3 * sharp_score)))
    # A page can be perfectly sized and still be unusable (blank, or a blurred
    # smear), so a blocking problem must pull the score down with it.
    if any(p["code"] == "LOW_CONTRAST" for p in problems):
        score = min(score, 5)
    elif not ok:
        score = min(score, 45)
    score = max(0, min(100, score))

    if level == "excellent":
        summary = "Качество макета отличное — распознавание пройдёт без потерь."
    elif level == "acceptable":
        summary = "Качество макета приемлемое — проверка запустится, но мелкий текст может быть распознан с ошибками."
    else:
        summary = "Качество макета недостаточно для распознавания — проверка не будет запущена."

    return QualityReport(ok=ok, level=level, score=score, summary=summary,
                         metrics=m, problems=problems, advice=advice)


def assess(content: bytes, filename: str = "", content_type: str = "",
           thresholds: dict | None = None) -> QualityReport:
    """Entry point. Raises AppError for unreadable/empty files, otherwise returns a report."""
    th = {**THRESHOLDS, **(thresholds or {})}
    if not content:
        raise AppError("FILE_EMPTY", "Файл пуст.", "Загрузите файл макета заново.",
                       subsystem="file", http_status=422)

    # Sniff the content first: a mislabelled file must be measured for what it is,
    # not for what its name claims (fitz will happily open a JPEG as a "document").
    name = (filename or "").lower()
    if content[:5] == b"%PDF-":
        is_pdf = True
    elif content[:3] == b"\xff\xd8\xff" or content[:8] == b"\x89PNG\r\n\x1a\n":
        is_pdf = False
    else:
        is_pdf = name.endswith(".pdf") or "pdf" in (content_type or "")
    metrics = _assess_pdf(content, th) if is_pdf else _assess_image(content, th)
    return _verdict(metrics, th)
