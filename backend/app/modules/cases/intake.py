"""Lo que el vendedor hace en la puerta (módulo 2, spec
`2026-10-04-modulo-2-vendedor-design.md`): visita, programa, formulario paso
a paso, archivos, términos con firma y envío a revisión.

El formulario lo define el módulo 1 (versión publicada del programa) y lo
evalúa `programs/engine.py`: la pantalla y el envío dicen lo mismo.
"""
import base64
import binascii
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import (
    VISIT_RESULTS,
    VISIT_STEP,
    Case,
    CaseFile,
    CaseStepSubmission,
    CaseTermsAcceptance,
    ProgramVersion,
)
from app.modules.programs import engine
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError
from app.shared.normalize import normalize_address, normalize_phone

RESULT_TO_STAGE = {"no_contact": "no_contact", "not_interested": "not_interested",
                   "not_eligible": "not_eligible", "opened": "new_prospect"}
EARLY_CLOSES = {"no_contact", "not_interested", "not_eligible"}
MEDIA_TYPES = {"photo", "document", "video", "signature"}
ALLOWED_MIME = {
    "photo": {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"},
    "document": {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"},
    "video": {"video/mp4", "video/quicktime", "video/webm"},
    "signature": {"image/png"},
}
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_FILES_PER_CASE = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _perms(user) -> set[str]:
    return get_effective_permissions(user)


def _require_owner(user, case: Case) -> None:
    """Mismo criterio que el router de José: lo ajeno responde 404."""
    if "cases.read_all" in _perms(user):
        return
    if case.assigned_salesperson_id != user.id:
        raise NotFoundError("El expediente no existe.", code="case_not_found")


def sees_sensitive(user, case: Case) -> bool:
    """Respuestas sensibles (§17.3): quien tiene el permiso o el vendedor que las captura."""
    return "fields.view_sensitive" in _perms(user) or case.assigned_salesperson_id == user.id


def sees_sensitive_files(user, case: Case) -> bool:
    """Archivos de campos sensibles (p. ej. foto del ID): además, quien revisa documentos."""
    return sees_sensitive(user, case) or "documents.review" in _perms(user)


async def sensitive_keys(db, case: Case) -> set[str]:
    if case.program_version_id is None:
        return set()
    definicion = await _definition(db, case)
    return {c["key"] for s in definicion["steps"] for c in s["fields"] if c.get("sensitive")}


def is_editable(case: Case) -> bool:
    return case.stage_code == "new_prospect" or (
        case.stage_code == "pending_approval" and case.substatus_code == "returned"
    )


def _require_editable(case: Case) -> None:
    if not is_editable(case):
        raise ConflictError(
            f"El expediente está en «{case.stage_label}»: el formulario ya no se edita "
            "(se corrige cuando Administración lo devuelve).",
            code="case_not_editable",
        )


async def _get_case(db, organization_id, case_id) -> Case:
    return await case_service.get_case_or_404(db, organization_id=organization_id, case_id=case_id)


# ---------------------------------------------------------------------------
# Visita (D2.1)
# ---------------------------------------------------------------------------

async def record_visit(db: AsyncSession, *, organization_id, user, data: dict) -> tuple[Case, str]:
    """Registra un toque de puerta. Devuelve el expediente y qué pasó:
    `created`, `reopened`, `updated`, `recorded` (sin cambio de etapa) o
    `in_progress` (la puerta ya va más adelante)."""
    resultado = data.get("result")
    if resultado not in VISIT_RESULTS:
        raise InvalidInputError("Elige qué pasó en la puerta.", code="invalid_visit_result")
    if not (data.get("address_street") or "").strip():
        raise InvalidInputError("Escribe la dirección de la puerta.", code="visit_address_required")
    destino = RESULT_TO_STAGE[resultado]
    normal = normalize_address(data.get("address_street"), data.get("address_unit"), data.get("address_city"),
                               data.get("address_zip"))
    case = (await db.execute(
        select(Case).where(Case.organization_id == organization_id, Case.normalized_address == normal,
                           Case.stage_code != "closed").order_by(Case.created_at.desc())
    )).scalars().first()

    if case is None:
        case = await case_service.create_case(
            db, organization_id=organization_id, actor_id=user.id, stage_code=destino,
            **{k: data.get(k) for k in ("address_street", "address_unit", "address_city", "address_state",
                                         "address_zip", "latitude", "longitude")},
        )
        que = "created"
    else:
        if case.assigned_salesperson_id not in (None, user.id) and "cases.read_all" not in _perms(user):
            raise ConflictError("Esta puerta ya tiene expediente con otro vendedor.", code="door_taken")
        if case.stage_code in EARLY_CLOSES and destino != case.stage_code \
                and stages.is_allowed(case.stage_code, destino):
            case = await case_service.transition(
                db, case=case, to_stage=destino, actor_id=user.id, actor_permissions=_perms(user),
                reason=f"Visita: {VISIT_RESULTS[resultado]}",
            )
            que = "reopened" if destino == "new_prospect" else "updated"
        elif case.stage_code in EARLY_CLOSES or case.stage_code == "new_prospect":
            que = "recorded"
        else:
            que = "in_progress"

    db.add(CaseStepSubmission(
        organization_id=organization_id, case_id=case.id, version_id=case.program_version_id,
        step_code=VISIT_STEP, answers={"result": resultado, "notes": (data.get("notes") or "").strip() or None},
        submitted_by_user_id=user.id, submitted_at=_now(),
        latitude=data.get("latitude"), longitude=data.get("longitude"),
    ))
    await db.commit()
    if data.get("program_id") and case.stage_code == "new_prospect" and case.program_id is None:
        case = await set_program(db, organization_id=organization_id, user=user, case_id=case.id,
                                 program_id=data["program_id"], zone_id=data.get("zone_id"))
    domain_events.emit("case.visit_recorded", {"case_id": str(case.id), "organization_id": str(organization_id),
                                                "result": resultado})
    return await _get_case(db, organization_id, case.id), que


async def list_visits(db, case: Case) -> list[CaseStepSubmission]:
    return list((await db.execute(
        select(CaseStepSubmission).where(CaseStepSubmission.case_id == case.id,
                                         CaseStepSubmission.step_code == VISIT_STEP)
        .order_by(CaseStepSubmission.submitted_at)
    )).scalars().all())


# ---------------------------------------------------------------------------
# Programa (D2.4)
# ---------------------------------------------------------------------------

async def set_program(db, *, organization_id, user, case_id, program_id, zone_id=None) -> Case:
    from app.modules.cases.models import ProgramZone
    from app.modules.programs import service as programs

    case = await _get_case(db, organization_id, case_id)
    _require_owner(user, case)
    if case.stage_code != "new_prospect":
        raise ConflictError("El programa se elige mientras el expediente es «Nuevo prospecto».",
                            code="program_locked")
    if case.program_version_id and (await db.execute(select(CaseStepSubmission.id).where(
            CaseStepSubmission.case_id == case.id, CaseStepSubmission.step_code != VISIT_STEP))).first():
        raise ConflictError("Ya hay respuestas guardadas con este programa; no se cambia.",
                            code="program_has_answers")
    programa = await programs.get_program(db, organization_id=organization_id, program_id=program_id)
    if not programa.active:
        raise InvalidInputError("Ese programa no está activo.", code="program_inactive")
    version = await programs.published_version(db, organization_id=organization_id, program_id=programa.id)
    if version is None:
        raise ConflictError(f"{programa.name} todavía no tiene formulario publicado.", code="program_without_form")
    if zone_id:
        zona = await db.get(ProgramZone, zone_id)
        if zona is None or zona.organization_id != organization_id or zona.program_id != programa.id:
            raise InvalidInputError("La zona no es de ese programa.", code="invalid_zone")
        case.zone_id = zona.id
    case.program_id = programa.id
    case.program_version_id = version.id
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="cases.program_selected", entity_type="case", entity_id=str(case.id),
                             after_data={"program": programa.code, "version": version.version})
    await db.commit()
    return await _get_case(db, organization_id, case.id)


# ---------------------------------------------------------------------------
# Formulario
# ---------------------------------------------------------------------------

async def _version(db, case: Case) -> ProgramVersion:
    if not case.program_version_id:
        raise ConflictError("Elige primero el programa del expediente.", code="program_required")
    return await db.get(ProgramVersion, case.program_version_id)


async def _definition(db, case: Case) -> dict:
    from app.modules.programs.service import version_definition

    return await version_definition(db, await _version(db, case))


async def current_answers(db, case: Case) -> tuple[dict, dict]:
    """Las respuestas vigentes (el último registro de cada paso) unidas en un
    solo diccionario, y cuándo se guardó cada paso."""
    filas = (await db.execute(
        select(CaseStepSubmission).where(CaseStepSubmission.case_id == case.id,
                                         CaseStepSubmission.step_code != VISIT_STEP)
        .order_by(CaseStepSubmission.submitted_at)
    )).scalars().all()
    ultimos: dict[str, CaseStepSubmission] = {}
    for f in filas:
        ultimos[f.step_code] = f
    respuestas: dict = {}
    for f in ultimos.values():
        respuestas.update(f.answers or {})
    return respuestas, {code: f.submitted_at for code, f in ultimos.items()}


async def form_state(db, *, user, case: Case) -> dict:
    definicion = await _definition(db, case)
    respuestas, guardados = await current_answers(db, case)
    archivos = (await db.execute(select(CaseFile).where(CaseFile.case_id == case.id))).scalars().all()
    aceptacion = (await db.execute(
        select(CaseTermsAcceptance).where(CaseTermsAcceptance.case_id == case.id)
        .order_by(CaseTermsAcceptance.accepted_at.desc())
    )).scalars().first()
    terminos = None
    version = await _version(db, case)
    if version.terms_id:
        from app.modules.programs.models import ProgramTerms

        t = await db.get(ProgramTerms, version.terms_id)
        terminos = {"id": str(t.id), "version": t.version, "language": t.language, "title": t.title, "body": t.body}
    # Lo sensible solo lo ve quien tiene permiso (§17.3); el vendedor que lo
    # captura sí lo ve porque lo está escribiendo.
    sensibles = {c["key"] for s in definicion["steps"] for c in s["fields"] if c.get("sensitive")}
    if not sees_sensitive_files(user, case):
        archivos = [f for f in archivos if f.field_key not in sensibles]
    if not sees_sensitive(user, case):
        respuestas = {k: ("•••" if k in sensibles and v not in engine.EMPTY else v) for k, v in respuestas.items()}
    return {
        "definition": definicion,
        "answers": respuestas,
        "saved_at": {k: v.isoformat() for k, v in guardados.items()},
        "evaluation": engine.evaluate(definicion, respuestas),
        "files": [{"id": str(f.id), "field_key": f.field_key, "original_filename": f.original_filename,
                   "mime_type": f.mime_type, "watermarked": f.watermarked, "review_status": f.review_status,
                   "review_notes": f.review_notes} for f in archivos],
        "terms": terminos,
        "acceptance": {"id": str(aceptacion.id), "customer_name": aceptacion.customer_name,
                       "accepted_at": aceptacion.accepted_at.isoformat(),
                       "terms_version": aceptacion.terms_version} if aceptacion else None,
        "editable": is_editable(case),
    }


async def save_step(db, *, organization_id, user, case_id, step_code, answers: dict,
                    latitude=None, longitude=None) -> Case:
    """Guarda las respuestas de un paso como un registro nuevo (D2.2). Se
    puede guardar incompleto; lo que no se acepta es un valor mal formado ni
    una clave que no pertenezca al paso."""
    case = await _get_case(db, organization_id, case_id)
    _require_owner(user, case)
    _require_editable(case)
    definicion = await _definition(db, case)
    paso = next((s for s in definicion["steps"] if s["code"] == step_code), None)
    if paso is None:
        raise NotFoundError("Ese paso no está en el formulario del programa.", code="step_not_found")
    campos = {c["key"]: c for c in paso["fields"]}
    ajenas = set(answers) - set(campos)
    if ajenas:
        raise InvalidInputError(f"Estas respuestas no son de este paso: {', '.join(sorted(ajenas))}.",
                                code="answers_not_in_step")
    errores = {}
    for key, valor in answers.items():
        campo = campos[key]
        if campo["type"] in MEDIA_TYPES and valor not in engine.EMPTY:
            await _require_file(db, case, key, valor)
            continue
        error = engine.validate_value(campo, valor)
        if error:
            errores[campo["label"]] = error
    if errores:
        raise InvalidInputError("Revisa: " + "; ".join(f"{k}: {v}" for k, v in errores.items()),
                                code="invalid_answers")
    anteriores, _ = await current_answers(db, case)
    previas_paso = {k: anteriores[k] for k in campos if k in anteriores}
    nuevas = {**previas_paso, **answers}
    db.add(CaseStepSubmission(
        organization_id=organization_id, case_id=case.id, version_id=case.program_version_id, step_code=step_code,
        answers=nuevas, submitted_by_user_id=user.id, submitted_at=_now(), latitude=latitude, longitude=longitude,
    ))
    await _apply_bindings(db, case, campos, nuevas)
    await db.commit()
    return await _get_case(db, organization_id, case.id)


async def _require_file(db, case, key, valor) -> None:
    try:
        file_id = uuid.UUID(str(valor))
    except ValueError:
        raise InvalidInputError("El archivo adjunto no es válido.", code="invalid_file_reference") from None
    f = await db.get(CaseFile, file_id)
    if f is None or f.case_id != case.id or f.field_key != key:
        raise InvalidInputError("El archivo no corresponde a este campo del expediente.", code="file_not_in_case")


async def _apply_bindings(db, case: Case, campos: dict, respuestas: dict) -> None:
    """Escritura híbrida (D2.3): lo que tiene destino va también a datos reales."""
    from app.modules.crm.models import Customer

    cliente_datos, direccion = {}, {}
    for key, campo in campos.items():
        destino, valor = campo.get("binding"), respuestas.get(key)
        if not destino or valor in engine.EMPTY:
            continue
        tabla, columna = destino.split(".", 1)
        (cliente_datos if tabla == "customer" else direccion)[columna] = str(valor).strip()

    for columna, valor in direccion.items():
        setattr(case, columna, valor)
    if direccion:
        case.normalized_address = normalize_address(case.address_street, case.address_unit, case.address_city,
                                                    case.address_zip)

    if not cliente_datos:
        return
    if case.customer_id:
        cliente = await db.get(Customer, case.customer_id)
        # Al cliente que nació con este expediente se le corrige todo. A uno
        # que ya existía (enlazado por teléfono u otro expediente) solo se le
        # completan datos vacíos: escribir un número ajeno no le cambia los
        # datos a otro cliente.
        otros = (await db.execute(select(Case.id).where(Case.customer_id == cliente.id, Case.id != case.id)
                                  .limit(1))).first()
        propio = otros is None and cliente.created_at is not None and case.created_at is not None \
            and cliente.created_at >= case.created_at
        for columna, valor in cliente_datos.items():
            if propio or getattr(cliente, columna) in (None, ""):
                setattr(cliente, columna, valor)
        return
    if not cliente_datos.get("legal_name"):
        return
    telefono = normalize_phone(cliente_datos.get("main_phone"))
    existente = None
    if telefono:
        candidatos = (await db.execute(select(Customer).where(
            Customer.organization_id == case.organization_id, Customer.main_phone.is_not(None),
            Customer.main_phone.like(f"%{telefono[-4:]}")))).scalars().all()
        existente = next((c for c in candidatos if normalize_phone(c.main_phone) == telefono), None)
    if existente is None:
        existente = Customer(organization_id=case.organization_id, **cliente_datos)
        db.add(existente)
        await db.flush()
    case.customer_id = existente.id


# ---------------------------------------------------------------------------
# Archivos (D2.5)
# ---------------------------------------------------------------------------

async def upload_file(db, *, organization_id, user, case_id, field_key, filename, content_type, data: bytes,
                      latitude=None, longitude=None, captured_at=None) -> CaseFile:
    from app.shared.files.storage import save_bytes
    from app.shared.files.watermark import apply_gps_watermark, apply_video_watermark

    case = await _get_case(db, organization_id, case_id)
    _require_owner(user, case)
    _require_editable(case)
    definicion = await _definition(db, case)
    campo = next((c for s in definicion["steps"] for c in s["fields"] if c["key"] == field_key), None)
    if campo is None or campo["type"] not in MEDIA_TYPES:
        raise InvalidInputError("Ese campo no recibe archivos.", code="field_not_media")
    from app.shared.files.validation import check_type

    mime = check_type(data, content_type, ALLOWED_MIME[campo["type"]])
    if len(data) > MAX_FILE_BYTES:
        raise InvalidInputError("El archivo supera el límite de 15 MB.", code="file_too_large")
    total = len((await db.execute(select(CaseFile.id).where(CaseFile.case_id == case.id))).all())
    if total >= MAX_FILES_PER_CASE:
        raise InvalidInputError("El expediente llegó al máximo de archivos.", code="too_many_files")
    marcado = False
    momento = captured_at or _now()
    if campo["type"] == "photo" or (campo["type"] == "document" and mime.startswith("image/")):
        try:
            data, mime, marcado = apply_gps_watermark(data, latitude=latitude, longitude=longitude,
                                                      captured_at=momento), "image/jpeg", True
        except Exception:
            marcado = False
    elif campo["type"] == "video":
        try:
            data, mime, marcado = apply_video_watermark(data, latitude=latitude, longitude=longitude,
                                                        captured_at=momento), "video/mp4", True
        except Exception:
            raise InvalidInputError("El video no se pudo procesar. Graba otro.", code="invalid_video") from None
    ruta = save_bytes(organization_id=organization_id, subfolder=f"cases/{case.id}", filename=filename or field_key,
                      data=data)
    f = CaseFile(organization_id=organization_id, case_id=case.id, field_key=field_key, file_path=ruta,
                 original_filename=filename, mime_type=mime, size_bytes=len(data), latitude=latitude,
                 longitude=longitude, captured_at=momento, watermarked=marcado, uploaded_by_user_id=user.id)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


async def get_file(db, *, organization_id, user, file_id) -> CaseFile:
    f = await db.get(CaseFile, file_id)
    if f is None or f.organization_id != organization_id:
        raise NotFoundError("El archivo no existe.", code="file_not_found")
    case = await _get_case(db, organization_id, f.case_id)
    _require_owner(user, case)
    if not sees_sensitive_files(user, case) and f.field_key in await sensitive_keys(db, case):
        raise NotFoundError("El archivo no existe.", code="file_not_found")
    return f


# ---------------------------------------------------------------------------
# Términos y firma (D2.6)
# ---------------------------------------------------------------------------

async def accept_terms(db, *, organization_id, user, case_id, customer_name: str, signature: str,
                       latitude=None, longitude=None, ip_address=None, user_agent=None) -> Case:
    from app.modules.programs.models import ProgramTerms
    from app.shared.files.storage import save_bytes

    case = await _get_case(db, organization_id, case_id)
    _require_owner(user, case)
    _require_editable(case)
    version = await _version(db, case)
    terminos = await db.get(ProgramTerms, version.terms_id) if version.terms_id else None
    if terminos is None:
        raise ConflictError("Este programa no tiene términos publicados.", code="terms_missing")
    nombre = (customer_name or "").strip()
    if len(nombre) < 3:
        raise InvalidInputError("Escribe el nombre de quien firma.", code="signer_name_required")
    try:
        crudo = signature.split(",", 1)[1] if signature.strip().startswith("data:") else signature
        png = base64.b64decode(crudo, validate=True)
    except (binascii.Error, ValueError, IndexError):
        raise InvalidInputError("La firma no es válida. Firma de nuevo.", code="invalid_signature") from None
    if not png.startswith(b"\x89PNG") or len(png) < 200:
        raise InvalidInputError("La firma está vacía. Pídele al cliente que firme en el recuadro.",
                                code="empty_signature")
    ruta = save_bytes(organization_id=organization_id, subfolder=f"cases/{case.id}", filename="firma-cliente.png",
                      data=png)
    ahora = _now()
    aceptacion = CaseTermsAcceptance(
        organization_id=organization_id, case_id=case.id, terms_id=terminos.id, terms_version=terminos.version,
        terms_language=terminos.language, customer_name=nombre, signature_path=ruta, accepted_at=ahora,
        salesperson_user_id=user.id, latitude=latitude, longitude=longitude, ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(aceptacion)
    await db.flush()
    # El paso de autorización queda completo con la misma aceptación.
    definicion = await _definition(db, case)
    paso = next((s for s in definicion["steps"] if any(c["type"] == "terms_checkbox" for c in s["fields"])), None)
    if paso:
        valores = {}
        for c in paso["fields"]:
            if c["type"] == "terms_checkbox":
                valores[c["key"]] = True
            elif c["type"] == "signature":
                valores[c["key"]] = str(aceptacion.id)
            elif c["type"] == "system_datetime":
                valores[c["key"]] = ahora.isoformat()
            elif c["key"] == "authorization.customer_name":
                valores[c["key"]] = nombre
        anteriores, _ = await current_answers(db, case)
        db.add(CaseStepSubmission(
            organization_id=organization_id, case_id=case.id, version_id=case.program_version_id,
            step_code=paso["code"],
            answers={**{k: anteriores[k] for k in (c["key"] for c in paso["fields"]) if k in anteriores}, **valores},
            submitted_by_user_id=user.id, submitted_at=ahora, latitude=latitude, longitude=longitude,
        ))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="cases.terms_accepted", entity_type="case", entity_id=str(case.id),
                             after_data={"terms_version": terminos.version, "language": terminos.language})
    await db.commit()
    return await _get_case(db, organization_id, case.id)


# ---------------------------------------------------------------------------
# Envío (D2.7)
# ---------------------------------------------------------------------------

async def submit(db, *, organization_id, user, case_id) -> Case:
    case = await _get_case(db, organization_id, case_id)
    _require_owner(user, case)
    _require_editable(case)
    definicion = await _definition(db, case)
    respuestas, _ = await current_answers(db, case)
    evaluacion = engine.evaluate(definicion, respuestas)
    if not evaluacion["can_submit"]:
        faltan = [m["label"] for m in evaluacion["missing"]]
        mal = [f"{k}: {v}" for k, v in evaluacion["errors"].items()]
        raise InvalidInputError("No se puede enviar. " + " ".join(filter(None, [
            ("Falta: " + "; ".join(faltan) + ".") if faltan else "",
            ("Revisa: " + "; ".join(mal) + ".") if mal else "",
        ])), code="case_incomplete")
    if case.customer_id is None:
        raise InvalidInputError("Falta el cliente: completa sus datos.", code="customer_required")
    from app.modules.cases.documents import unresolved

    if (await unresolved(db, case))["rejected"]:
        raise InvalidInputError("Reemplaza los documentos rechazados antes de volver a enviar.",
                                code="documents_rejected")
    reenvio = case.stage_code == "pending_approval"
    if reenvio:
        case = await case_service.set_substatus(db, case=case, substatus="pending_review", actor_id=user.id,
                                                actor_permissions=_perms(user), reason="Corregido y reenviado")
    else:
        case = await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=user.id,
                                             actor_permissions=_perms(user), substatus="pending_review",
                                             reason="Enviado a revisión por el vendedor")
    domain_events.emit("case.submitted", {"case_id": str(case.id), "organization_id": str(organization_id),
                                          "resubmitted": reenvio})
    return case


