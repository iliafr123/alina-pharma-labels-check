import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.errors import AppError, classify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Alina Pharma Labels Check API",
    description="Система автоматизированной проверки макетов этикеток БАД",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    # Accept any Railway subdomain so the frontend domain can be renamed without a CORS change.
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_body(err: AppError) -> dict:
    """Response shape the frontend renders: a title, what to do, and the code.

    `detail` stays a string-compatible field so older clients that print
    `response.data.detail` still show something meaningful.
    """
    return {
        "detail": err.message,
        "error": err.to_dict(),
    }


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Errors the app raised deliberately - already carry a cause and a hint."""
    from app.core.database import AsyncSessionLocal
    from app.services.error_service import log_error

    try:
        async with AsyncSessionLocal() as db:
            await log_error(db, exc, source="api", path=str(request.url.path), exc=exc)
    except Exception:
        logging.getLogger("alina.errors").exception("failed to persist AppError")
    return JSONResponse(status_code=exc.http_status, content=_error_body(exc))


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    """Anything unexpected: classify it, record it, and still say something useful."""
    from app.core.database import AsyncSessionLocal
    from app.services.error_service import log_error

    err = classify(exc)
    try:
        async with AsyncSessionLocal() as db:
            await log_error(db, err, source="api", path=str(request.url.path), exc=exc)
    except Exception:
        logging.getLogger("alina.errors").exception("failed to persist unhandled error")
    return JSONResponse(status_code=err.http_status, content=_error_body(err))


from app.api import auth, users, uploads, checks, admin, references

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(uploads.router, prefix="/api/v1")
app.include_router(checks.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(references.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}
