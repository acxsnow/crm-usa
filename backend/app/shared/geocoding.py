"""Coordenadas a partir de la dirección, para las obras que no traen el GPS de
la visita (el vendedor no dio permiso de ubicación, la obra se creó a mano o
son datos de prueba).

Proveedor: el geocodificador del Censo de EE. UU. Es gratis, no pide llave y
cubre las direcciones de California, Arizona y Nevada. Solo viaja la dirección
(calle, ciudad, estado y ZIP); nunca el nombre del cliente. La unidad o el
espacio del parque («Spc 7») no se manda: el Censo ubica la calle, y el punto
del parque basta para llegar.

`GEOCODER=off` lo apaga (las obras sin GPS se fijan a mano en el mapa).
"""
import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"
TIMEOUT_S = 8.0


def enabled() -> bool:
    return get_settings().GEOCODER == "census"


async def geocode(street: str | None, city: str | None, state: str | None,
                  zip_code: str | None) -> tuple[float, float] | None:
    """(latitud, longitud) de la dirección, o None si no se encontró o el
    servicio no respondió. Nunca lanza: quien llama sigue con «sin ubicar»."""
    if not enabled() or not street or not (zip_code or (city and state)):
        return None
    params = {"street": street, "city": city or "", "state": state or "", "zip": zip_code or "",
              "benchmark": "Public_AR_Current", "format": "json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            r = await client.get(CENSUS_URL, params=params)
            r.raise_for_status()
            coincidencias = r.json().get("result", {}).get("addressMatches") or []
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("geocoding_failed", error=type(exc).__name__)
        return None
    if not coincidencias:
        return None
    punto = coincidencias[0].get("coordinates") or {}
    try:
        return float(punto["y"]), float(punto["x"])
    except (KeyError, TypeError, ValueError):
        return None
