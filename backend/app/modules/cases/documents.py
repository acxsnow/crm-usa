"""Documentos del expediente (módulo 3).

Los archivos los sube el vendedor en el formulario (módulo 2, `intake.py`).
Aquí Administración los revisa uno por uno: los acepta o los rechaza con una
nota, y puede agregar documentos que no salen de un campo del formulario
(por ejemplo una factura de luz que llegó por correo).

**Documentos vigentes:** de cada campo cuenta solo el archivo que la
respuesta vigente del paso tiene guardado. Si el vendedor reemplaza una foto,
la anterior queda en disco y en la base (no se borra nada), pero sale de la
lista y de la revisión. Los adicionales cuentan todos.

Un documento rechazado bloquea el reenvío del vendedor y la aprobación del
expediente hasta que lo reemplacen (guarda `guard_documents_reviewed`).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases import intake
from app.modules.cases.approval_clock import approval_wait, wait_context
from app.modules.cases.models import DOCUMENT_REVIEW_STATUSES, EXTRA_DOCUMENT_KEY, Case, CaseFile
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

# Etapas en las que Administración revisa: mientras el expediente espera su
# aprobación (incluida la lista de espera del programa).
REVIEW_STAGES = {"pending_approval", "on_hold"}
# Etapas en las que ya no se agregan documentos.
CLOSED_STAGES = {"closed", "no_contact", "not_interested", "not_eligible"}
EXTRA_MIME = intake.ALLOWED_MIME["document"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def current_files(db: AsyncSession, case: Case) -> list[CaseFile]:
    """Los archivos que hoy cuentan: el vigente de cada campo y los adicionales."""
    respuestas, _ = await intake.current_answers(db, case)
    vigentes = {str(v) for v in respuestas.values() if isinstance(v, str)}
    archivos = (await db.execute(select(CaseFile).where(CaseFile.case_id == case.id)
                                 .order_by(CaseFile.created_at))).scalars().all()
    return [f for f in archivos if f.field_key == EXTRA_DOCUMENT_KEY or str(f.id) in vigentes]


async def _labels(db, case: Case) -> dict[str, tuple[str, str]]:
    """field_key → (paso, etiqueta del campo), para mostrar cada documento."""
    if case.program_version_id is None:
        return {}
    definicion = await intake._definition(db, case)
    return {c["key"]: (s["title"], c["label"]) for s in definicion["steps"] for c in s["fields"]}


async def _reviewer_names(db, ids: set) -> dict:
    from app.modules.users.models import User

    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()}


async def list_documents(db: AsyncSession, case: Case, user=None) -> list[dict]:
    archivos = await current_files(db, case)
    if user is not None and not intake.sees_sensitive_files(user, case):
        sensibles = await intake.sensitive_keys(db, case)
        archivos = [f for f in archivos if f.field_key not in sensibles]
    etiquetas = await _labels(db, case)
    revisores = await _reviewer_names(db, {f.reviewed_by_user_id for f in archivos})
    salida = []
    for f in archivos:
        paso, etiqueta = etiquetas.get(f.field_key, ("Documentos adicionales", f.field_key))
        if f.field_key == EXTRA_DOCUMENT_KEY:
            paso, etiqueta = "Documentos adicionales", f.label or "Documento"
        salida.append({
            "id": str(f.id), "field_key": f.field_key, "step_title": paso, "label": etiqueta,
            "original_filename": f.original_filename, "mime_type": f.mime_type, "size_bytes": f.size_bytes,
            "watermarked": f.watermarked, "latitude": f.latitude, "longitude": f.longitude,
            "captured_at": f.captured_at.isoformat() if f.captured_at else None,
            "uploaded_at": f.created_at.isoformat() if f.created_at else None,
            "review_status": f.review_status, "review_label": DOCUMENT_REVIEW_STATUSES[f.review_status],
            "review_notes": f.review_notes, "reviewed_by": revisores.get(f.reviewed_by_user_id),
            "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None,
        })
    return salida


async def review(db: AsyncSession, *, organization_id, user, file_id: uuid.UUID, status: str,
                 notes: str | None) -> CaseFile:
    if status not in ("accepted", "rejected"):
        raise InvalidInputError("El documento se acepta o se rechaza.", code="invalid_review_status")
    notas = (notes or "").strip() or None
    if status == "rejected" and not notas:
        raise InvalidInputError("Explica por qué se rechaza: el vendedor lo verá para corregirlo.",
                                code="review_notes_required")
    f = await db.get(CaseFile, file_id)
    if f is None or f.organization_id != organization_id:
        raise NotFoundError("El archivo no existe.", code="file_not_found")
    case = await intake._get_case(db, organization_id, f.case_id)
    if case.stage_code not in REVIEW_STAGES:
        raise ConflictError(f"El expediente está en «{case.stage_label}»: sus documentos ya no se revisan.",
                            code="case_not_in_review")
    if f.id not in {x.id for x in await current_files(db, case)}:
        raise ConflictError("Ese archivo fue reemplazado; revisa el vigente.", code="file_superseded")
    antes = {"review_status": f.review_status, "review_notes": f.review_notes}
    f.review_status, f.review_notes = status, notas
    f.reviewed_by_user_id, f.reviewed_at = user.id, _now()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action=f"documents.{status}", entity_type="case_file", entity_id=str(f.id),
                             before_data=antes, after_data={"review_status": status, "review_notes": notas,
                                                            "case_id": str(case.id)})
    await db.commit()
    await db.refresh(f)
    return f


async def upload_extra(db: AsyncSession, *, organization_id, user, case_id, label: str, filename, content_type,
                       data: bytes, latitude=None, longitude=None) -> CaseFile:
    """Documento adicional que no sale de un campo del formulario. Lo sube
    quien tenga `documents.manage` mientras el expediente siga abierto."""
    from app.shared.files.storage import save_bytes
    from app.shared.files.validation import check_type
    from app.shared.files.watermark import apply_gps_watermark

    etiqueta = (label or "").strip()
    if not etiqueta:
        raise InvalidInputError("Ponle nombre al documento (por ejemplo «Factura de luz»).",
                                code="document_label_required")
    case = await intake._get_case(db, organization_id, case_id)
    intake._require_owner(user, case)
    if case.stage_code in CLOSED_STAGES:
        raise ConflictError(f"El expediente está en «{case.stage_label}»: ya no recibe documentos.",
                            code="case_closed")
    mime = check_type(data, content_type, EXTRA_MIME)
    total = len((await db.execute(select(CaseFile.id).where(CaseFile.case_id == case.id))).all())
    if total >= intake.MAX_FILES_PER_CASE:
        raise InvalidInputError("El expediente llegó al máximo de archivos.", code="too_many_files")
    marcado, momento = False, _now()
    if mime.startswith("image/"):
        try:
            data, mime, marcado = apply_gps_watermark(data, latitude=latitude, longitude=longitude,
                                                      captured_at=momento), "image/jpeg", True
        except Exception:
            marcado = False
    ruta = save_bytes(organization_id=organization_id, subfolder=f"cases/{case.id}", filename=filename or "documento",
                      data=data)
    f = CaseFile(organization_id=organization_id, case_id=case.id, field_key=EXTRA_DOCUMENT_KEY, label=etiqueta[:255],
                 file_path=ruta, original_filename=filename, mime_type=mime, size_bytes=len(data),
                 latitude=latitude, longitude=longitude, captured_at=momento, watermarked=marcado,
                 uploaded_by_user_id=user.id)
    db.add(f)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="documents.uploaded", entity_type="case", entity_id=str(case.id),
                             after_data={"label": etiqueta})
    await db.commit()
    await db.refresh(f)
    return f


async def review_queue(db: AsyncSession, *, organization_id) -> list[dict]:
    """Expedientes en revisión que tienen documentos por revisar o rechazados,
    los más antiguos primero (los que llevan más tiempo esperando)."""
    from app.modules.cases.models import Program
    from app.modules.crm.models import Customer

    # Solo los que tienen algún archivo pendiente o rechazado. Saber cuáles son
    # los vigentes exige leer las respuestas de cada expediente (una consulta
    # por expediente), así que primero se descartan en la base los que no
    # tienen nada por revisar: con 20.000 expedientes la cola tardaba 15 s
    # (prueba de carga, 11 oct 2026). El resultado no cambia: abajo se sigue
    # verificando con los archivos vigentes.
    por_revisar = select(CaseFile.id).where(CaseFile.case_id == Case.id,
                                            CaseFile.review_status.in_(("pending", "rejected")))
    casos = (await db.execute(
        select(Case).where(Case.organization_id == organization_id, Case.stage_code.in_(REVIEW_STAGES),
                           exists(por_revisar))
        .order_by(Case.submitted_at.asc().nulls_last(), Case.id)
    )).scalars().all()
    filas = []
    for c in casos:
        archivos = await current_files(db, c)
        cuenta = {k: sum(1 for f in archivos if f.review_status == k) for k in DOCUMENT_REVIEW_STATUSES}
        if not archivos or (cuenta["pending"] == 0 and cuenta["rejected"] == 0):
            continue
        filas.append((c, cuenta))
    clientes = {x.id: x.legal_name for x in (await db.execute(select(Customer).where(
        Customer.id.in_({c.customer_id for c, _ in filas if c.customer_id})))).scalars().all()}
    programas = {x.id: x.name for x in (await db.execute(select(Program).where(
        Program.id.in_({c.program_id for c, _ in filas if c.program_id})))).scalars().all()}
    reloj = await wait_context(db, organization_id)
    return [{"case_id": str(c.id), "case_number": c.case_number, "customer_name": clientes.get(c.customer_id),
             "program_name": programas.get(c.program_id), "stage_label": c.stage_label,
             "substatus_code": c.substatus_code,
             "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
             "pending": cuenta["pending"], "accepted": cuenta["accepted"], "rejected": cuenta["rejected"],
             "approval_wait": approval_wait(c, reloj)}
            for c, cuenta in filas]


async def unresolved(db: AsyncSession, case: Case) -> dict[str, int]:
    archivos = await current_files(db, case)
    return {"pending": sum(1 for f in archivos if f.review_status == "pending"),
            "rejected": sum(1 for f in archivos if f.review_status == "rejected")}


async def guard_documents_reviewed(*, db, case, actor_id, reason):
    """No se aprueba un expediente con documentos sin revisar o rechazados."""
    falta = await unresolved(db, case)
    if falta["rejected"]:
        raise InvalidInputError(
            f"Hay {falta['rejected']} documento(s) rechazado(s): devuelve el expediente al vendedor para que "
            "los reemplace antes de aprobar.", code="documents_rejected")
    if falta["pending"]:
        raise InvalidInputError(
            f"Faltan {falta['pending']} documento(s) por revisar antes de aprobar.", code="documents_pending")


_registrado = False


def register() -> None:
    global _registrado
    if _registrado:
        return
    from app.modules.cases import stages

    stages.register_guard("pending_approval", "approved", guard_documents_reviewed)
    stages.register_guard("on_hold", "approved", guard_documents_reviewed)
    _registrado = True


def _reset_for_tests() -> None:
    """Las pruebas vacían las guardas del motor; la bandera vuelve atrás."""
    global _registrado
    _registrado = False
