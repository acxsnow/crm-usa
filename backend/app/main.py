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
from app.shared.error_handlers import build_unhandled_error_response, register_error_handlers
from app.shared.request_context import clear_request_context, set_request_context

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

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    # Se limpia antes de enlazar: sin esto, el contexto de una petición anterior
    # sobrevive en el mismo worker y las líneas de log salen con el request_id
    # equivocado, que es peor que no tener registro.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    # Los manejadores de error lo leen de aquí para incluirlo en la respuesta.
    request.state.request_id = request_id
    # La auditoría lo toma de aquí, para no ir pasándolo por parámetro desde
    # cada endpoint hasta el service que registra el evento.
    set_request_context(
        request_id=request_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        # Se atrapa aquí, y no solo con `@app.exception_handler(Exception)`,
        # porque ese manejador vive en el middleware de errores de Starlette,
        # que está POR ENCIMA del de CORS: su respuesta no pasaría por CORS, el
        # navegador la bloquearía por política de origen y el frontend vería un
        # error de red en vez del 500 con su código de referencia. Desde este
        # middleware, la respuesta sí sube por CORS.
        response = build_unhandled_error_response(request, exc)
    finally:
        structlog.contextvars.clear_contextvars()
        clear_request_context()
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


# CORS se registra DE ÚLTIMO a propósito: `add_middleware` inserta al principio
# de la cadena, así que el último en registrarse es el más externo. Si CORS
# quedara por dentro, las respuestas que generan los middlewares de arriba
# —en particular el 500 de un fallo no controlado— saldrían sin cabeceras de
# origen, el navegador las bloquearía y el frontend vería un error de red en
# lugar del error real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Traducción de errores a respuestas HTTP (ver app/shared/error_handlers.py).
register_error_handlers(app)


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
