"""Run on first deploy: python scripts/init_db.py"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alembic.config import Config
from alembic import command
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.core.config import settings
from app.models.users import User, UserRole
from app.models.references import DictionaryEntry, ChecklistRule, RuleCategory

INITIAL_DICTIONARY = [
    ("витамин C", "vitamins"), ("витамин D3", "vitamins"), ("витамин E", "vitamins"),
    ("витамин B12", "vitamins"), ("витамин B6", "vitamins"), ("витамин A", "vitamins"),
    ("фолиевая кислота", "vitamins"), ("биотин", "vitamins"), ("ниацин", "vitamins"),
    ("пантотеновая кислота", "vitamins"), ("рибофлавин", "vitamins"), ("тиамин", "vitamins"),
    ("цинк", "minerals"), ("магний", "minerals"), ("кальций", "minerals"),
    ("железо", "minerals"), ("селен", "minerals"), ("йод", "minerals"),
    ("хром", "minerals"), ("марганец", "minerals"), ("медь", "minerals"),
    ("калий", "minerals"), ("натрий", "minerals"), ("фосфор", "minerals"),
    ("коллаген", "ingredients"), ("L-карнитин", "ingredients"), ("коэнзим Q10", "ingredients"),
    ("омега-3", "ingredients"), ("лецитин", "ingredients"), ("инулин", "ingredients"),
    ("экстракт зелёного чая", "ingredients"), ("куркумин", "ingredients"),
    ("ресвератрол", "ingredients"), ("астаксантин", "ingredients"),
    ("мг", "units"), ("мкг", "units"), ("МЕ", "units"), ("г", "units"),
    ("мл", "units"), ("мкмоль", "units"), ("ммоль", "units"),
    ("INCI", "abbreviations"), ("БАД", "abbreviations"), ("ЕАС", "abbreviations"),
    ("ТР ТС", "abbreviations"), ("СГР", "abbreviations"), ("ТУ", "abbreviations"),
    ("ЕАЭС", "abbreviations"), ("ПЭН", "abbreviations"),
    ("Ascorbic acid", "inci"), ("Cholecalciferol", "inci"), ("Tocopherol", "inci"),
    ("Retinol acetate", "inci"), ("Zinc oxide", "inci"), ("Magnesium oxide", "inci"),
]

INITIAL_CHECKLIST_RULES = [
    ("tr_ts_product_name", "Наименование продукта присутствует на маркировке", RuleCategory.all),
    ("tr_ts_composition", "Состав продукта указан полностью", RuleCategory.all),
    ("tr_ts_net_weight", "Масса нетто / объём указаны", RuleCategory.all),
    ("tr_ts_manufacturer", "Наименование и адрес производителя указаны", RuleCategory.all),
    ("tr_ts_country_of_origin", "Страна происхождения указана", RuleCategory.all),
    ("tr_ts_date_of_manufacture", "Дата изготовления указана", RuleCategory.all),
    ("tr_ts_shelf_life", "Срок годности указан", RuleCategory.all),
    ("tr_ts_storage_conditions", "Условия хранения указаны", RuleCategory.all),
    ("tr_ts_eaeu_sign", "Знак обращения ЕАЭС (ЕАС) присутствует", RuleCategory.all),
    ("tr_ts_barcode", "Штрих-код присутствует", RuleCategory.all),
    ("tr_ts_mobius_loop", "Знак переработки (петля Мёбиуса) присутствует", RuleCategory.all),
    ("bad_disclaimer", "Фраза «БАД. Не является лекарственным средством» присутствует дословно", RuleCategory.bad),
    ("bad_sgr_number", "Номер и дата СГР указаны", RuleCategory.bad),
    ("bad_dosage_form", "Форма выпуска указана (капсулы, таблетки и т.д.)", RuleCategory.bad),
    ("bad_serving_size", "Рекомендуемая доза / способ применения указаны", RuleCategory.bad),
    ("font_size_min", "Размер шрифта обязательных реквизитов >= 2 мм", RuleCategory.all),
    ("text_contrast", "Контрастность текста к фону достаточна для читаемости", RuleCategory.all),
    ("mr_nutrient_format", "Формат указания нутриентов соответствует МР 2.3.1.0253-21", RuleCategory.bad),
]


async def run():
    print("Запуск миграций Alembic...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Миграции применены.")

    async with AsyncSessionLocal() as db:
        # Create admin
        admin_email = "admin@alina-pharma.ru"
        admin_pass = settings.INITIAL_ADMIN_PASSWORD
        existing = await db.execute(select(User).where(User.email == admin_email))
        if not existing.scalar_one_or_none():
            db.add(User(email=admin_email, password_hash=get_password_hash(admin_pass), role=UserRole.admin))
            print(f"Администратор {admin_email} создан. Пароль: {admin_pass}")
        else:
            print(f"Администратор {admin_email} уже существует.")

        # Seed dictionary
        for term, category in INITIAL_DICTIONARY:
            existing = await db.execute(select(DictionaryEntry).where(DictionaryEntry.term == term))
            if not existing.scalar_one_or_none():
                db.add(DictionaryEntry(term=term, category=category))
        print(f"Отраслевой словарь: добавлено {len(INITIAL_DICTIONARY)} терминов.")

        # Seed checklist
        for key, desc, cat in INITIAL_CHECKLIST_RULES:
            existing = await db.execute(select(ChecklistRule).where(ChecklistRule.rule_key == key))
            if not existing.scalar_one_or_none():
                db.add(ChecklistRule(rule_key=key, description=desc, category=cat))
        print(f"Нормативный чек-лист: добавлено {len(INITIAL_CHECKLIST_RULES)} правил.")

        await db.commit()
    print("Инициализация завершена.")


if __name__ == "__main__":
    asyncio.run(run())
