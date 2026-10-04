"""Programas, catálogo de campos, flujo versionado, T&C y zonas de venta
(módulo 1, spec `2026-10-04-modulo-1-programas-design.md`).

Regla central: una versión publicada no se edita (D1.3). Todo lo que cambia el
flujo pasa por `_draft_version`, que lo comprueba en un solo sitio.
"""
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases.models import Program, ProgramVersion, ProgramZone
from app.modules.programs import engine
from app.modules.programs.models import (
    BINDINGS,
    FIELD_TYPES,
    PHASE_ROLES,
    REQUIREMENT_LEVELS,
    SELECT_TYPES,
    FieldDefinition,
    ProgramTerms,
    WorkflowPhase,
    WorkflowStep,
    WorkflowStepField,
    ZoneAssignment,
)
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{2,100}$")
LANGUAGES = {"es": "Español", "en": "Inglés"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _owned(db, model, obj_id, organization_id, message, code):
    obj = (
        await db.execute(select(model).where(model.id == obj_id, model.organization_id == organization_id))
    ).scalar_one_or_none()
    if obj is None:
        raise NotFoundError(message, code=code)
    return obj


async def _audit(db, organization_id, user, action, entity_type, entity_id, data=None):
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id if user else None, action=action,
        entity_type=entity_type, entity_id=str(entity_id), after_data=data,
    )


# ---------------------------------------------------------------------------
# Programas
# ---------------------------------------------------------------------------

PROGRAM_FIELDS = ("name", "active", "description", "funder_name", "customer_facing_name", "logo_url",
                  "authorization_text", "invoice_entity")


async def list_programs(db: AsyncSession, *, organization_id) -> list[Program]:
    return list((await db.execute(
        select(Program).where(Program.organization_id == organization_id).order_by(Program.name)
    )).scalars().all())


async def get_program(db, *, organization_id, program_id) -> Program:
    return await _owned(db, Program, program_id, organization_id, "El programa no existe.", "program_not_found")


async def create_program(db, *, organization_id, user, data: dict) -> Program:
    code = (data.get("code") or "").strip().upper()
    if not CODE_RE.match(code):
        raise InvalidInputError("El código usa letras, números y guion bajo (ej. AZ_EFFICIENCY).",
                                code="invalid_program_code")
    if (await db.execute(select(Program.id).where(Program.organization_id == organization_id,
                                                  Program.code == code))).first():
        raise ConflictError(f"Ya existe un programa con el código {code}.", code="program_code_taken")
    program = Program(organization_id=organization_id, code=code,
                      **{k: data[k] for k in PROGRAM_FIELDS if data.get(k) is not None})
    db.add(program)
    await db.flush()
    await _audit(db, organization_id, user, "programs.created", "Program", program.id, {"code": code})
    await db.commit()
    await db.refresh(program)
    return program


async def update_program(db, *, organization_id, user, program_id, changes: dict) -> Program:
    """El código no cambia: reportes, cobros y expedientes lo usan."""
    program = await get_program(db, organization_id=organization_id, program_id=program_id)
    for k in PROGRAM_FIELDS:
        if k in changes:
            setattr(program, k, changes[k])
    await _audit(db, organization_id, user, "programs.updated", "Program", program.id,
                 {k: changes[k] for k in changes if k in PROGRAM_FIELDS})
    await db.commit()
    await db.refresh(program)
    return program


# ---------------------------------------------------------------------------
# T&C por versión e idioma (D1.5)
# ---------------------------------------------------------------------------

async def list_terms(db, *, organization_id, program_id) -> list[ProgramTerms]:
    await get_program(db, organization_id=organization_id, program_id=program_id)
    return list((await db.execute(
        select(ProgramTerms).where(ProgramTerms.organization_id == organization_id,
                                   ProgramTerms.program_id == program_id)
        .order_by(ProgramTerms.created_at)
    )).scalars().all())


