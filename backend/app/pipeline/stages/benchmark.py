from app.pipeline.base import BaseLLMProvider


async def run_benchmark(reference_text: str, issues: list[dict], llm_provider: BaseLLMProvider) -> dict | None:
    """Compare system-found issues against a manual-review reference. Returns a verdict dict or None."""
    if not reference_text or not reference_text.strip():
        return None
    compare = getattr(llm_provider, "compare_benchmark", None)
    if compare is None:
        return {"matched": None, "summary": "Сравнение не поддерживается выбранным провайдером.",
                "missing": [], "extra": []}
    try:
        v = await compare(reference_text, issues) or {}
    except Exception as e:
        return {"matched": None, "summary": f"Не удалось выполнить сравнение: {str(e)[:150]}",
                "missing": [], "extra": []}
    return {
        "matched": bool(v.get("matched")) if v.get("matched") is not None else None,
        "summary": v.get("summary", ""),
        "missing": v.get("missing", []) or [],
        "extra": v.get("extra", []) or [],
    }
