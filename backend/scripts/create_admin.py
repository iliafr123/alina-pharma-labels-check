"""Usage: python scripts/create_admin.py admin@example.com Password123!"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.users import User, UserRole


async def main(email: str, password: str):
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"Пользователь {email} уже существует")
            return
        user = User(email=email, password_hash=get_password_hash(password), role=UserRole.admin)
        db.add(user)
        await db.commit()
        print(f"Администратор {email} создан успешно")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python scripts/create_admin.py <email> <password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
