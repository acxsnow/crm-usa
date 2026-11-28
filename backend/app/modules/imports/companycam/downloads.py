"""Descarga de los binarios (fotos y documentos) de lo importado.

Trabaja sobre `import_items` por lotes. Un elemento pasa por
`pending → downloading → downloaded`; si falla vuelve a `error` y se reintenta
(hasta `MAX_ATTEMPTS`); un tipo no permitido queda `skipped_type` y lo que ya
no existe en CompanyCam, `gone`. El `CaseFile` se crea al final, cuando el
archivo ya está guardado; si el commit falla se borra el archivo.

Las URL de CompanyCam caducan: ante 403/404 se pide una vigente a la API
(`refresh_photo_url`). **Al bajar el binario no se manda el token**: las URL
apuntan a otros dominios (CDN, S3)."""
import io
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.cases.models import Case, CaseFile
from app.modules.imports.companycam.client import CompanyCamClient, CompanyCamError
from app.modules.imports.models import ImportItem
from app.shared.errors import InvalidInputError
from app.shared.files import storage
from app.shared.files.validation import _FAMILY, check_type, sniff_mime

logger = structlog.get_logger(__name__)

SOURCE = "companycam"
BATCH_SIZE = 10
# Presupuesto de tiempo por lote: el límite duro de la tarea es 180 s y con `pool=solo`
# Celery no lo aplica, así que el lote se corta solo y suelta lo que no alcanzó.
BATCH_BUDGET_SECONDS = 100.0
THUMB_SIZE = 400
MAX_ATTEMPTS = 5
STALE_AFTER = timedelta(minutes=10)
MAX_BYTES = 25 * 1024 * 1024
PHOTO_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
DOC_MIME = PHOTO_MIME | {"application/pdf"}
_MIME_BY_FAMILY = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "heic": "image/heic",
                   "pdf": "application/pdf"}
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic",
        "image/heif": "heif", "application/pdf": "pdf"}
REVIEW_NOTE = "Importado de CompanyCam (sin revisión)"
KINDS = ("photo", "document")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _TooLarge(Exception):
    pass


class _Gone(Exception):
    pass


class DiskFull(Exception):
    pass


def free_bytes() -> int:
    return shutil.disk_usage(storage.absolute_path("")).free


def min_free_bytes() -> int:
    return int(get_settings().COMPANYCAM_MIN_FREE_GB * 1024 ** 3)


def _elegibles(organization_id: uuid.UUID, ahora: datetime):
    return (ImportItem.organization_id == organization_id, ImportItem.source == SOURCE,
            ImportItem.kind.in_(KINDS), or_(
                ImportItem.status == "pending",
                (ImportItem.status == "error") & (ImportItem.attempts < MAX_ATTEMPTS),
                (ImportItem.status == "downloading") & (ImportItem.locked_at < ahora - STALE_AFTER)))


async def claim_batch(db: AsyncSession, organization_id: uuid.UUID, size: int = BATCH_SIZE,
                      now: datetime | None = None) -> list[ImportItem]:
    """Reserva un lote (`FOR UPDATE SKIP LOCKED`: dos procesos no toman lo mismo)."""
    ahora = now or _now()
    stmt = (
        select(ImportItem)
        .where(*_elegibles(organization_id, ahora))
        .order_by(ImportItem.created_at, ImportItem.id).limit(size).with_for_update(skip_locked=True)
    )
    items = list((await db.execute(stmt)).scalars().all())
    for it in items:
        it.status, it.locked_at, it.attempts = "downloading", ahora, (it.attempts or 0) + 1
    await db.commit()
    return items


async def pending_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    return (await db.execute(select(func.count(ImportItem.id)).where(
        ImportItem.organization_id == organization_id, ImportItem.source == SOURCE,
        ImportItem.kind.in_(KINDS), or_(
            ImportItem.status == "pending",
            (ImportItem.status == "error") & (ImportItem.attempts < MAX_ATTEMPTS),
            ImportItem.status == "downloading")))).scalar_one()


async def _fetch(http: httpx.AsyncClient, url: str) -> bytes:
    """GET con tope de tamaño. 403/404 → `_Gone` (el llamador intenta renovar)."""
    async with http.stream("GET", url, follow_redirects=True) as r:
        if r.status_code in (403, 404, 410):
            raise _Gone(r.status_code)
        r.raise_for_status()
        largo = r.headers.get("content-length")
        if largo and largo.isdigit() and int(largo) > MAX_BYTES:
            raise _TooLarge()
        partes, total = [], 0
        async for trozo in r.aiter_bytes():
            total += len(trozo)
            if total > MAX_BYTES:
                raise _TooLarge()
            partes.append(trozo)
    return b"".join(partes)


