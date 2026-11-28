"""Cliente HTTP de la API v2 de CompanyCam (solo lectura).

- `Authorization: Bearer <token>`; el token nunca se imprime ni se registra.
- Paginación por `page` hasta recibir una lista vacía (CompanyCam topa el
  tamaño de página, así que no se confía en `per_page`).
- 429 y 5xx se reintentan con espera (`Retry-After` si viene, si no
  exponencial), hasta `MAX_ATTEMPTS`; los cortes de red también.
- Ritmo propio de unas 4 peticiones por segundo.
- 404 → `CompanyCamNotFound` (un proyecto eliminado no frena la importación).
"""
import asyncio
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable

import httpx

BASE_URL = "https://api.companycam.com/v2"
MAX_ATTEMPTS = 6
MIN_INTERVAL = 0.25  # ~4 peticiones por segundo
MAX_PAGES = 5000
ENV_FILE = Path.home() / ".companycam.env"


class CompanyCamError(Exception):
    pass


class CompanyCamNotFound(CompanyCamError):
    pass


def resolve_token() -> str | None:
    """El token, de la variable de entorno o de `~/.companycam.env`
    (línea `COMPANYCAM_TOKEN=...`). Nunca se imprime."""
    token = os.environ.get("COMPANYCAM_TOKEN", "").strip()
    if token:
        return token
    try:
        for linea in ENV_FILE.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea.startswith("COMPANYCAM_TOKEN="):
                valor = linea.split("=", 1)[1].strip().strip("'\"")
                return valor or None
    except OSError:
        pass
    return None


class CompanyCamClient:
    def __init__(
        self,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = BASE_URL,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval: float = MIN_INTERVAL,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(30.0),
            transport=transport,
        )
        self._sleep = sleep
        self._min_interval = min_interval
        self._last = 0.0

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "CompanyCamClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def _pace(self) -> None:
        espera = self._last + self._min_interval - time.monotonic()
        if espera > 0:
            await self._sleep(espera)
        self._last = time.monotonic()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        ultimo = "sin respuesta"
        for intento in range(1, MAX_ATTEMPTS + 1):
            await self._pace()
            try:
                r = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                ultimo = f"red: {type(exc).__name__}"
                await self._sleep(min(2 ** intento, 30))
                continue
            if r.status_code == 404:
                raise CompanyCamNotFound(f"404 en {path}")
            if r.status_code == 429 or r.status_code >= 500:
                ultimo = f"HTTP {r.status_code}"
                try:
                    espera = float(r.headers.get("Retry-After", ""))
                except ValueError:
                    espera = float(min(2 ** intento, 60))
                await self._sleep(max(espera, 0.0))
                continue
            if r.status_code >= 400:
                raise CompanyCamError(f"HTTP {r.status_code} en {path}")
            if not r.content.strip():
                return []
            try:
                return r.json()
            except ValueError as exc:
                raise CompanyCamError(f"Respuesta no JSON en {path}") from exc
        raise CompanyCamError(f"{ultimo} en {path} tras {MAX_ATTEMPTS} intentos")

    async def paginate(self, path: str, params: dict[str, Any] | None = None) -> AsyncIterator[dict]:
        """Recorre las páginas hasta una vacía. Corta también si una página
        repite a la anterior (un endpoint que ignore `page` no cicla)."""
        primero_anterior = None
        for pagina in range(1, MAX_PAGES + 1):
            datos = await self.get(path, {**(params or {}), "page": pagina, "per_page": 100})
            if not isinstance(datos, list) or not datos:
                return
            marca = str(datos[0].get("id")) if isinstance(datos[0], dict) else None
            if marca is not None and marca == primero_anterior:
                return
            primero_anterior = marca
            for item in datos:
                yield item

    async def list_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict]:
        return [x async for x in self.paginate(path, params)]

    async def project(self, project_id: str) -> dict:
        return await self.get(f"/projects/{project_id}")

    async def refresh_photo_url(self, photo_id: str) -> str | None:
        """URL vigente de la foto original (las de CompanyCam caducan)."""
        try:
            foto = await self.get(f"/photos/{photo_id}")
        except CompanyCamNotFound:
            return None
        return original_uri(foto)

    async def refresh_document_url(self, project_id: str, document_id: str) -> str | None:
        try:
            documentos = await self.list_all(f"/projects/{project_id}/documents")
        except CompanyCamNotFound:
            return None
        for d in documentos:
            if str(d.get("id")) == str(document_id):
                return d.get("url")
        return None


def original_uri(photo: dict) -> str | None:
    """La URL de la imagen original de una foto de CompanyCam."""
    uris = photo.get("uris") or []
    for tipo in ("original", "web"):
        for u in uris:
            if u.get("type") == tipo and (u.get("url") or u.get("uri")):
                return u.get("url") or u.get("uri")
    return None