async def create_terms(db, *, organization_id, user, program_id, data: dict) -> ProgramTerms:
    await get_program(db, organization_id=organization_id, program_id=program_id)
    idioma = data.get("language") or "es"
    if idioma not in LANGUAGES:
        raise InvalidInputError("El idioma es español (es) o inglés (en).", code="invalid_language")
    version = (data.get("version") or "").strip()
    if not version:
        raise InvalidInputError("Indica la versión de los términos (ej. 2026.1).", code="terms_version_required")
    if len((data.get("body") or "").strip()) < 20:
        raise InvalidInputError("Escribe el texto completo de los términos.", code="terms_body_required")
    existe = (await db.execute(select(ProgramTerms.id).where(
        ProgramTerms.program_id == program_id, ProgramTerms.version == version, ProgramTerms.language == idioma,
    ))).first()
    if existe:
        raise ConflictError(f"Ya existe la versión {version} en {LANGUAGES[idioma].lower()}.",
                            code="terms_version_taken")
    terms = ProgramTerms(organization_id=organization_id, program_id=program_id, version=version,
                         language=idioma, title=data.get("title") or "Términos y condiciones",
                         body=data["body"].strip())
    db.add(terms)
    await db.flush()
    await _audit(db, organization_id, user, "programs.terms_created", "ProgramTerms", terms.id,
                 {"version": version, "language": idioma})
    await db.commit()
    await db.refresh(terms)
    return terms


async def publish_terms(db, *, organization_id, user, terms_id) -> ProgramTerms:
    terms = await _owned(db, ProgramTerms, terms_id, organization_id, "Los términos no existen.", "terms_not_found")
    if terms.published_at:
        raise ConflictError("Estos términos ya están publicados.", code="terms_already_published")
    terms.published_at = _now()
    await _audit(db, organization_id, user, "programs.terms_published", "ProgramTerms", terms.id)
    await db.commit()
    await db.refresh(terms)
    return terms


async def update_terms(db, *, organization_id, user, terms_id, changes: dict) -> ProgramTerms:
    terms = await _owned(db, ProgramTerms, terms_id, organization_id, "Los términos no existen.", "terms_not_found")
    if terms.published_at:
        raise ConflictError("Unos términos publicados no se editan: crea una versión nueva.",
                            code="terms_published")
    for k in ("title", "body"):
        if changes.get(k):
            setattr(terms, k, changes[k])
    await db.commit()
    await db.refresh(terms)
    return terms


# ---------------------------------------------------------------------------
# Catálogo de campos (D1.2)
# ---------------------------------------------------------------------------

FIELD_EDITABLE = ("label", "help_text", "section", "options", "validation", "binding", "internal", "sensitive",
                  "active")


def _check_field(field_type: str, options, validation, binding) -> None:
    if field_type not in FIELD_TYPES:
        raise InvalidInputError(f"El tipo «{field_type}» no existe.", code="invalid_field_type")
    if field_type in SELECT_TYPES:
        if not options or not all(isinstance(o, dict) and o.get("value") and o.get("label") for o in options):
            raise InvalidInputError("Una selección necesita opciones con valor y etiqueta.",
                                    code="field_options_required")
        valores = [o["value"] for o in options]
        if len(valores) != len(set(valores)):
            raise InvalidInputError("Hay opciones repetidas.", code="field_options_duplicated")
        excl = set((validation or {}).get("exclusive") or [])
        if excl - set(valores):
            raise InvalidInputError("La opción excluyente tiene que estar entre las opciones.",
                                    code="invalid_exclusive_option")
    if binding is not None and binding not in BINDINGS:
        raise InvalidInputError(f"El destino «{binding}» no existe.", code="invalid_binding")


async def list_fields(db, *, organization_id, include_inactive: bool = True) -> list[FieldDefinition]:
    stmt = select(FieldDefinition).where(FieldDefinition.organization_id == organization_id)
    if not include_inactive:
        stmt = stmt.where(FieldDefinition.active.is_(True))
    return list((await db.execute(stmt.order_by(FieldDefinition.section, FieldDefinition.key))).scalars().all())


