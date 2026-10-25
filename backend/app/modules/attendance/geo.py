"""Distancias y orden de paradas sin servicios externos.

Todo es en línea recta (haversine) y así se marca: `straight_line`. Si más
adelante se conecta un servicio de rutas, sus kilómetros se guardan como
`route` y conviven con estos sin confundirse (spec, «Mapa y rutas»).
"""
import math
from urllib.parse import quote

EARTH_RADIUS_KM = 6371.0088
STRAIGHT_LINE = "straight_line"


def valid_point(lat, lng) -> bool:
    return (lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180
            and not (lat == 0 and lng == 0))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_neighbor_order(start: tuple[float, float] | None, stops: list[dict]) -> list[dict]:
    """Ordena las paradas yendo siempre a la más cercana. `stops` trae
    `latitude` y `longitude`; las que no tienen quedan al final, en su orden.
    Es distancia, no tiempo de manejo: la UI lo dice."""
    con = [s for s in stops if valid_point(s.get("latitude"), s.get("longitude"))]
    sin = [s for s in stops if s not in con]
    if not con:
        return sin
    orden: list[dict] = []
    actual = start if start and valid_point(*start) else (con[0]["latitude"], con[0]["longitude"])
    pendientes = list(con)
    while pendientes:
        siguiente = min(pendientes, key=lambda s: haversine_km(actual[0], actual[1], s["latitude"], s["longitude"]))
        siguiente = {**siguiente, "km_from_previous": round(
            haversine_km(actual[0], actual[1], siguiente["latitude"], siguiente["longitude"]), 2)}
        orden.append(siguiente)
        pendientes = [s for s in pendientes if s["id"] != siguiente["id"]]
        actual = (siguiente["latitude"], siguiente["longitude"])
    return orden + sin


def google_maps_directions_url(origin: tuple[float, float] | None, stops: list[dict]) -> str | None:
    """Enlace de «Cómo llegar» de Google Maps (gratis, sin llave): abre la app
    en el celular con todas las paradas. Google acepta hasta 9 intermedias."""
    puntos = [s for s in stops if valid_point(s.get("latitude"), s.get("longitude"))][:10]
    if not puntos:
        return None
    destino = puntos[-1]
    url = ("https://www.google.com/maps/dir/?api=1&travelmode=driving"
           f"&destination={destino['latitude']},{destino['longitude']}")
    if origin and valid_point(*origin):
        url += f"&origin={origin[0]},{origin[1]}"
    if len(puntos) > 1:
        url += "&waypoints=" + quote("|".join(f"{p['latitude']},{p['longitude']}" for p in puntos[:-1]))
    return url