async def _download(item: ImportItem, http: httpx.AsyncClient, client: CompanyCamClient | None) -> bytes | None:
    """Los bytes, o None si el elemento ya no existe en CompanyCam."""
    try:
        if not item.remote_url:
            raise _Gone("sin url")
        return await _fetch(http, item.remote_url)
    except _Gone:
        pass
    if client is None:
        return None
    if item.kind == "photo":
        nueva = await client.refresh_photo_url(item.external_id)
    else:
        nueva = await client.refresh_document_url(str((item.payload or {}).get("project_id")), item.external_id)
    if not nueva:
        return None
    item.remote_url = nueva
    try:
        return await _fetch(http, nueva)
    except _Gone:
        return None


def _resolve_mime(item: ImportItem, data: bytes) -> str:
    """Tipo real por contenido (no se confía en lo declarado) y permitido."""
    if item.kind == "document":
        declarado = ((item.payload or {}).get("content_type") or "").lower().strip()
    else:
        declarado = _MIME_BY_FAMILY.get(sniff_mime(data) or "", "")
    return check_type(data, declarado, PHOTO_MIME if item.kind == "photo" else DOC_MIME)


async def _thumbnail(item: ImportItem, http: httpx.AsyncClient, data: bytes) -> str | None:
    """Miniatura liviana para la cuadrícula: la versión `web` de CompanyCam o,
    si no se puede bajar, una reducida con Pillow. Nunca hace fallar la descarga."""
    web = (item.payload or {}).get("web_url")
    miniatura: bytes | None = None
    if web:
        try:
            miniatura = await _fetch(http, web)
            if sniff_mime(miniatura) not in ("jpeg", "png", "webp"):
                miniatura = None
        except Exception:
            miniatura = None
    if miniatura is None:
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as im:
                im = im.convert("RGB")
                im.thumbnail((THUMB_SIZE, THUMB_SIZE))
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=75)
                miniatura = buf.getvalue()
        except Exception:
            return None
    try:
        return storage.save_bytes(organization_id=item.organization_id,
                                  subfolder=f"cases/{item.case_id}/companycam",
                                  filename=f"thumb-{item.external_id}.jpg", data=miniatura)
    except Exception:
        return None


async def _release(db: AsyncSession, item_id: uuid.UUID, error: str) -> None:
    """Devuelve a `pending` un elemento reservado que no se procesó (sin gastar un intento)."""
    it = await db.get(ImportItem, item_id, populate_existing=True)
    if it is None:
        return
    it.status, it.locked_at, it.last_error = "pending", None, error
    it.attempts = max(0, (it.attempts or 1) - 1)
    await db.commit()


async def process_item(db: AsyncSession, item_id: uuid.UUID, http: httpx.AsyncClient,
                       client: CompanyCamClient | None) -> str:
    """Baja un elemento y lo deja guardado. Devuelve su estado final. Recibe el
    id y lo vuelve a leer: un `rollback` anterior deja vencidos los objetos.
    Si el disco tiene poco espacio libre, devuelve el elemento a `pending` y
    lanza `DiskFull` para que se detenga la cola."""
    item = await db.get(ImportItem, item_id, populate_existing=True)
    if item is None:  # lo borró una reversa mientras estaba reservado
        return "gone"
    if free_bytes() < min_free_bytes():
        await _release(db, item_id, f"Disco casi lleno: quedan menos de {get_settings().COMPANYCAM_MIN_FREE_GB:g} GB libres")
        raise DiskFull()
    payload = item.payload or {}
    if item.kind == "document":
        decl = (payload.get("content_type") or "").lower().strip()
        if decl not in DOC_MIME:  # ni se baja: ahorra ancho de banda
            item.status, item.locked_at, item.last_error = "skipped_type", None, f"Tipo no permitido: {decl or '?'}"
            await db.commit()
            return item.status
    ruta = miniatura = None
    try:
        data = await _download(item, http, client)
        if data is None:
            item.status, item.locked_at, item.last_error = "gone", None, "Ya no existe en CompanyCam"
            await db.commit()
            return item.status
        try:
            mime = _resolve_mime(item, data)
        except InvalidInputError as exc:
            item.status, item.locked_at, item.last_error = "skipped_type", None, str(exc)[:500]
            await db.commit()
            return item.status
        nombre = payload.get("name") if item.kind == "document" else f"companycam-{item.external_id}.{_EXT[mime]}"
        nombre = (nombre or f"companycam-{item.external_id}")[:255]
        ruta = storage.save_bytes(organization_id=item.organization_id, subfolder=f"cases/{item.case_id}/companycam",
                                  filename=nombre[:200], data=data)
        if item.kind == "photo":
            miniatura = await _thumbnail(item, http, data)
        capturado = payload.get("captured_at") or payload.get("created_at")
        archivo = CaseFile(
            organization_id=item.organization_id, case_id=item.case_id,
            field_key="companycam_photo" if item.kind == "photo" else "companycam_document",
            file_path=ruta, original_filename=nombre, mime_type=mime, size_bytes=len(data),
            latitude=payload.get("latitude"), longitude=payload.get("longitude"),
            captured_at=datetime.fromtimestamp(int(capturado), tz=timezone.utc) if capturado else None,
            watermarked=False, uploaded_by_user_id=None, review_status="accepted", review_notes=REVIEW_NOTE,
            label=(payload.get("name") or "")[:255] or None, external_ref=item.external_id,
            author_name=payload.get("author_name"), tags=payload.get("tags") or None,
        )
        db.add(archivo)
        await db.flush()
        item.case_file_id, item.status = archivo.id, "downloaded"
        if miniatura:
            item.payload = {**payload, "thumb_path": miniatura}
        item.downloaded_at, item.locked_at, item.last_error = _now(), None, None
        await db.commit()
        return "downloaded"
    except _TooLarge:
        await db.rollback()
        return await _fail(db, item_id, "Supera el tope de 25 MB", final=True)
    except Exception as exc:
        await db.rollback()
        _borrar(ruta)  # si el commit falló no se deja el archivo huérfano
        _borrar(miniatura)
        return await _fail(db, item_id, f"{type(exc).__name__}: {exc}"[:500])