async def create_field(db, *, organization_id, user, data: dict) -> FieldDefinition:
    key = (data.get("key") or "").strip()
    if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$", key):
        raise InvalidInputError("La clave va en minúsculas con punto, como customer.full_name.",
                                code="invalid_field_key")
    _check_field(data.get("field_type"), data.get("options"), data.get("validation"), data.get("binding"))
    if (await db.execute(select(FieldDefinition.id).where(FieldDefinition.organization_id == organization_id,
                                                          FieldDefinition.key == key))).first():
        raise ConflictError(f"Ya existe el campo {key}.", code="field_key_taken")
    field = FieldDefinition(organization_id=organization_id, key=key, label=data["label"],
                            field_type=data["field_type"],
                            **{k: data[k] for k in FIELD_EDITABLE if k in data and k != "label"})
    db.add(field)
    await db.flush()
    await _audit(db, organization_id, user, "fields.created", "FieldDefinition", field.id, {"key": key})
    await db.commit()
    await db.refresh(field)
    return field


async def update_field(db, *, organization_id, user, field_id, changes: dict) -> FieldDefinition:
    """La clave y el tipo no cambian: las respuestas guardadas dependen de
    ellos. Se cambian etiqueta, opciones, reglas y marcas; para "borrar" se
    desactiva."""
    field = await _owned(db, FieldDefinition, field_id, organization_id, "El campo no existe.", "field_not_found")
    nuevo = {k: changes[k] for k in FIELD_EDITABLE if k in changes}
    _check_field(field.field_type, nuevo.get("options", field.options), nuevo.get("validation", field.validation),
                 nuevo.get("binding", field.binding))
    if "options" in nuevo and field.options:
        quitadas = {o["value"] for o in field.options} - {o["value"] for o in nuevo["options"] or []}
        if quitadas:
            raise ConflictError("No se pueden quitar opciones que ya pudieron responderse "
                                f"({', '.join(sorted(quitadas))}); cámbiales la etiqueta.",
                                code="field_option_removed")
    for k, v in nuevo.items():
        setattr(field, k, v)
    await _audit(db, organization_id, user, "fields.updated", "FieldDefinition", field.id, nuevo)
    await db.commit()
    await db.refresh(field)
    return field


# ---------------------------------------------------------------------------
# Versiones del flujo (D1.3)
# ---------------------------------------------------------------------------

async def list_versions(db, *, organization_id, program_id) -> list[ProgramVersion]:
    await get_program(db, organization_id=organization_id, program_id=program_id)
    return list((await db.execute(
        select(ProgramVersion).where(ProgramVersion.organization_id == organization_id,
                                     ProgramVersion.program_id == program_id)
        .order_by(ProgramVersion.created_at)
    )).scalars().all())


async def get_version(db, *, organization_id, version_id) -> ProgramVersion:
    return await _owned(db, ProgramVersion, version_id, organization_id, "La versión no existe.",
                        "version_not_found")


async def published_version(db, *, organization_id, program_id) -> ProgramVersion | None:
    return (await db.execute(select(ProgramVersion).where(
        ProgramVersion.organization_id == organization_id, ProgramVersion.program_id == program_id,
        ProgramVersion.status == "published",
    ))).scalar_one_or_none()


async def phases_of(db, version_id) -> list[WorkflowPhase]:
    return list((await db.execute(
        select(WorkflowPhase).where(WorkflowPhase.version_id == version_id).order_by(WorkflowPhase.sort_order)
        .execution_options(populate_existing=True)
    )).scalars().all())


async def _draft_version(db, organization_id, version_id) -> ProgramVersion:
    version = await get_version(db, organization_id=organization_id, version_id=version_id)
    if version.status != "draft":
        raise ConflictError("Una versión publicada o archivada no se edita: crea una versión nueva.",
                            code="version_not_draft")
    return version


