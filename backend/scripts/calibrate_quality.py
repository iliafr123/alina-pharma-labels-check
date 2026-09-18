"""Calibration harness for the mockup-quality gate.

Run it over a folder of real label artwork to see where the measured metrics land,
and over synthetic degradations of those same files to see where OCR-breaking
quality sits. The thresholds in app/services/quality_service.py were chosen from
this output.

    python -m scripts.calibrate_quality "<folder with labels>"
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import quality_service as q  # noqa: E402

EXTS = (".pdf", ".jpg", ".jpeg", ".png")


def degrade(content: bytes, name: str):
    """Produce OCR-hostile variants of a real file: downscale, blur, JPEG-crush."""
    from PIL import Image, ImageFilter

    if name.lower().endswith(".pdf"):
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        pix = doc[0].get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()
    else:
        img = Image.open(io.BytesIO(content)).convert("RGB")

    out = []
    for factor in (0.5, 0.25, 0.12):
        w, h = img.size
        small = img.resize((max(1, int(w * factor)), max(1, int(h * factor))))
        b = io.BytesIO(); small.save(b, "JPEG", quality=85, dpi=(72, 72))
        out.append((f"downscale x{factor}", b.getvalue()))
    for radius in (1, 2, 4):
        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        b = io.BytesIO(); blurred.save(b, "JPEG", quality=90, dpi=(300, 300))
        out.append((f"blur r{radius}", b.getvalue()))
    for quality in (30, 12):
        b = io.BytesIO(); img.save(b, "JPEG", quality=quality, dpi=(300, 300))
        out.append((f"jpeg q{quality}", b.getvalue()))
    b = io.BytesIO(); Image.new("RGB", img.size, (252, 252, 252)).save(b, "JPEG", dpi=(300, 300))
    out.append(("blank page", b.getvalue()))
    return out


def row(tag: str, name: str, content: bytes):
    try:
        rep = q.assess(content, filename=name)
    except Exception as e:
        print(f"{tag:22} {name[:44]:44} ERROR {type(e).__name__}: {str(e)[:60]}")
        return
    m = rep.metrics
    ppm = m.get("effective_px_per_mm")
    print(f"{tag:22} {name[:44]:44} "
          f"level={rep.level:10} score={rep.score:3} "
          f"ppm={str(ppm):>6} dpi={str(m.get('effective_dpi')):>5} "
          f"sharp={m.get('sharpness'):.4f} contrast={m.get('contrast'):5.1f} "
          f"text_layer={str(m.get('has_text_layer')):5}")


def main(folder: str):
    files = []
    for root, _dirs, names in os.walk(folder):
        for n in names:
            if n.lower().endswith(EXTS):
                files.append(os.path.join(root, n))
    files.sort()
    print(f"# {len(files)} files under {folder}\n")

    print("== REAL ARTWORK (these all OCR'd correctly in production) ==")
    originals = []
    for path in files:
        with open(path, "rb") as f:
            content = f.read()
        originals.append((path, content))
        row("real", os.path.basename(path), content)

    print("\n== SYNTHETIC DEGRADATIONS ==")
    for path, content in originals[:6]:
        base = os.path.basename(path)
        for tag, degraded in degrade(content, base):
            row(tag, base, degraded)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
