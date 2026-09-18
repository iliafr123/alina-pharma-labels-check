"""Test harness: a throwaway SQLite database, an ASGI client, and ready-made tokens.

Everything runs without Postgres, Redis, S3 or any provider key, so the suite can
be the gate that runs before every deploy.
"""
import asyncio
import os
import uuid

# Must be set before anything imports app.core.config (the engine is built at import).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_alina.db"
os.environ["CELERY_EAGER"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dGVzLXg=")
os.environ.setdefault("S3_ACCESS_KEY", "")
os.environ.setdefault("S3_SECRET_KEY", "")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

import app.models  # noqa: E402,F401  - registers every table on Base.metadata
from app.core.database import Base, engine, AsyncSessionLocal  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models.users import User, UserRole  # noqa: E402
# Imported last and bound to a distinct name: `import app.models` above rebinds the
# bare name `app` to the package, which would shadow the FastAPI instance.
from app.main import app as fastapi_app  # noqa: E402


ADMIN_EMAIL = "admin@test.local"
SPECIALIST_EMAIL = "spec@test.local"
PASSWORD = "TestPass123!"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_db():
    """A fresh schema per test - no ordering dependencies between tests."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        db.add(User(id=uuid.uuid4(), email=ADMIN_EMAIL,
                    password_hash=get_password_hash(PASSWORD), role=UserRole.admin))
        db.add(User(id=uuid.uuid4(), email=SPECIALIST_EMAIL,
                    password_hash=get_password_hash(PASSWORD), role=UserRole.specialist))
        await db.commit()
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client: AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(client):
    return {"Authorization": f"Bearer {await _token(client, ADMIN_EMAIL)}"}


@pytest_asyncio.fixture
async def spec_headers(client):
    return {"Authorization": f"Bearer {await _token(client, SPECIALIST_EMAIL)}"}


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