async def create_version(db, *, organization_id, user, program_id) -> ProgramVersion:
    """Versión nueva en borrador. Copia la última (publicada o no) para que el
    cambio sea un ajuste y no empezar de cero; si no hay ninguna, nace con la
    fase Vendedor vacía."""
    await get_program(db, organization_id=organization_id, program_id=program_id)
    versiones = await list_versions(db, organization_id=organization_id, program_id=program_id)
    if any(v.status == "draft" for v in versiones):
        raise ConflictError("Este programa ya tiene una versión en borrador. Termínala o publícala.",
                            code="draft_exists")
    base = next((v for v in reversed(versiones) if v.status == "published"), versiones[-1] if versiones else None)
    nueva = ProgramVersion(organization_id=organization_id, program_id=program_id,
                           version=str(len(versiones) + 1), status="draft",
                           terms_id=base.terms_id if base else None)
    db.add(nueva)
    await db.flush()
    if base:
        await _copy_structure(db, base.id, nueva)
    else:
        db.add(WorkflowPhase(organization_id=organization_id, version_id=nueva.id, code="salesperson",
                             name="Vendedor", role_code="salesperson", sort_order=0))
    await _audit(db, organization_id, user, "workflows.version_created", "ProgramVersion", nueva.id,
                 {"version": nueva.version, "from": base.version if base else None})
    await db.commit()
    await db.refresh(nueva)
    return nueva


async def _copy_structure(db, origen_id, nueva: ProgramVersion) -> None:
    for fase in await phases_of(db, origen_id):
        f = WorkflowPhase(organization_id=nueva.organization_id, version_id=nueva.id, code=fase.code,
                          name=fase.name, role_code=fase.role_code, sort_order=fase.sort_order)
        db.add(f)
        await db.flush()
        for paso in fase.steps:
            p = WorkflowStep(organization_id=nueva.organization_id, phase_id=f.id, code=paso.code,
                             title=paso.title, description=paso.description, sort_order=paso.sort_order)
            db.add(p)
            await db.flush()
            for c in paso.fields:
                db.add(WorkflowStepField(organization_id=nueva.organization_id, step_id=p.id, field_id=c.field_id,
                                         requirement=c.requirement, condition=c.condition,
                                         label_override=c.label_override, help_override=c.help_override,
                                         sort_order=c.sort_order))


async def update_version(db, *, organization_id, user, version_id, changes: dict) -> ProgramVersion:
    version = await _draft_version(db, organization_id, version_id)
    if "terms_id" in changes:
        if changes["terms_id"] is not None:
            terms = await _owned(db, ProgramTerms, changes["terms_id"], organization_id,
                                 "Los términos no existen.", "terms_not_found")
            if terms.program_id != version.program_id:
                raise InvalidInputError("Esos términos son de otro programa.", code="terms_other_program")
        version.terms_id = changes["terms_id"]
    if "notes" in changes:
        version.notes = changes["notes"]
    await db.commit()
    await db.refresh(version)
    return version


async def publish_version(db, *, organization_id, user, version_id) -> ProgramVersion:
    """Congela la versión y archiva la publicada anterior. Antes revisa que
    se pueda llenar: cada paso con campos, condiciones bien formadas y que
    apunten a campos de la misma versión, y T&C publicados si el flujo pide
    aceptarlos."""
    version = await _draft_version(db, organization_id, version_id)
    problemas = await version_problems(db, version)
    if problemas:
        raise InvalidInputError("No se puede publicar: " + "; ".join(problemas) + ".", code="version_invalid")
    anterior = await published_version(db, organization_id=organization_id, program_id=version.program_id)
    if anterior:
        anterior.status = "archived"
    version.status = "published"
    version.published_at = _now()
    version.published_by_user_id = user.id
    await _audit(db, organization_id, user, "workflows.version_published", "ProgramVersion", version.id,
                 {"version": version.version, "archived": anterior.version if anterior else None})
    await db.commit()
    await db.refresh(version)
    return version


async def archive_version(db, *, organization_id, user, version_id) -> ProgramVersion:
    version = await get_version(db, organization_id=organization_id, version_id=version_id)
    if version.status == "archived":
        raise ConflictError("La versión ya está archivada.", code="version_archived")
    version.status = "archived"
    await _audit(db, organization_id, user, "workflows.version_archived", "ProgramVersion", version.id)
    await db.commit()
    await db.refresh(version)
    return version


