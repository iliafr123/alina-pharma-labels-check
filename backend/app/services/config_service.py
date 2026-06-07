import uuid
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.config import SystemConfig
from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    # Pad/encode to valid Fernet key if needed
    if len(key) < 32:
        key = key.ljust(32, "=")
    import base64
    try:
        return Fernet(key.encode())
    except Exception:
        return Fernet(base64.urlsafe_b64encode(key[:32].encode().ljust(32, b"=")))


async def get_config(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    if not row or row.value is None:
        return None
    if row.is_encrypted:
        try:
            return _get_fernet().decrypt(row.value.encode()).decode()
        except Exception:
            return row.value
    return row.value


async def set_config(db: AsyncSession, key: str, value: str, is_encrypted: bool = False, updated_by_id: uuid.UUID | None = None):
    stored_value = value
    if is_encrypted and value:
        stored_value = _get_fernet().encrypt(value.encode()).decode()
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = stored_value
        row.is_encrypted = is_encrypted
        row.updated_by = updated_by_id
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemConfig(key=key, value=stored_value, is_encrypted=is_encrypted, updated_by=updated_by_id, updated_at=datetime.now(timezone.utc)))
    await db.commit()


def mask_key(value: str | None) -> str:
    if not value or len(value) < 4:
        return "****"
    return "****" + value[-4:]


async def get_pipeline_config(db: AsyncSession) -> dict:
    keys = ["ocr_provider", "llm_provider", "unified_llm", "pipeline_mode"]
    result = {}
    for key in keys:
        val = await get_config(db, key)
        result[key] = val or ""
    return result


API_KEY_PROVIDERS = ["openai", "anthropic", "gemini", "grok", "yandex_vision", "abbyy"]


async def get_masked_api_keys(db: AsyncSession) -> dict:
    masked = {}
    for provider in API_KEY_PROVIDERS:
        raw = await get_config(db, f"api_key_{provider}")
        masked[provider] = mask_key(raw)
    return masked


async def get_extras(db: AsyncSession) -> dict:
    """Non-key provider settings: Yandex folderId (plain), ABBYY password (masked) + url."""
    return {
        "yandex_folder_id": (await get_config(db, "yandex_folder_id")) or "",
        "abbyy_password": mask_key(await get_config(db, "abbyy_password")),
        "abbyy_url": (await get_config(db, "abbyy_url")) or "https://cloud.ocrsdk.com",
    }


async def build_ocr_provider(db: AsyncSession, name: str):
    from app.pipeline.providers import get_ocr_provider
    key_name = "anthropic" if name == "anthropic_vision" else name  # vision-LLMs reuse the LLM key
    key = (await get_config(db, f"api_key_{key_name}")) or ""
    extras = {}
    if name == "yandex_vision":
        extras["folder_id"] = await get_config(db, "yandex_folder_id")
    elif name == "abbyy":
        extras["password"] = await get_config(db, "abbyy_password")
        extras["base_url"] = await get_config(db, "abbyy_url")
    return get_ocr_provider(name, key, **extras)


async def build_llm_provider(db: AsyncSession, name: str):
    from app.pipeline.providers import get_llm_provider
    return get_llm_provider(name, (await get_config(db, f"api_key_{name}")) or "")
