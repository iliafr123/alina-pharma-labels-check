from app.pipeline.base import BaseLLMProvider


async def run_regulatory_check(
    ocr_text: str,
    image_bytes: bytes,
    category: str,
    checklist_rules: list[dict],
    llm_provider: BaseLLMProvider,
) -> list[dict]:
    issues = []

    # Text-based regulatory check
    if ocr_text.strip():
        result = await llm_provider.check_regulatory(ocr_text, category, checklist_rules)
        for i in result.get("issues", []):
            if i.get("status") in ("fail", "warn"):
                issues.append({
                    "type": "error" if i.get("status") == "fail" else "warning",
                    "module": "regulatory",
                    "description": i.get("description", ""),
                    "suggestion": "",
                    "bbox": None,
                    "meta": {"rule_key": i.get("rule_key")},
                })

    # Layout analysis (font size, contrast, visual elements)
    if image_bytes:
        layout_result = await llm_provider.analyze_layout(image_bytes, category)
        for i in layout_result.get("issues", []):
            if i.get("status") in ("fail", "warn"):
                issues.append({
                    "type": "error" if i.get("status") == "fail" else "warning",
                    "module": "layout",
                    "description": i.get("description", ""),
                    "suggestion": "",
                    "bbox": None,
                    "meta": {"element": i.get("element")},
                })

    return issues
