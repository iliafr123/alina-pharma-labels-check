from app.pipeline.base import BaseOCRProvider, BaseLLMProvider
from app.pipeline.providers.yandex_vision import YandexVisionProvider
from app.pipeline.providers.openai_provider import OpenAIVisionProvider, OpenAILLMProvider
from app.pipeline.providers.anthropic_provider import AnthropicLLMProvider, AnthropicVisionProvider
from app.pipeline.providers.gemini_provider import GeminiProvider
from app.pipeline.providers.grok_provider import GrokLLMProvider


def get_ocr_provider(provider_name: str, api_key: str) -> BaseOCRProvider:
    match provider_name:
        case "yandex_vision":
            return YandexVisionProvider(api_key)
        case "openai":
            return OpenAIVisionProvider(api_key)
        case "anthropic" | "anthropic_vision":
            return AnthropicVisionProvider(api_key)
        case "gemini":
            return GeminiProvider(api_key)
        case _:
            raise ValueError(f"Unknown OCR provider: {provider_name}")


def get_llm_provider(provider_name: str, api_key: str) -> BaseLLMProvider:
    match provider_name:
        case "openai":
            return OpenAILLMProvider(api_key)
        case "anthropic":
            return AnthropicLLMProvider(api_key)
        case "gemini":
            return GeminiProvider(api_key)
        case "grok":
            return GrokLLMProvider(api_key)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
