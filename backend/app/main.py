import uuid
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging()
logger = structlog.get_logger(__name__)

if settings.ENVIRONMENT != "development" and settings.JWT_SECRET_KEY == "CHANGE_ME_IN_PRODUCTION":
    # Fail loudly rather than silently signing every token with a public,
    # well-known secret (OWASP A02: Cryptographic Failures / A07: Identification
    # and Authentication Failures).
    raise RuntimeError(
        "JWT_SECRET_KEY is still the placeholder default. Set a real secret "
        "via the JWT_SECRET_KEY environment variable before running outside development."
    )

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
)

frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
frontend_index = frontend_dist / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# OWASP secure-headers baseline (Phase 5 hardening). This is an API-only
# backend — the frontend is a separate origin/deployment — so there's no
# HTML response here to attach a same-origin CSP to; the headers below are
# the ones that matter for a JSON API: no MIME-sniffing, no framing, no
# referrer leakage, and (in non-dev environments, where TLS is assumed)
# HSTS.
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if settings.ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if not frontend_index.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found.")
    if full_path == "health" or full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found.")

    requested = (frontend_dist / full_path).resolve()
    if full_path and requested.exists() and requested.is_file() and frontend_dist in requested.parents:
        return FileResponse(requested)
    return FileResponse(frontend_index)
