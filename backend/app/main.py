import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.agent_routes import router as agent_router
from app.api.report_routes import router as report_router
from app.api.routes import router
from app.core.config import get_settings
from app.db.session import engine
from app.schemas.api import ErrorResponse
from app.services.audits import RecordNotFound
from app.services.crawls import recover_expired_scans


@asynccontextmanager
async def lifespan(app: FastAPI):
    recovery = asyncio.create_task(recover_expired_scans())
    try:
        yield
    finally:
        recovery.cancel()
        with suppress(asyncio.CancelledError):
            await recovery


app = FastAPI(
    lifespan=lifespan,
    title="AgentReadiness API",
    version="0.1.0",
    responses={code: {"model": ErrorResponse} for code in (404, 422, 500, 501, 503)},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
app.include_router(agent_router)
app.include_router(report_router)


def error_response(status: int, code: str, message: str, details: list | None = None):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or []}},
    )


@app.exception_handler(RecordNotFound)
async def not_found(_: Request, exc: RecordNotFound):
    return error_response(404, "not_found", str(exc))


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return error_response(
        exc.status_code,
        "not_implemented" if exc.status_code == 501 else "http_error",
        str(exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [
        {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()
    ]
    return error_response(422, "validation_error", "Request validation failed", details)


@app.exception_handler(SQLAlchemyError)
async def database_error(_: Request, exc: SQLAlchemyError):
    logging.getLogger(__name__).error("Database operation failed (%s)", type(exc).__name__)
    return error_response(503, "database_unavailable", "Database operation unavailable")


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    logging.getLogger(__name__).error("Unexpected server error (%s)", type(exc).__name__)
    return error_response(500, "internal_error", "An unexpected server error occurred")


@app.get("/health", tags=["Health"])
def health():
    """Readiness check; verifies database access and the initial migration."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1 FROM projects LIMIT 1"))
    return {"status": "ok", "database": "ok"}


@app.exception_handler(ValueError)
async def invalid_scope(_: Request, exc: ValueError):
    return error_response(422, "invalid_crawl_scope", str(exc))
