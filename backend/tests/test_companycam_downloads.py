"""Descarga de fotos y documentos importados."""
import httpx
import pytest
from sqlalchemy import func, select

from app.modules.cases import service as case_service
from app.modules.cases.models import CaseFile
from app.modules.imports.companycam import downloads
from app.modules.imports.companycam.client import CompanyCamClient
from app.modules.imports.models import ImportItem
from app.shared.files import storage
from tests.field_helpers import jpeg_bytes, pdf_bytes


async def _caso(db, org_id, ref="1"):
    caso, _ = await case_service.import_case(db, organization_id=org_id, source="companycam", external_ref=ref,
                                             stage_code="on_hold", address_street="1 Main")
    await db.commit()
    return caso


def _item(org_id, caso, kind, ext, url, **payload):
    return ImportItem(organization_id=org_id, source="companycam", kind=kind, external_id=ext, case_id=caso.id,
                      remote_url=url, payload=payload, status="pending")


def _http(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _cc(handler):
    async def dormir(_):
        return None

    return CompanyCamClient("tok", transport=httpx.MockTransport(handler), sleep=dormir, min_interval=0)


@pytest.mark.asyncio
async def test_descarga_foto_y_documento(db, seeded_org):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add_all([_item(org, caso, "photo", "501", "https://img.test/a.jpg", captured_at=1_760_000_000,
                      latitude=34.2, longitude=-118.3, author_name="Carla", tags=["Front Side"]),
                _item(org, caso, "document", "7001", "https://s3.test/d.pdf", name="Doc.pdf",
                      content_type="application/pdf", project_id="1")])
    await db.commit()
    vistos = []

    def handler(req):
        vistos.append(req)
        return httpx.Response(200, content=jpeg_bytes() if req.url.path.endswith(".jpg") else pdf_bytes())

    async with _http(handler) as http:
        r = await downloads.process_batch(db, org, http=http)
    assert r["downloaded"] == 2 and r["remaining"] == 0
    assert all("authorization" not in q.headers for q in vistos)  # el token no viaja a otros dominios
    foto = (await db.execute(select(CaseFile).where(CaseFile.field_key == "companycam_photo"))).scalar_one()
    assert foto.review_status == "accepted" and foto.watermarked is False and foto.uploaded_by_user_id is None
    assert foto.tags == ["Front Side"] and foto.author_name == "Carla" and foto.latitude == 34.2
    assert foto.external_ref == "501" and foto.mime_type == "image/jpeg"
    assert f"cases/{caso.id}/companycam" in foto.file_path
    assert storage.read_bytes(foto.file_path)[:3] == b"\xff\xd8\xff"
    doc = (await db.execute(select(CaseFile).where(CaseFile.field_key == "companycam_document"))).scalar_one()
    assert doc.mime_type == "application/pdf" and doc.label == "Doc.pdf"
    item = (await db.execute(select(ImportItem).where(ImportItem.external_id == "501"))).scalar_one()
    assert item.status == "downloaded" and item.case_file_id == foto.id


@pytest.mark.asyncio
async def test_url_vencida_se_renueva(db, seeded_org):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add(_item(org, caso, "photo", "501", "https://img.test/viejo.jpg"))
    await db.commit()

    def handler(req):
        return httpx.Response(200, content=jpeg_bytes()) if "nuevo" in req.url.path else httpx.Response(403)

    def api(req):
        return httpx.Response(200, json={"id": "501", "uris": [{"type": "original", "url": "https://img.test/nuevo.jpg"}]})

    async with _http(handler) as http, _cc(api) as cc:
        r = await downloads.process_batch(db, org, http=http, client=cc)
    assert r["downloaded"] == 1
    assert (await db.execute(select(ImportItem))).scalar_one().remote_url.endswith("nuevo.jpg")


@pytest.mark.asyncio
async def test_sigue_404_queda_gone(db, seeded_org):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add(_item(org, caso, "photo", "501", "https://img.test/a.jpg"))
    await db.commit()
    async with _http(lambda r: httpx.Response(404)) as http, _cc(lambda r: httpx.Response(404)) as cc:
        r = await downloads.process_batch(db, org, http=http, client=cc)
    assert r["gone"] == 1
    assert (await db.execute(select(ImportItem))).scalar_one().status == "gone"


@pytest.mark.asyncio
async def test_mime_falso_y_tipo_no_permitido(db, seeded_org):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add_all([_item(org, caso, "photo", "1", "https://x/falsa.jpg"),
                _item(org, caso, "document", "2", "https://x/v.mp4", name="v.mp4", content_type="video/mp4",
                      project_id="1"),
                _item(org, caso, "document", "3", "https://x/falso.pdf", name="f.pdf", content_type="application/pdf",
                      project_id="1")])
    await db.commit()
    llamadas = []

    def handler(req):
        llamadas.append(req.url.path)
        return httpx.Response(200, content=b"MZ\x90\x00 no soy una imagen ni un pdf")

    async with _http(handler) as http:
        r = await downloads.process_batch(db, org, http=http)
    assert r["skipped_type"] == 3 and "/v.mp4" not in llamadas  # el video ni se baja
    assert (await db.execute(select(func.count(CaseFile.id)))).scalar_one() == 0


@pytest.mark.asyncio
async def test_reintentos_hasta_el_limite(db, seeded_org):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add(_item(org, caso, "photo", "1", "https://x/a.jpg"))
    await db.commit()
    async with _http(lambda r: httpx.Response(500)) as http:
        for _ in range(7):
            await downloads.process_batch(db, org, http=http)
    it = (await db.execute(select(ImportItem))).scalar_one()
    assert it.status == "error" and it.attempts == downloads.MAX_ATTEMPTS and "500" in it.last_error
    assert await downloads.retry_errors(db, org) == 1
    await db.refresh(it)
    assert it.status == "pending" and it.attempts == 0


@pytest.mark.asyncio
async def test_no_duplica_y_recupera_bloqueos_viejos(db, seeded_org):
    from datetime import datetime, timedelta, timezone

    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add_all([_item(org, caso, "photo", "1", "https://x/a.jpg"), _item(org, caso, "photo", "2", "https://x/b.jpg")])
    await db.commit()
    it = (await db.execute(select(ImportItem).where(ImportItem.external_id == "2"))).scalar_one()
    it.status, it.locked_at = "downloading", datetime.now(timezone.utc) - timedelta(minutes=30)
    await db.commit()
    async with _http(lambda r: httpx.Response(200, content=jpeg_bytes())) as http:
        await downloads.process_batch(db, org, http=http)
        r2 = await downloads.process_batch(db, org, http=http)
    assert r2.get("downloaded", 0) == 0
    assert (await db.execute(select(func.count(CaseFile.id)))).scalar_one() == 2


@pytest.mark.asyncio
async def test_tope_de_tamano(db, seeded_org, monkeypatch):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add(_item(org, caso, "photo", "1", "https://x/a.jpg"))
    await db.commit()
    monkeypatch.setattr(downloads, "MAX_BYTES", 10)
    async with _http(lambda r: httpx.Response(200, content=jpeg_bytes())) as http:
        await downloads.process_batch(db, org, http=http)
    it = (await db.execute(select(ImportItem))).scalar_one()
    assert it.status == "error" and it.attempts == downloads.MAX_ATTEMPTS and "25 MB" in it.last_error


@pytest.mark.asyncio
async def test_si_falla_el_commit_se_borra_el_archivo(db, seeded_org, monkeypatch):
    org = seeded_org["org"].id
    caso = await _caso(db, org)
    db.add(_item(org, caso, "photo", "1", "https://x/a.jpg"))
    await db.commit()
    guardados = []
    original = storage.save_bytes

    def espiar(**kw):
        ruta = original(**kw)
        guardados.append(ruta)
        return ruta

    monkeypatch.setattr(storage, "save_bytes", espiar)
    original_flush = db.flush

    async def flush_roto(*a, **k):
        if guardados:
            raise RuntimeError("commit roto")
        return await original_flush(*a, **k)

    monkeypatch.setattr(db, "flush", flush_roto)
    async with _http(lambda r: httpx.Response(200, content=jpeg_bytes())) as http:
        await downloads.process_batch(db, org, http=http)
    assert guardados and not storage.absolute_path(guardados[0]).exists()
    assert (await db.execute(select(ImportItem))).scalar_one().status == "error"
