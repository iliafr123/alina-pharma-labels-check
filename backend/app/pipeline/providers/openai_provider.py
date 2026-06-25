import base64
import json
import httpx
from app.pipeline.base import BaseOCRProvider, BaseLLMProvider, OCRResult, TextBlock

_RU_ONLY = "\nКРИТИЧЕСКИ ВАЖНО: весь текст в ответе (description, suggestion, summary и любые пояснения) — СТРОГО на русском языке. Английский в ответе недопустим."

SPELLING_SYSTEM = """Ты эксперт по русскому языку и маркировке пищевых продуктов и БАД.
Проверь текст на орфографические ошибки, пунктуацию и типографику.
Игнорируй слова из предоставленного словаря и список брендов.
Верни JSON: {"issues": [{"text": "...", "suggestion": "...", "type": "spelling|punctuation|typography|style"}]}""" + _RU_ONLY

PEN_SYSTEM = """Ты эксперт по маркировке БАД и пищевых продуктов в России и ЕАЭС.
Сравни текст макета этикетки с эталонным документом ПЭН (по полям).
Толерантное сравнение: игнорируй регистр и лишние пробелы, НО сигнализируй о вариантах написания чисел, единиц измерения и порядке состава.
Верни JSON: {"issues": [{"field": "...", "expected": "...", "found": "...", "issue_type": "missing|mismatch|order_error|format_variant", "description": "..."}]}""" + _RU_ONLY

REGULATORY_SYSTEM = """Ты эксперт по нормативным требованиям к маркировке БАД и пищевых продуктов (ТР ТС 022/2011, МР 2.3.1.0253-21, ЕАЭС).
Проверь текст макета по предоставленному чек-листу.
Верни JSON: {"issues": [{"rule_key": "...", "description": "...", "status": "ok|fail|warn"}]}""" + _RU_ONLY

LAYOUT_SYSTEM = """Ты эксперт по дизайну этикеток. Проанализируй изображение макета.
Проверь: размер шрифта (обязательные реквизиты >= 2 мм), контрастность текста, наличие знака ЕАЭС (ЕАС), штрих-кода, петли Мёбиуса.
Верни JSON: {"issues": [{"element": "...", "description": "...", "status": "ok|fail|warn"}]}""" + _RU_ONLY

BENCHMARK_SYSTEM = """Ты сравниваешь результаты автоматической проверки макета этикетки с эталоном — результатами ручной проверки специалиста.
Дан текст ручной проверки (эталонные замечания) и список замечаний, найденных системой.
Определи, покрывает ли система существенные замечания из ручной проверки.
Верни JSON: {"matched": true|false, "summary": "краткий вывод на русском", "missing": ["существенные замечания из ручной проверки, которые система НЕ нашла"], "extra": ["замечания системы, которых нет в ручной проверке"]}.
matched=true только если система выявила все существенные замечания ручной проверки (дополнительные системные замечания допустимы и не влияют на matched).""" + _RU_ONLY


# Canonical mandatory marking elements (доп. требования) — the checklist verdict covers ALL of these.
CHECKLIST_ITEMS = [
    "Наименование продукции", "Номер нормативного документа (ТУ)", "Номер и дата получения СГР", "Состав",
    "Количество товара", "Количество содержания активного вещества в суточной дозе",
    "Форма выпуска / количество в 1 единице", "Показатели пищевой ценности", "Область применения БАД",
    "Рекомендации и (или) ограничения по использованию", "Продолжительность приёма БАД", "Противопоказания",
    "Дата изготовления / партия (серия) / годен до", "Срок годности", "Условия хранения",
    "Юридический адрес производителя. Адрес производства",
    "Наименование, адрес, контакты организации, принимающей претензии от потребителей",
    "Штрих-код", "Пиктограммы (петля Мёбиуса)", "Знак обращения на рынке — ЕАС",
    "Фраза «БАД. Не является лекарственным средством»",
    "Информация о компонентах-аллергенах / противопоказаниях при заболеваниях", "Размер шрифта — не менее 2 мм",
]

