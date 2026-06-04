from app.pipeline.base import BaseLLMProvider

ISSUE_TYPE_TO_SEVERITY = {
    "missing": "error",
    "mismatch": "error",
    "order_error": "warning",
    "format_variant": "warning",
}


async def run_pen_comparison(
    ocr_text: str,
    pen_fields: dict,
    llm_provider: BaseLLMProvider,
    category: str,
) -> list[dict]:
    if not ocr_text.strip() or not pen_fields:
        return []
    result = await llm_provider.compare_with_pen(ocr_text, pen_fields, category)
    issues = result.get("issues", [])
    return [
        {
            "type": ISSUE_TYPE_TO_SEVERITY.get(i.get("issue_type", "mismatch"), "error"),
            "module": "pen_comparison",
            "description": i.get("description", f"Расхождение в поле «{i.get('field', '')}»"),
            "suggestion": f"Ожидается: {i.get('expected', '')}",
            "bbox": None,
            "meta": {"field": i.get("field"), "expected": i.get("expected"), "found": i.get("found")},
        }
        for i in issues
    ]