# ---------------------------------------------------------------------------
# Tablero (kanban)
# ---------------------------------------------------------------------------

async def board(db, *, organization_id, user, include_early_closes=False, mine=False, limit_per_stage=50) -> list[dict]:
    from app.modules.cases.models import Program
    from app.modules.crm.models import Customer

    stmt = select(Case).where(Case.organization_id == organization_id).order_by(Case.updated_at.desc())
    # "Mi día" pide solo los propios aunque quien entre pueda ver todos.
    if mine or "cases.read_all" not in _perms(user):
        stmt = stmt.where(Case.assigned_salesperson_id == user.id)
    if not include_early_closes:
        stmt = stmt.where(Case.stage_code.not_in(EARLY_CLOSES))
    casos = list((await db.execute(stmt)).scalars().all())
    clientes = {c.id: c.legal_name for c in (await db.execute(select(Customer).where(
        Customer.id.in_({c.customer_id for c in casos if c.customer_id})))).scalars().all()}
    programas = {p.id: p.name for p in (await db.execute(select(Program).where(
        Program.id.in_({c.program_id for c in casos if c.program_id})))).scalars().all()}
    columnas = []
    for code in stages.STAGES:
        if not include_early_closes and code in EARLY_CLOSES:
            continue
        del_codigo = [c for c in casos if c.stage_code == code]
        columnas.append({
            "code": code, "label": stages.STAGE_LABELS[code], "count": len(del_codigo),
            "cases": [{"id": str(c.id), "case_number": c.case_number, "customer_name": clientes.get(c.customer_id),
                       "address": ", ".join(x for x in (c.address_street, c.address_unit, c.address_city) if x),
                       "program_name": programas.get(c.program_id), "substatus_code": c.substatus_code,
                       "updated_at": c.updated_at.isoformat() if c.updated_at else None}
                      for c in del_codigo[:limit_per_stage]],
        })
    return columnas