async def version_problems(db, version: ProgramVersion) -> list[str]:
    definicion = await version_definition(db, version)
    problemas = []
    claves = {c["key"] for p in definicion["steps"] for c in p["fields"]}
    if not definicion["steps"]:
        problemas.append("la versión no tiene pasos")
    for paso in definicion["steps"]:
        if not paso["fields"]:
            problemas.append(f"el paso «{paso['title']}» no tiene campos")
        for c in paso["fields"]:
            if c["condition"]:
                error = engine.check_condition(c["condition"])
                if error:
                    problemas.append(f"«{c['label']}»: {error[0].lower()}{error[1:].rstrip('.')}")
                elif c["condition"]["field"] not in claves:
                    problemas.append(f"«{c['label']}» depende de {c['condition']['field']}, que no está en la versión")
            if c["requirement"] == "conditional" and not c["condition"]:
                problemas.append(f"«{c['label']}» es condicional pero no tiene condición")
    pide_terminos = any(c["type"] == "terms_checkbox" for p in definicion["steps"] for c in p["fields"])
    if pide_terminos:
        terms = await db.get(ProgramTerms, version.terms_id) if version.terms_id else None
        if terms is None or terms.published_at is None:
            problemas.append("el flujo pide aceptar los términos y la versión no tiene términos publicados")
    return problemas


async def version_definition(db, version: ProgramVersion) -> dict:
    """La definición que evalúa `engine.evaluate`: pasos en orden, cada uno con
    sus campos ya resueltos (etiqueta y ayuda propias del programa)."""
    pasos = []
    for fase in await phases_of(db, version.id):
        for paso in fase.steps:
            pasos.append({
                "id": str(paso.id), "code": paso.code, "title": paso.title, "description": paso.description,
                "phase": fase.code, "phase_name": fase.name, "role": fase.role_code,
                "fields": [{
                    "id": str(c.id), "field_id": str(c.field_id), "key": c.field.key,
                    "label": c.label_override or c.field.label, "help": c.help_override or c.field.help_text,
                    "type": c.field.field_type, "options": c.field.options, "validation": c.field.validation,
                    "binding": c.field.binding, "requirement": c.requirement, "condition": c.condition,
                    "internal": c.field.internal, "sensitive": c.field.sensitive,
                } for c in paso.fields],
            })
    return {"version_id": str(version.id), "program_id": str(version.program_id), "version": version.version,
            "status": version.status, "steps": pasos}


# --- Fases, pasos y campos del paso (solo en borrador) ------------------------

async def add_phase(db, *, organization_id, user, version_id, data) -> WorkflowPhase:
    version = await _draft_version(db, organization_id, version_id)
    if data.get("role_code") not in PHASE_ROLES:
        raise InvalidInputError("Elige el rol responsable de la fase.", code="invalid_phase_role")
    orden = len(await phases_of(db, version.id))
    fase = WorkflowPhase(organization_id=organization_id, version_id=version.id,
                         code=_slug(data.get("code") or data["name"]), name=data["name"],
                         role_code=data["role_code"], sort_order=orden)
    db.add(fase)
    await db.commit()
    await db.refresh(fase)
    return fase


async def add_step(db, *, organization_id, user, phase_id, data) -> WorkflowStep:
    fase = await _owned(db, WorkflowPhase, phase_id, organization_id, "La fase no existe.", "phase_not_found")
    await _draft_version(db, organization_id, fase.version_id)
    codigo = _slug(data.get("code") or data["title"])
    if any(p.code == codigo for p in fase.steps):
        raise ConflictError("Ya hay un paso con ese código en la fase.", code="step_code_taken")
    paso = WorkflowStep(organization_id=organization_id, phase_id=fase.id, code=codigo, title=data["title"],
                        description=data.get("description"), sort_order=len(fase.steps))
    db.add(paso)
    await db.commit()
    await db.refresh(paso)
    return paso


async def update_step(db, *, organization_id, user, step_id, changes) -> WorkflowStep:
    paso, _ = await _step_in_draft(db, organization_id, step_id)
    for k in ("title", "description"):
        if k in changes:
            setattr(paso, k, changes[k])
    await db.commit()
    await db.refresh(paso)
    return paso


async def delete_step(db, *, organization_id, user, step_id) -> None:
    paso, fase = await _step_in_draft(db, organization_id, step_id)
    await db.delete(paso)
    await db.flush()
    await _renumber(db, [p for p in fase.steps if p.id != paso.id])
    await db.commit()


