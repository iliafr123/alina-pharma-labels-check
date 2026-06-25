"""Dev-only DB bootstrap: create tables directly (no Alembic) + seed. Use with SQLite."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select, text
from app.core.database import engine, AsyncSessionLocal, Base
from app.core.security import get_password_hash
from app.core.config import settings
import app.models  # noqa: F401 — register all models on Base.metadata
from app.models.users import User, UserRole
from app.models.references import DictionaryEntry, ChecklistRule, RuleCategory
from scripts.init_db import INITIAL_DICTIONARY, INITIAL_CHECKLIST_RULES


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migrations for columns added after the table already existed (Postgres).
        for stmt in (
            "ALTER TABLE check_tasks ADD COLUMN IF NOT EXISTS reference_text TEXT",
            "ALTER TABLE check_tasks ADD COLUMN IF NOT EXISTS benchmark JSONB",
            "ALTER TABLE check_tasks ADD COLUMN IF NOT EXISTS focus_prompt TEXT",
            "ALTER TABLE check_tasks ADD COLUMN IF NOT EXISTS batch_id VARCHAR(64)",
            "ALTER TABLE check_tasks ADD COLUMN IF NOT EXISTS checklist JSONB",
        ):
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # SQLite / column already present
    print("Таблицы созданы (create_all) + миграции колонок.")

    async with AsyncSessionLocal() as db:
        admin_email = "admin@alina-pharma.ru"
        existing = await db.execute(select(User).where(User.email == admin_email))
        if not existing.scalar_one_or_none():
            db.add(User(email=admin_email, password_hash=get_password_hash(settings.INITIAL_ADMIN_PASSWORD), role=UserRole.admin))
            print(f"Администратор {admin_email} создан. Пароль: {settings.INITIAL_ADMIN_PASSWORD}")

        for term, category in INITIAL_DICTIONARY:
            existing = await db.execute(select(DictionaryEntry).where(DictionaryEntry.term == term))
            if not existing.scalar_one_or_none():
                db.add(DictionaryEntry(term=term, category=category))

        for key, desc, cat in INITIAL_CHECKLIST_RULES:
            existing = await db.execute(select(ChecklistRule).where(ChecklistRule.rule_key == key))
            if not existing.scalar_one_or_none():
                db.add(ChecklistRule(rule_key=key, description=desc, category=cat))

        await db.commit()
    print("Словарь и чек-лист загружены. Готово.")


if __name__ == "__main__":
    asyncio.run(run())
