"""Clientes delgados de Stripe y Plaid sobre httpx (sin sus SDK), el cifrado de
los tokens y la verificación de la firma de cada webhook.

Las pruebas reemplazan `stripe_request` y `plaid_request`; nada sale a la red.
"""
import base64
import hashlib
import hmac
import time
from decimal import Decimal
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.shared.errors import ExternalServiceError, InvalidInputError

TIMEOUT = 20.0


# ---------------------------------------------------------------------------
# Cifrado de tokens (Fernet)
# ---------------------------------------------------------------------------

def _fernet() -> Fernet:
    s = get_settings()
    llave = s.PAYMENTS_ENCRYPTION_KEY
    if not llave:
        if s.ENVIRONMENT not in ("development", "test"):
            raise ExternalServiceError("Falta PAYMENTS_ENCRYPTION_KEY para guardar la conexión del banco.",
                                       code="payments_key_missing")
        llave = base64.urlsafe_b64encode(hashlib.sha256(("pagos:" + s.JWT_SECRET_KEY).encode()).digest()).decode()
    return Fernet(llave.encode() if isinstance(llave, str) else llave)


def encrypt(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decrypt(cifrado: str) -> str:
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken:
        raise ExternalServiceError("No se pudo leer la conexión del banco; vuelve a conectarla.",
                                   code="bank_token_unreadable") from None


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------

def stripe_enabled() -> bool:
    return bool(get_settings().STRIPE_SECRET_KEY)


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe recibe formularios con claves anidadas: a[b][0][c]=x."""
    pares: list[tuple[str, str]] = []
    for k, v in data.items():
        clave = f"{prefix}[{k}]" if prefix else str(k)
        if isinstance(v, dict):
            pares += _flatten(v, clave)
        elif isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    pares += _flatten(item, f"{clave}[{i}]")
                else:
                    pares.append((f"{clave}[{i}]", str(item)))
        elif v is not None:
            pares.append((clave, "true" if v is True else "false" if v is False else str(v)))
    return pares


async def stripe_request(method: str, path: str, data: dict | None = None, *, idempotency_key: str | None = None) -> dict:
    s = get_settings()
    if not s.STRIPE_SECRET_KEY:
        raise ExternalServiceError("El cobro en línea no está configurado.", code="stripe_not_configured")
    headers = {"Authorization": f"Bearer {s.STRIPE_SECRET_KEY}", "Stripe-Version": "2024-06-20"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    async with httpx.AsyncClient(base_url=s.STRIPE_API_BASE, timeout=TIMEOUT) as c:
        if method == "GET":
            r = await c.get(path, params=_flatten(data or {}), headers=headers)
        else:
            # Formulario ya codificado: httpx trata una lista de pares como un
            # flujo síncrono y falla dentro de un cliente asíncrono.
            r = await c.request(method, path, content=urlencode(_flatten(data or {})),
                                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"})
    if r.status_code >= 400:
        detalle = r.json().get("error", {}).get("message", "") if r.headers.get("content-type", "").startswith(
            "application/json") else ""
        raise ExternalServiceError(f"Stripe rechazó la operación. {detalle}".strip(), code="stripe_error")
    return r.json()


def cents(monto: Decimal) -> int:
    return int((monto * 100).quantize(Decimal("1")))


def from_cents(valor: int | None) -> Decimal:
    return (Decimal(valor or 0) / 100).quantize(Decimal("0.01"))


def verify_stripe_signature(payload: bytes, header: str | None, *, tolerance: int = 300) -> None:
    """La firma de Stripe: `t=<epoch>,v1=<hmac sha256 de "t.payload">`."""
    secreto = get_settings().STRIPE_WEBHOOK_SECRET
    if not secreto or not header:
        raise InvalidInputError("Firma de Stripe ausente.", code="invalid_signature")
    partes = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    firmas = [p.split("=", 1)[1] for p in header.split(",") if p.startswith("v1=")]
    try:
        t = int(partes.get("t", "0"))
    except ValueError:
        t = 0
    if not t or abs(time.time() - t) > tolerance:
        raise InvalidInputError("Firma de Stripe vencida.", code="invalid_signature")
    esperada = hmac.new(secreto.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(esperada, f) for f in firmas):
        raise InvalidInputError("Firma de Stripe inválida.", code="invalid_signature")


# ---------------------------------------------------------------------------
# Plaid
# ---------------------------------------------------------------------------

PLAID_HOSTS = {"sandbox": "https://sandbox.plaid.com", "production": "https://production.plaid.com"}


def plaid_enabled() -> bool:
    s = get_settings()
    return bool(s.PLAID_CLIENT_ID and s.PLAID_SECRET)


async def plaid_request(path: str, body: dict) -> dict:
    s = get_settings()
    if not plaid_enabled():
        raise ExternalServiceError("La banca conectada no está configurada.", code="plaid_not_configured")
    host = PLAID_HOSTS.get(s.PLAID_ENV, PLAID_HOSTS["sandbox"])
    async with httpx.AsyncClient(base_url=host, timeout=TIMEOUT) as c:
        r = await c.post(path, json={"client_id": s.PLAID_CLIENT_ID, "secret": s.PLAID_SECRET, **body})
    datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400:
        codigo = datos.get("error_code", "")
        if codigo == "ITEM_LOGIN_REQUIRED":
            raise ExternalServiceError("El banco pide volver a iniciar sesión.", code="bank_login_required")
        raise ExternalServiceError(f"Plaid rechazó la operación ({codigo or r.status_code}).", code="plaid_error")
    return datos


async def verify_plaid_webhook(payload: bytes, token: str | None) -> None:
    """Plaid firma cada webhook con un JWT ES256 (cabecera Plaid-Verification)
    cuyo `request_body_sha256` debe coincidir con el cuerpo recibido."""
    import jwt

    if not token:
        raise InvalidInputError("Firma de Plaid ausente.", code="invalid_signature")
    try:
        cabecera = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise InvalidInputError("Firma de Plaid inválida.", code="invalid_signature") from None
    if cabecera.get("alg") != "ES256" or not cabecera.get("kid"):
        raise InvalidInputError("Firma de Plaid inválida.", code="invalid_signature")
    llave = (await plaid_request("/webhook_verification_key/get", {"key_id": cabecera["kid"]}))["key"]
    try:
        claims = jwt.decode(token, jwt.PyJWK(llave).key, algorithms=["ES256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        raise InvalidInputError("Firma de Plaid inválida.", code="invalid_signature") from None
    if time.time() - claims.get("iat", 0) > 300:
        raise InvalidInputError("Firma de Plaid vencida.", code="invalid_signature")
    if not hmac.compare_digest(claims.get("request_body_sha256", ""), hashlib.sha256(payload).hexdigest()):
        raise InvalidInputError("El cuerpo no coincide con la firma de Plaid.", code="invalid_signature")