async def move_step(db, *, organization_id, user, step_id, direction: str) -> None:
    paso, fase = await _step_in_draft(db, organization_id, step_id)
    _swap(list(fase.steps), paso, direction)
    await db.commit()


async def add_step_field(db, *, organization_id, user, step_id, data) -> WorkflowStepField:
    paso, fase = await _step_in_draft(db, organization_id, step_id)
    campo = await _owned(db, FieldDefinition, data["field_id"], organization_id, "El campo no existe.",
                         "field_not_found")
    if not campo.active:
        raise InvalidInputError("Ese campo está desactivado en el catálogo.", code="field_inactive")
    if any(c.field_id == campo.id for p in await _version_steps(db, fase.version_id) for c in p.fields):
        raise ConflictError(f"«{campo.label}» ya está en esta versión.", code="field_already_in_version")
    _check_step_field(data.get("requirement", "optional"), data.get("condition"))
    sf = WorkflowStepField(organization_id=organization_id, step_id=paso.id, field_id=campo.id,
                           requirement=data.get("requirement", "optional"), condition=data.get("condition"),
                           label_override=data.get("label_override"), help_override=data.get("help_override"),
                           sort_order=len(paso.fields))
    db.add(sf)
    await db.commit()
    await db.refresh(sf)
    return sf


async def update_step_field(db, *, organization_id, user, step_field_id, changes) -> WorkflowStepField:
    sf = await _step_field_in_draft(db, organization_id, step_field_id)
    requisito = changes.get("requirement", sf.requirement)
    condicion = changes["condition"] if "condition" in changes else sf.condition
    _check_step_field(requisito, condicion)
    for k in ("requirement", "condition", "label_override", "help_override"):
        if k in changes:
            setattr(sf, k, changes[k])
    await db.commit()
    await db.refresh(sf)
    return sf


async def delete_step_field(db, *, organization_id, user, step_field_id) -> None:
    sf = await _step_field_in_draft(db, organization_id, step_field_id)
    paso = await db.get(WorkflowStep, sf.step_id)
    await db.delete(sf)
    await db.flush()
    await _renumber(db, [c for c in paso.fields if c.id != sf.id])
    await db.commit()


async def move_step_field(db, *, organization_id, user, step_field_id, direction) -> None:
    sf = await _step_field_in_draft(db, organization_id, step_field_id)
    paso = await db.get(WorkflowStep, sf.step_id)
    _swap(list(paso.fields), sf, direction)
    await db.commit()


def _check_step_field(requirement, condition) -> None:
    if requirement not in REQUIREMENT_LEVELS:
        raise InvalidInputError("La obligatoriedad es obligatorio, opcional o condicional.",
                                code="invalid_requirement")
    if condition:
        error = engine.check_condition(condition)
        if error:
            raise InvalidInputError(error, code="invalid_condition")
    if requirement == "conditional" and not condition:
        raise InvalidInputError("Un campo condicional necesita la condición que lo muestra.",
                                code="condition_required")


async def _step_in_draft(db, organization_id, step_id):
    paso = await _owned(db, WorkflowStep, step_id, organization_id, "El paso no existe.", "step_not_found")
    fase = await db.get(WorkflowPhase, paso.phase_id)
    await _draft_version(db, organization_id, fase.version_id)
    return paso, fase


async def _step_field_in_draft(db, organization_id, step_field_id):
    sf = await _owned(db, WorkflowStepField, step_field_id, organization_id, "El campo del paso no existe.",
                      "step_field_not_found")
    await _step_in_draft(db, organization_id, sf.step_id)
    return sf


async def _version_steps(db, version_id) -> list[WorkflowStep]:
    return [p for f in await phases_of(db, version_id) for p in f.steps]


def _swap(items: list, item, direction: str) -> None:
    if direction not in ("up", "down"):
        raise InvalidInputError("La dirección es arriba o abajo.", code="invalid_direction")
    i = next(n for n, x in enumerate(items) if x.id == item.id)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(items):
        items[i].sort_order, items[j].sort_order = items[j].sort_order, items[i].sort_order


async def _renumber(db, items) -> None:
    for n, x in enumerate(sorted(items, key=lambda x: x.sort_order)):
        x.sort_order = n


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")[:50] or "paso"


