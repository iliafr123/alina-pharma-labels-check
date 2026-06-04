import io
import fitz  # PyMuPDF


COLORS = {
    "error": (0.9, 0.1, 0.1),
    "warning": (1.0, 0.7, 0.0),
    "info": (0.1, 0.7, 0.1),
}


def generate_annotated_pdf(original_pdf_bytes: bytes, all_issues: list[dict]) -> bytes:
    doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")

    for issue in all_issues:
        bbox = issue.get("bbox")
        if not bbox:
            continue
        page_num = bbox.get("page", 0)
        if page_num >= len(doc):
            continue
        page = doc[page_num]
        rect = fitz.Rect(
            bbox.get("x", 0),
            bbox.get("y", 0),
            bbox.get("x", 0) + bbox.get("w", 50),
            bbox.get("y", 0) + bbox.get("h", 12),
        )
        color = COLORS.get(issue.get("type", "warning"), COLORS["warning"])
        page.draw_rect(rect, color=color, fill=color, fill_opacity=0.25, width=1.5)
        desc = issue.get("description", "")[:60]
        page.insert_text(
            fitz.Point(rect.x0, rect.y0 - 2),
            desc,
            fontsize=6,
            color=color,
        )

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
