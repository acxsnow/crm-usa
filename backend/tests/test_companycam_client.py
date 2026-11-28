"""Cliente HTTP de CompanyCam con transporte simulado (sin red)."""
import httpx
import pytest

from app.modules.imports.companycam.client import (
    CompanyCamClient,
    CompanyCamError,
    CompanyCamNotFound,
    original_uri,
)


async def _nada(_):
    return None


def _client(handler, esperas=None):
    async def dormir(s):
        if esperas is not None:
            esperas.append(s)

    return CompanyCamClient("secreto", transport=httpx.MockTransport(handler), sleep=dormir, min_interval=0)


@pytest.mark.asyncio
async def test_pagina_hasta_lista_vacia_y_manda_bearer():
    vistos = []

    def handler(req):
        vistos.append(req)
        pagina = int(req.url.params["page"])
        return httpx.Response(200, json=[{"id": str(pagina * 10 + i)} for i in range(2)] if pagina <= 3 else [])

    async with _client(handler) as c:
        items = await c.list_all("/projects")
    assert [i["id"] for i in items] == ["10", "11", "20", "21", "30", "31"]
    assert all(r.headers["authorization"] == "Bearer secreto" for r in vistos)


@pytest.mark.asyncio
async def test_pagina_repetida_corta_el_ciclo():
    def handler(req):
        return httpx.Response(200, json=[{"id": "1"}])

    async with _client(handler) as c:
        assert len(await c.list_all("/x")) == 1


@pytest.mark.asyncio
async def test_429_respeta_retry_after_y_reintenta():
    llamadas, esperas = [], []

    def handler(req):
        llamadas.append(1)
        if len(llamadas) < 3:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json=[{"id": "1"}])

    async with _client(handler, esperas) as c:
        assert await c.get("/users") == [{"id": "1"}]
    assert len(llamadas) == 3 and esperas.count(7.0) == 2


@pytest.mark.asyncio
async def test_5xx_agota_reintentos():
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(503)

    async with _client(handler) as c:
        with pytest.raises(CompanyCamError):
            await c.get("/users")
    assert len(n) == 6


@pytest.mark.asyncio
async def test_corte_de_red_se_reintenta():
    n = []

    def handler(req):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("corte")
        return httpx.Response(200, json={"id": "9"})

    async with _client(handler) as c:
        assert (await c.project("9"))["id"] == "9"
    assert len(n) == 2


@pytest.mark.asyncio
async def test_404_es_not_found_y_sin_reintento():
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(404)

    async with _client(handler) as c:
        with pytest.raises(CompanyCamNotFound):
            await c.project("1")
        assert await c.refresh_photo_url("1") is None
    assert len(n) == 2


@pytest.mark.asyncio
async def test_refresh_photo_url():
    def handler(req):
        assert req.url.path == "/v2/photos/55"
        return httpx.Response(200, json={"id": "55", "uris": [{"type": "web", "url": "https://x/w.jpg"},
                                                              {"type": "original", "url": "https://x/o.jpg"}]})

    async with _client(handler) as c:
        assert await c.refresh_photo_url("55") == "https://x/o.jpg"
    assert original_uri({"uris": []}) is None