# ---------------------------------------------------------------------------
# Zonas de venta y vendedores (D1.6)
# ---------------------------------------------------------------------------

async def list_zones(db, *, organization_id, program_id) -> list[ProgramZone]:
    await get_program(db, organization_id=organization_id, program_id=program_id)
    return list((await db.execute(
        select(ProgramZone).where(ProgramZone.organization_id == organization_id,
                                  ProgramZone.program_id == program_id).order_by(ProgramZone.name)
    )).scalars().all())


async def create_zone(db, *, organization_id, user, program_id, data) -> ProgramZone:
    await get_program(db, organization_id=organization_id, program_id=program_id)
    code = _slug(data.get("code") or data["name"]).upper()
    if (await db.execute(select(ProgramZone.id).where(ProgramZone.organization_id == organization_id,
                                                      ProgramZone.code == code))).first():
        raise ConflictError(f"Ya existe una zona con el código {code}.", code="zone_code_taken")
    if data.get("state") and data["state"] not in ("CA", "AZ", "NV"):
        raise InvalidInputError("El estado es CA, AZ o NV.", code="invalid_state")
    zona = ProgramZone(organization_id=organization_id, program_id=program_id, code=code, name=data["name"],
                       state=data.get("state"), city=data.get("city"), notes=data.get("notes"))
    db.add(zona)
    await db.flush()
    await _audit(db, organization_id, user, "zones.created", "ProgramZone", zona.id, {"code": code})
    await db.commit()
    await db.refresh(zona)
    return zona


async def update_zone(db, *, organization_id, user, zone_id, changes) -> ProgramZone:
    zona = await _owned(db, ProgramZone, zone_id, organization_id, "La zona no existe.", "zone_not_found")
    for k in ("name", "state", "city", "notes", "active"):
        if k in changes:
            setattr(zona, k, changes[k])
    await db.commit()
    await db.refresh(zona)
    return zona


async def zone_salespeople(db, zone_id) -> list[uuid.UUID]:
    return list((await db.execute(select(ZoneAssignment.user_id).where(ZoneAssignment.zone_id == zone_id)))
                .scalars().all())


