import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.agent_routes import router as agent_router
from app.api.customer_routes import router as customer_router
from app.api.dashboard_routes import router as dashboard_router
from app.api.fix_routes import router as fix_router
from app.api.report_routes import router as report_router
from app.api.routes import router
from app.core.config import get_settings
from app.db.session import engine
from app.engines.agent.provider import InferenceError, get_agent_provider
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
    title="AgentLane API",
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
app.include_router(fix_router)
app.include_router(customer_router)
app.include_router(dashboard_router)


def error_response(status: int, code: str, message: str, details: list | None = None):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or []}},
    )


@app.middleware("http")
async def customer_surface(request: Request, call_next):
    path = request.url.path
    if get_settings().customer_mode_enabled and path.startswith("/api/v1/"):
        public = path == "/api/v1/free-scans" or any(
            path.startswith(prefix)
            for prefix in (
                "/api/v1/free-reports/",
                "/api/v1/verification/",
                "/api/v1/webhooks/stripe",
                "/api/v1/dashboard/",  # Owner dashboard; every route requires its token.
            )
        )
        if not public:
            return error_response(
                403,
                "customer_only",
                "Internal workspace access is disabled. AI browser-agent testing is coming Christmas 2026.",
            )
    return await call_next(request)


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


@app.get("/health/llm", tags=["Health"])
async def llm_health():
    """Check provider reachability and model availability without inference."""
    if get_settings().customer_mode_enabled:
        return JSONResponse(
            status_code=503,
            content={
                "status": "coming_soon",
                "message": "AI agent testing is coming Christmas 2026",
            },
        )
    provider = None
    try:
        provider = get_agent_provider(get_settings())
        result = await provider.health()
        ready = result["reachable"] and result["model_available"]
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ok" if ready else "unavailable", **result},
        )
    except (InferenceError, ValidationError, ValueError) as exc:
        logging.getLogger(__name__).warning("LLM health check failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "error": type(exc).__name__},
        )
    finally:
        if provider is not None:
            await provider.close()


@app.exception_handler(ValueError)
async def invalid_scope(_: Request, exc: ValueError):
    return error_response(422, "invalid_crawl_scope", str(exc))
