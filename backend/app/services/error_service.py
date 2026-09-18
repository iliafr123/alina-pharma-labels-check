"""Persistent error log: one place that records every failure so the admin
screen ("Ошибки") can show what actually went wrong.

Writing must never mask the original failure, so every helper here swallows its
own exceptions - a logging problem must not replace the real error.
"""
from __future__ import annotations

import logging
import traceback as _tb
import uuid
from datetime import datetime, timezone

from app.core.errors import AppError, classify

logger = logging.getLogger("alina.errors")

# Keep the table from growing without bound on a small Railway Postgres.
MAX_ROWS = 2000
TRIM_TO = 1500


def _row(err: AppError, *, source: str, path: str | None, task_id: str | None,
         user_id: uuid.UUID | None, exc: BaseException | None, severity: str):
    from app.models.error_log import ErrorLog
    tb = None
    if exc is not None:
        try:
            tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))[-6000:]
        except Exception:
            tb = None
    return ErrorLog(
        id=uuid.uuid4(),
        code=err.code, title=err.title[:500], hint=err.hint, detail=err.detail,
        provider=err.provider or None, subsystem=err.subsystem or None, stage=err.stage or None,
        source=source, severity=severity, http_status=err.http_status,
        path=path, task_id=task_id, user_id=user_id, context=err.context or None,
        traceback=tb, created_at=datetime.now(timezone.utc),
    )


def _log_line(err: AppError, source: str) -> str:
    """The same information in the container log, so Railway logs are useful too."""
    bits = [f"[{err.code}]", err.title]
    if err.provider:
        bits.append(f"provider={err.provider}")
    if err.stage:
        bits.append(f"stage={err.stage}")
    if err.detail:
        bits.append(f"detail={err.detail[:300]}")
    return f"({source}) " + " | ".join(bits)


async def log_error(db, err: AppError, *, source: str = "api", path: str | None = None,
                    task_id: str | None = None, user_id: uuid.UUID | None = None,
                    exc: BaseException | None = None, severity: str = "error") -> None:
    """Async path (FastAPI). Commits its own row."""
    logger.error(_log_line(err, source))
    try:
        db.add(_row(err, source=source, path=path, task_id=task_id,
                    user_id=user_id, exc=exc, severity=severity))
        await db.commit()
        await _trim_async(db)
    except Exception as e:  # never let logging break the request
        logger.warning(f"error_log write failed: {e}")
        try:
            await db.rollback()
        except Exception:
            pass


async def log_exception(db, exc: Exception, **kw) -> AppError:
    """Classify then log; returns the AppError so the caller can render it."""
    err = classify(exc, provider=kw.pop("provider", ""), subsystem=kw.pop("subsystem", ""),
                   stage=kw.pop("stage", ""), endpoint=kw.pop("endpoint", ""),
                   bucket=kw.pop("bucket", ""))
    await log_error(db, err, exc=exc, **kw)
    return err


async def _trim_async(db) -> None:
    from sqlalchemy import select, delete, func
    from app.models.error_log import ErrorLog
    try:
        total = (await db.execute(select(func.count(ErrorLog.id)))).scalar_one()
        if total <= MAX_ROWS:
            return
        keep = (await db.execute(
            select(ErrorLog.created_at).order_by(ErrorLog.created_at.desc()).offset(TRIM_TO).limit(1)
        )).scalar_one_or_none()
        if keep is not None:
            await db.execute(delete(ErrorLog).where(ErrorLog.created_at < keep))
            await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


async def log_error_standalone(err: AppError, **kw) -> None:
    """For code paths without a session at hand (Celery worker). Opens its own."""
    from app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            await log_error(db, err, **kw)
    except Exception as e:
        logger.warning(f"standalone error_log write failed: {e}")
