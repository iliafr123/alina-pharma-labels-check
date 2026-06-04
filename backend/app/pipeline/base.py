from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TextBlock:
    text: str
    bbox: dict  # {"x": float, "y": float, "w": float, "h": float, "page": int}
    confidence: float = 1.0


@dataclass
class OCRResult:
    blocks: list[TextBlock] = field(default_factory=list)
    full_text: str = ""
    language: str = "ru"
    pages: int = 1


class BaseOCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass


class BaseLLMProvider(ABC):
    @abstractmethod
    async def check_spelling(self, text: str, dictionary_terms: list[str], brand_whitelist: list[str]) -> dict:
        pass

    @abstractmethod
    async def compare_with_pen(self, ocr_text: str, pen_fields: dict, category: str) -> dict:
        pass

    @abstractmethod
    async def check_regulatory(self, ocr_text: str, category: str, checklist_rules: list[dict]) -> dict:
        pass

    @abstractmethod
    async def analyze_layout(self, image_bytes: bytes, category: str) -> dict:
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