def _borrar(ruta: str | None) -> None:
    if ruta:
        try:
            storage.absolute_path(ruta).unlink(missing_ok=True)
        except OSError:
            pass


async def _fail(db: AsyncSession, item_id: uuid.UUID, error: str, final: bool = False) -> str:
    fresh = await db.get(ImportItem, item_id, populate_existing=True)
    if fresh is None:  # lo borró una reversa en medio de la descarga
        return "gone"
    fresh.status, fresh.locked_at, fresh.last_error = "error", None, error
    if final:
        fresh.attempts = MAX_ATTEMPTS
    await db.commit()
    return "error"


async def process_batch(db: AsyncSession, organization_id: uuid.UUID, *, http: httpx.AsyncClient | None = None,
                        client: CompanyCamClient | None = None, size: int = BATCH_SIZE,
                        budget_seconds: float = BATCH_BUDGET_SECONDS) -> dict:
    """Un lote completo de una organización. Se corta solo al pasar el
    presupuesto de tiempo o si el disco se llena; lo no procesado vuelve a
    `pending`. Devuelve conteos por resultado y cuántos quedan."""
    propio = http is None
    http = http or httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    resultados: dict[str, int] = {}
    inicio = time.monotonic()
    try:
        ids = [it.id for it in await claim_batch(db, organization_id, size)]
        for n, item_id in enumerate(ids):
            if time.monotonic() - inicio > budget_seconds:
                for resto in ids[n:]:
                    await _release(db, resto, None)
                break
            try:
                estado = await process_item(db, item_id, http, client)
            except DiskFull:
                for resto in ids[n + 1:]:
                    await _release(db, resto, "Disco casi lleno: cola detenida")
                resultados["disk_full"] = 1
                break
            resultados[estado] = resultados.get(estado, 0) + 1
    finally:
        if propio:
            await http.aclose()
    # Con el disco lleno no se reencola: se reanuda a mano al liberar espacio.
    resultados["remaining"] = 0 if resultados.get("disk_full") else await pending_count(db, organization_id)
    return resultados


async def status(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, dict[str, int]]:
    filas = (await db.execute(select(ImportItem.kind, ImportItem.status, func.count()).where(
        ImportItem.organization_id == organization_id, ImportItem.source == SOURCE)
        .group_by(ImportItem.kind, ImportItem.status))).all()
    out: dict[str, dict[str, int]] = {}
    for kind, st, n in filas:
        out.setdefault(kind, {})[st] = n
    return out


async def retry_errors(db: AsyncSession, organization_id: uuid.UUID) -> int:
    items = (await db.execute(select(ImportItem).where(
        ImportItem.organization_id == organization_id, ImportItem.source == SOURCE,
        ImportItem.status.in_(("error", "gone"))))).scalars().all()
    for it in items:
        it.status, it.attempts, it.locked_at = "pending", 0, None
    await db.commit()
    return len(items)


async def purge(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Borra del disco los binarios de lo importado (de esta organización) que
    ya no tiene expediente: los `case_files` se van en cascada con el
    expediente, el archivo no. Tolera subcarpetas dentro de `companycam/`."""
    org_dir = storage.absolute_path(str(organization_id)) / "cases"
    if not org_dir.is_dir():
        return 0
    vivos = {str(i) for (i,) in (await db.execute(select(Case.id).where(
        Case.organization_id == organization_id))).all()}
    borrados = 0
    for caso in org_dir.iterdir():
        carpeta = caso / "companycam"
        if caso.name in vivos or not carpeta.is_dir():
            continue
        borrados += sum(1 for f in carpeta.rglob("*") if f.is_file())
        shutil.rmtree(carpeta, ignore_errors=True)
        try:
            caso.rmdir()
        except OSError:
            pass
    return borrados