CHECKLIST_SYSTEM = """Ты эксперт по маркировке БАД (ТР ТС 022/2011, ТР ТС 021/2011, МР 2.3.1.0253-21, требования ЕАЭС).
Дан распознанный текст макета этикетки и эталонный документ ПЭН (проект этикеточной надписи).
Проверь НАЛИЧИЕ и КОРРЕКТНОСТЬ КАЖДОГО обязательного элемента из списка (присутствует ли, корректен ли, совпадает ли с ПЭН).
Для КАЖДОГО элемента верни статус: "ok" (присутствует и корректен), "fail" (отсутствует / ошибка / расхождение с ПЭН или нормами), "na" (неприменимо).
Обязательно верни ВСЕ пункты из списка в том же порядке, ничего не пропуская.
Верни JSON: {"checklist": [{"item": "<точное название пункта>", "status": "ok|fail|na", "explanation": "<кратко: что проверено и в чём расхождение>"}]}"""


def _checklist_user(ocr_text: str, pen_fields: dict, items: list) -> str:
    nums = "\n".join(f"{i}. {it}" for i, it in enumerate(items, 1))
    return (f"Обязательные элементы (проверь каждый):\n{nums}\n\n"
            f"Эталон ПЭН:\n{json.dumps(pen_fields, ensure_ascii=False)[:6000]}\n\n"
            f"Распознанный текст макета:\n{ocr_text[:8000]}")


def _benchmark_user(reference_text: str, issues: list) -> str:
    return (f"Ручная проверка (эталон):\n{reference_text[:8000]}\n\n"
            f"Замечания системы:\n{json.dumps(issues, ensure_ascii=False)[:8000]}")


class OpenAIVisionProvider(BaseOCRProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def extract_text(self, image_bytes: bytes, hint_lang: str = "ru") -> OCRResult:
        encoded = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Извлеки весь текст с этого изображения. Язык: {hint_lang}. Верни только текст, без пояснений."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ],
            }],
            "max_tokens": 8192,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
        block = TextBlock(text=text, bbox={"x": 0, "y": 0, "w": 0, "h": 0, "page": 0})
        return OCRResult(blocks=[block], full_text=text)

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {self._api_key}"})
            resp.raise_for_status()
            return True


class OpenAILLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://api.openai.com/v1"

    @property
    def provider_name(self) -> str:
        return "openai"

    async def _chat(self, system: str, user: str) -> dict:
        if getattr(self, "_focus", ""):
            system = f"ОСОБЫЙ ФОКУС ПРОВЕРКИ (высокий приоритет): {self._focus}\n\n" + system
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": self._model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "response_format": {"type": "json_object"}, "max_tokens": 8192},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])

    async def check_spelling(self, text: str, dictionary_terms: list[str], brand_whitelist: list[str]) -> dict:
        user = f"Словарь: {', '.join(dictionary_terms[:100])}\nБренды: {', '.join(brand_whitelist[:50])}\n\nТекст:\n{text[:8000]}"
        return await self._chat(SPELLING_SYSTEM, user)

    async def compare_benchmark(self, reference_text: str, issues: list) -> dict:
        return await self._chat(BENCHMARK_SYSTEM, _benchmark_user(reference_text, issues))

    async def build_checklist(self, ocr_text: str, pen_fields: dict, items: list) -> dict:
        return await self._chat(CHECKLIST_SYSTEM, _checklist_user(ocr_text, pen_fields, items))

    async def compare_with_pen(self, ocr_text: str, pen_fields: dict, category: str) -> dict:
        user = f"Категория: {category}\nПЭН:\n{json.dumps(pen_fields, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}"
        return await self._chat(PEN_SYSTEM, user)

    async def check_regulatory(self, ocr_text: str, category: str, checklist_rules: list[dict]) -> dict:
        user = f"Категория: {category}\nЧек-лист:\n{json.dumps(checklist_rules, ensure_ascii=False)}\n\nТекст макета:\n{ocr_text[:8000]}"
        return await self._chat(REGULATORY_SYSTEM, user)

    async def analyze_layout(self, image_bytes: bytes, category: str) -> dict:
        encoded = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": LAYOUT_SYSTEM}, {"role": "user", "content": [
                {"type": "text", "text": f"Категория продукта: {category}. Проанализируй макет."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ]}],
            "response_format": {"type": "json_object"}, "max_tokens": 2048,
        }
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {self._api_key}"})
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])

    async def test_connection(self) -> bool:
        # Surface real errors; uses self._base_url so Grok (api.x.ai) works without overriding.
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/models", headers={"Authorization": f"Bearer {self._api_key}"})
            resp.raise_for_status()
            return True
