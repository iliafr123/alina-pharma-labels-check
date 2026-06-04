from app.pipeline.base import BaseLLMProvider


async def run_spelling_check(
    ocr_text: str,
    dictionary_terms: list[str],
    brand_whitelist: list[str],
    llm_provider: BaseLLMProvider,
) -> list[dict]:
    if not ocr_text.strip():
        return []
    result = await llm_provider.check_spelling(ocr_text, dictionary_terms, brand_whitelist)
    issues = result.get("issues", [])
    return [
        {
            "type": "warning" if i.get("type") in ("typography", "style") else "error",
            "module": "spelling",
            "description": i.get("text", ""),
            "suggestion": i.get("suggestion", ""),
            "bbox": None,
        }
        for i in issues
    ]