async def set_zone_salespeople(db, *, organization_id, user, zone_id, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Reemplaza los vendedores de la zona. Solo usuarios de la organización
    que pueden crear expedientes (los que salen a tocar puertas)."""
    from app.api.deps import get_effective_permissions
    from app.modules.users.models import User

    zona = await _owned(db, ProgramZone, zone_id, organization_id, "La zona no existe.", "zone_not_found")
    usuarios = (await db.execute(select(User).where(User.id.in_(user_ids),
                                                    User.organization_id == organization_id))).scalars().all()
    if len(usuarios) != len(set(user_ids)):
        raise NotFoundError("Alguno de los usuarios no existe.", code="user_not_found")
    no_vendedores = [u.full_name for u in usuarios if "cases.create" not in get_effective_permissions(u)]
    if no_vendedores:
        raise InvalidInputError(f"{', '.join(no_vendedores)} no puede crear expedientes; no se asigna a una zona.",
                                code="not_a_salesperson")
    actuales = {a.user_id: a for a in (await db.execute(
        select(ZoneAssignment).where(ZoneAssignment.zone_id == zona.id))).scalars().all()}
    for uid, a in actuales.items():
        if uid not in set(user_ids):
            await db.delete(a)
    for uid in set(user_ids) - set(actuales):
        db.add(ZoneAssignment(organization_id=organization_id, zone_id=zona.id, user_id=uid))
    await _audit(db, organization_id, user, "zones.salespeople_set", "ProgramZone", zona.id,
                 {"users": [str(u) for u in user_ids]})
    await db.commit()
    return await zone_salespeople(db, zona.id)


async def my_assignments(db, *, organization_id, user) -> list[dict]:
    """Inicio del vendedor (D5): sus programas activos con versión publicada y
    sus zonas en cada uno."""
    filas = (await db.execute(
        select(ProgramZone, Program).join(ZoneAssignment, ZoneAssignment.zone_id == ProgramZone.id)
        .join(Program, Program.id == ProgramZone.program_id)
        .where(ZoneAssignment.user_id == user.id, ZoneAssignment.organization_id == organization_id,
               ProgramZone.active.is_(True), Program.active.is_(True))
        .order_by(Program.name, ProgramZone.name)
    )).all()
    por_programa: dict = {}
    for zona, programa in filas:
        item = por_programa.setdefault(programa.id, {"program": programa, "zones": []})
        item["zones"].append(zona)
    resultado = []
    for item in por_programa.values():
        version = await published_version(db, organization_id=organization_id, program_id=item["program"].id)
        if version:
            resultado.append({**item, "version": version})
    return resultado


# ---------------------------------------------------------------------------
# Plantillas del sistema (D1.7)
# ---------------------------------------------------------------------------

async def install_defaults(db, *, organization_id, user=None) -> dict:
    """Copia el catálogo canónico y los programas de Arizona y TECH a la
    organización. Idempotente: lo que ya existe (por clave o código) no se
    toca, así que nunca deshace un ajuste del administrador."""
    from app.modules.programs.templates import CATALOG, PROGRAMS

    existentes = {f.key: f for f in await list_fields(db, organization_id=organization_id)}
    creados_campos = 0
    for key, label, tipo, seccion, extra in CATALOG:
        if key in existentes:
            continue
        f = FieldDefinition(organization_id=organization_id, key=key, label=label, field_type=tipo,
                            section=seccion, help_text=extra.get("help"), options=extra.get("options"),
                            validation=extra.get("validation"), binding=extra.get("binding"),
                            internal=extra.get("internal", False), sensitive=extra.get("sensitive", False))
        db.add(f)
        existentes[key] = f
        creados_campos += 1
    await db.flush()

    creados_programas = []
    for plantilla in PROGRAMS:
        programa = (await db.execute(select(Program).where(Program.organization_id == organization_id,
                                                           Program.code == plantilla["code"]))).scalar_one_or_none()
        if programa is None:
            programa = Program(organization_id=organization_id, code=plantilla["code"], name=plantilla["name"])
            db.add(programa)
        # Completa la identidad solo donde está vacía.
        for k in ("customer_facing_name", "funder_name", "invoice_entity", "authorization_text"):
            if not getattr(programa, k, None):
                setattr(programa, k, plantilla[k])
        await db.flush()
        tiene_version = (await db.execute(select(func.count()).select_from(ProgramVersion)
                                          .where(ProgramVersion.program_id == programa.id))).scalar_one()
        if tiene_version:
            continue
        terms = ProgramTerms(organization_id=organization_id, program_id=programa.id, version="2026.1",
                             language="es", title=plantilla["terms_title"],
                             body=plantilla["authorization_text"], published_at=_now())
        db.add(terms)
        await db.flush()
        version = ProgramVersion(organization_id=organization_id, program_id=programa.id, version="1",
                                 status="published", published_at=_now(), terms_id=terms.id,
                                 notes="Plantilla inicial del sistema (valores provisionales, D7).")
        db.add(version)
        await db.flush()
        fase = WorkflowPhase(organization_id=organization_id, version_id=version.id, code="salesperson",
                             name="Vendedor", role_code="salesperson", sort_order=0)
        db.add(fase)
        await db.flush()
        for n, (codigo, titulo, campos) in enumerate(plantilla["steps"]):
            paso = WorkflowStep(organization_id=organization_id, phase_id=fase.id, code=codigo, title=titulo,
                                sort_order=n)
            db.add(paso)
            await db.flush()
            for m, (key, requisito, condicion) in enumerate(campos):
                db.add(WorkflowStepField(organization_id=organization_id, step_id=paso.id,
                                         field_id=existentes[key].id, requirement=requisito,
                                         condition=condicion, sort_order=m))
        creados_programas.append(programa.code)
    if user is not None and (creados_campos or creados_programas):
        await _audit(db, organization_id, user, "programs.defaults_installed", "Organization", organization_id,
                     {"fields": creados_campos, "programs": creados_programas})
    await db.commit()
    return {"fields_created": creados_campos, "programs_created": creados_programas}
