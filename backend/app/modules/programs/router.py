"""Rutas del módulo 1: programas, T&C, catálogo de campos, flujo versionado y
zonas de venta (spec §3). Leer: `programs.read`. Cambiar: el permiso de cada
parte (`programs.manage`, `fields.manage`, `workflows.manage`,
`workflows.publish`, `zones.manage`)."""
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_organization_id, require_permission
from app.db.session import get_db
from app.modules.programs import engine
from app.modules.programs import service as svc
from app.modules.programs.models import BINDINGS, FIELD_TYPES, PHASE_ROLES, REQUIREMENT_LEVELS
from app.modules.users.models import User

router = APIRouter(tags=["programs"])

_read = require_permission("programs.read")
_manage = require_permission("programs.manage")
_fields = require_permission("fields.manage")
_workflows = require_permission("workflows.manage")
_publish = require_permission("workflows.publish")
_zones = require_permission("zones.manage")


# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------

class ProgramIn(BaseModel):
    code: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    funder_name: str | None = Field(default=None, max_length=255)
    customer_facing_name: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=1024)
    authorization_text: str | None = None
    invoice_entity: str | None = Field(default=None, max_length=255)


class ProgramUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    active: bool | None = None
    description: str | None = None
    funder_name: str | None = Field(default=None, max_length=255)
    customer_facing_name: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=1024)
    authorization_text: str | None = None
    invoice_entity: str | None = Field(default=None, max_length=255)


class ProgramOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    active: bool
    description: str | None
    funder_name: str | None
    customer_facing_name: str | None
    logo_url: str | None
    authorization_text: str | None
    invoice_entity: str | None
    published_version: str | None = None
    model_config = {"from_attributes": True}


class TermsIn(BaseModel):
    version: str = Field(min_length=1, max_length=30)
    language: str = "es"
    title: str | None = Field(default=None, max_length=255)
    body: str


class TermsUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    body: str | None = None


class TermsOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    version: str
    language: str
    title: str
    body: str
    published_at: datetime | None
    model_config = {"from_attributes": True}


class Option(BaseModel):
    value: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=255)


class FieldIn(BaseModel):
    key: str = Field(min_length=3, max_length=100)
    label: str = Field(min_length=1, max_length=255)
    field_type: str
    help_text: str | None = None
    section: str | None = Field(default=None, max_length=120)
    options: list[Option] | None = None
    validation: dict | None = None
    binding: str | None = None
    internal: bool = False
    sensitive: bool = False


class FieldUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    help_text: str | None = None
    section: str | None = Field(default=None, max_length=120)
    options: list[Option] | None = None
    validation: dict | None = None
    binding: str | None = None
    internal: bool | None = None
    sensitive: bool | None = None
    active: bool | None = None


class FieldOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    field_type: str
    help_text: str | None
    section: str | None
    options: list[dict] | None
    validation: dict | None
    binding: str | None
    internal: bool
    sensitive: bool
    active: bool
    model_config = {"from_attributes": True}


class VersionOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    version: str
    status: str
    published_at: datetime | None
    terms_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class VersionUpdate(BaseModel):
    terms_id: uuid.UUID | None = None
    notes: str | None = None


class PhaseIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    role_code: str
    code: str | None = None


class StepIn(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: str | None = None
    code: str | None = None


class StepUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None


class StepFieldIn(BaseModel):
    field_id: uuid.UUID
    requirement: str = "optional"
    condition: dict | None = None
    label_override: str | None = Field(default=None, max_length=255)
    help_override: str | None = None


class StepFieldUpdate(BaseModel):
    requirement: str | None = None
    condition: dict | None = None
    label_override: str | None = Field(default=None, max_length=255)
    help_override: str | None = None


class Move(BaseModel):
    direction: Literal["up", "down"]


class PreviewIn(BaseModel):
    answers: dict = {}
    include_internal: bool = True


class ZoneIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str | None = None
    state: str | None = None
    city: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    state: str | None = None
    city: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    active: bool | None = None


class ZoneOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID | None
    code: str
    name: str
    state: str | None
    city: str | None
    notes: str | None
    active: bool
    salesperson_ids: list[uuid.UUID] = []
    model_config = {"from_attributes": True}


class SalespeopleIn(BaseModel):
    user_ids: list[uuid.UUID]


async def _zone_out(db, zona) -> ZoneOut:
    return ZoneOut.model_validate({**{c: getattr(zona, c) for c in ZoneOut.model_fields if c != "salesperson_ids"},
                                   "salesperson_ids": await svc.zone_salespeople(db, zona.id)})


async def _program_out(db, organization_id, programa) -> ProgramOut:
    version = await svc.published_version(db, organization_id=organization_id, program_id=programa.id)
    return ProgramOut.model_validate({**{c: getattr(programa, c) for c in ProgramOut.model_fields
                                         if c != "published_version"},
                                      "published_version": version.version if version else None})


# ---------------------------------------------------------------------------
# Catálogos para la pantalla
# ---------------------------------------------------------------------------

@router.get("/programs/catalogs")
async def catalogs(current_user: User = Depends(_read)) -> dict:
    return {"field_types": FIELD_TYPES, "bindings": BINDINGS, "requirements": REQUIREMENT_LEVELS,
            "phase_roles": PHASE_ROLES, "languages": svc.LANGUAGES}


@router.post("/programs/install-defaults")
async def install_defaults(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_manage)) -> dict:
    """Carga el catálogo canónico y los programas de Arizona y TECH. No pisa lo
    que ya exista."""
    return await svc.install_defaults(db, organization_id=organization_id, user=current_user)


# ---------------------------------------------------------------------------
# Programas
# ---------------------------------------------------------------------------

@router.get("/programs", response_model=list[ProgramOut])
async def list_programs(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)):
    return [await _program_out(db, organization_id, p) for p in await svc.list_programs(db, organization_id=organization_id)]


@router.post("/programs", response_model=ProgramOut, status_code=201)
async def create_program(payload: ProgramIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)):
    p = await svc.create_program(db, organization_id=organization_id, user=current_user, data=payload.model_dump())
    return await _program_out(db, organization_id, p)


@router.get("/programs/{program_id}", response_model=ProgramOut)
async def get_program(program_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_read)):
    return await _program_out(db, organization_id, await svc.get_program(db, organization_id=organization_id,
                                                                         program_id=program_id))


@router.patch("/programs/{program_id}", response_model=ProgramOut)
async def update_program(program_id: uuid.UUID, payload: ProgramUpdate, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)):
    p = await svc.update_program(db, organization_id=organization_id, user=current_user, program_id=program_id,
                                 changes=payload.model_dump(exclude_unset=True))
    return await _program_out(db, organization_id, p)


# --- T&C -----------------------------------------------------------------------

@router.get("/programs/{program_id}/terms", response_model=list[TermsOut])
async def list_terms(program_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_read)):
    return await svc.list_terms(db, organization_id=organization_id, program_id=program_id)


@router.post("/programs/{program_id}/terms", response_model=TermsOut, status_code=201)
async def create_terms(program_id: uuid.UUID, payload: TermsIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    return await svc.create_terms(db, organization_id=organization_id, user=current_user, program_id=program_id,
                                  data=payload.model_dump())


@router.patch("/program-terms/{terms_id}", response_model=TermsOut)
async def update_terms(terms_id: uuid.UUID, payload: TermsUpdate, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    return await svc.update_terms(db, organization_id=organization_id, user=current_user, terms_id=terms_id,
                                  changes=payload.model_dump(exclude_unset=True))


@router.post("/program-terms/{terms_id}/publish", response_model=TermsOut)
async def publish_terms(terms_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)):
    return await svc.publish_terms(db, organization_id=organization_id, user=current_user, terms_id=terms_id)


# ---------------------------------------------------------------------------
# Catálogo de campos
# ---------------------------------------------------------------------------

@router.get("/fields", response_model=list[FieldOut])
async def list_fields(include_inactive: bool = True, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_read)):
    return await svc.list_fields(db, organization_id=organization_id, include_inactive=include_inactive)


@router.post("/fields", response_model=FieldOut, status_code=201)
async def create_field(payload: FieldIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_fields)):
    return await svc.create_field(db, organization_id=organization_id, user=current_user,
                                  data=payload.model_dump(mode="json"))


@router.patch("/fields/{field_id}", response_model=FieldOut)
async def update_field(field_id: uuid.UUID, payload: FieldUpdate, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_fields)):
    return await svc.update_field(db, organization_id=organization_id, user=current_user, field_id=field_id,
                                  changes=payload.model_dump(mode="json", exclude_unset=True))


# ---------------------------------------------------------------------------
# Versiones y flujo
# ---------------------------------------------------------------------------

@router.get("/programs/{program_id}/versions", response_model=list[VersionOut])
async def list_versions(program_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)):
    return await svc.list_versions(db, organization_id=organization_id, program_id=program_id)


@router.post("/programs/{program_id}/versions", response_model=VersionOut, status_code=201)
async def create_version(program_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_workflows)):
    return await svc.create_version(db, organization_id=organization_id, user=current_user, program_id=program_id)


@router.get("/program-versions/{version_id}")
async def get_version(version_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_read)) -> dict:
    """La versión completa: fases, pasos y campos, más lo que impediría
    publicarla (para mostrarlo antes de intentarlo)."""
    version = await svc.get_version(db, organization_id=organization_id, version_id=version_id)
    fases = [{"id": str(f.id), "code": f.code, "name": f.name, "role_code": f.role_code,
              "steps": [{"id": str(p.id), "code": p.code, "title": p.title, "description": p.description}
                        for p in f.steps]}
             for f in await svc.phases_of(db, version.id)]
    return {"version": VersionOut.model_validate(version).model_dump(mode="json"), "phases": fases,
            "definition": await svc.version_definition(db, version),
            "problems": await svc.version_problems(db, version) if version.status == "draft" else []}


@router.patch("/program-versions/{version_id}", response_model=VersionOut)
async def update_version(version_id: uuid.UUID, payload: VersionUpdate, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_workflows)):
    return await svc.update_version(db, organization_id=organization_id, user=current_user, version_id=version_id,
                                    changes=payload.model_dump(exclude_unset=True))


@router.post("/program-versions/{version_id}/publish", response_model=VersionOut)
async def publish_version(version_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_publish)):
    return await svc.publish_version(db, organization_id=organization_id, user=current_user, version_id=version_id)


@router.post("/program-versions/{version_id}/archive", response_model=VersionOut)
async def archive_version(version_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_publish)):
    return await svc.archive_version(db, organization_id=organization_id, user=current_user, version_id=version_id)


@router.post("/program-versions/{version_id}/preview")
async def preview(version_id: uuid.UUID, payload: PreviewIn, db: AsyncSession = Depends(get_db),
                  organization_id: uuid.UUID = Depends(get_organization_id),
                  current_user: User = Depends(_read)) -> dict:
    """Cómo vería el vendedor esta versión con estas respuestas: qué campos
    aparecen, qué falta y qué está mal. No guarda nada."""
    version = await svc.get_version(db, organization_id=organization_id, version_id=version_id)
    return engine.evaluate(await svc.version_definition(db, version), payload.answers,
                           include_internal=payload.include_internal)


@router.post("/program-versions/{version_id}/phases", status_code=201)
async def add_phase(version_id: uuid.UUID, payload: PhaseIn, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_workflows)) -> dict:
    f = await svc.add_phase(db, organization_id=organization_id, user=current_user, version_id=version_id,
                            data=payload.model_dump())
    return {"id": str(f.id), "code": f.code, "name": f.name, "role_code": f.role_code}


@router.post("/workflow-phases/{phase_id}/steps", status_code=201)
async def add_step(phase_id: uuid.UUID, payload: StepIn, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_workflows)) -> dict:
    p = await svc.add_step(db, organization_id=organization_id, user=current_user, phase_id=phase_id,
                           data=payload.model_dump())
    return {"id": str(p.id), "code": p.code, "title": p.title}


@router.patch("/workflow-steps/{step_id}", status_code=204)
async def update_step(step_id: uuid.UUID, payload: StepUpdate, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_workflows)):
    await svc.update_step(db, organization_id=organization_id, user=current_user, step_id=step_id,
                          changes=payload.model_dump(exclude_unset=True))
    return Response(status_code=204)


@router.delete("/workflow-steps/{step_id}", status_code=204)
async def delete_step(step_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_workflows)):
    await svc.delete_step(db, organization_id=organization_id, user=current_user, step_id=step_id)
    return Response(status_code=204)


@router.post("/workflow-steps/{step_id}/move", status_code=204)
async def move_step(step_id: uuid.UUID, payload: Move, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_workflows)):
    await svc.move_step(db, organization_id=organization_id, user=current_user, step_id=step_id,
                        direction=payload.direction)
    return Response(status_code=204)


@router.post("/workflow-steps/{step_id}/fields", status_code=201)
async def add_step_field(step_id: uuid.UUID, payload: StepFieldIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_workflows)) -> dict:
    sf = await svc.add_step_field(db, organization_id=organization_id, user=current_user, step_id=step_id,
                                  data=payload.model_dump())
    return {"id": str(sf.id)}


@router.patch("/workflow-step-fields/{step_field_id}", status_code=204)
async def update_step_field(step_field_id: uuid.UUID, payload: StepFieldUpdate, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_workflows)):
    await svc.update_step_field(db, organization_id=organization_id, user=current_user,
                                step_field_id=step_field_id, changes=payload.model_dump(exclude_unset=True))
    return Response(status_code=204)


@router.delete("/workflow-step-fields/{step_field_id}", status_code=204)
async def delete_step_field(step_field_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_workflows)):
    await svc.delete_step_field(db, organization_id=organization_id, user=current_user, step_field_id=step_field_id)
    return Response(status_code=204)


@router.post("/workflow-step-fields/{step_field_id}/move", status_code=204)
async def move_step_field(step_field_id: uuid.UUID, payload: Move, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_workflows)):
    await svc.move_step_field(db, organization_id=organization_id, user=current_user, step_field_id=step_field_id,
                              direction=payload.direction)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Zonas de venta
# ---------------------------------------------------------------------------

@router.get("/programs/{program_id}/zones", response_model=list[ZoneOut])
async def list_zones(program_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_read)):
    return [await _zone_out(db, z) for z in await svc.list_zones(db, organization_id=organization_id,
                                                                 program_id=program_id)]


@router.post("/programs/{program_id}/zones", response_model=ZoneOut, status_code=201)
async def create_zone(program_id: uuid.UUID, payload: ZoneIn, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_zones)):
    z = await svc.create_zone(db, organization_id=organization_id, user=current_user, program_id=program_id,
                              data=payload.model_dump())
    return await _zone_out(db, z)


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
async def update_zone(zone_id: uuid.UUID, payload: ZoneUpdate, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_zones)):
    z = await svc.update_zone(db, organization_id=organization_id, user=current_user, zone_id=zone_id,
                              changes=payload.model_dump(exclude_unset=True))
    return await _zone_out(db, z)


@router.put("/zones/{zone_id}/salespeople")
async def set_salespeople(zone_id: uuid.UUID, payload: SalespeopleIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_zones)) -> list[uuid.UUID]:
    return await svc.set_zone_salespeople(db, organization_id=organization_id, user=current_user,
                                          zone_id=zone_id, user_ids=payload.user_ids)


@router.get("/me/programs")
async def my_programs(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(get_current_user)) -> list[dict]:
    """El inicio del vendedor (D5): sus programas, con la versión publicada que
    va a llenar, y sus zonas."""
    return [{"program": {"id": str(i["program"].id), "code": i["program"].code, "name": i["program"].name},
             "version_id": str(i["version"].id), "version": i["version"].version,
             "zones": [{"id": str(z.id), "code": z.code, "name": z.name, "state": z.state, "city": z.city}
                       for z in i["zones"]]}
            for i in await svc.my_assignments(db, organization_id=organization_id, user=current_user)]


@router.get("/me/program-options")
async def my_program_options(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                             current_user: User = Depends(get_current_user)) -> dict:
    """Programas para elegir en un expediente: los de mis zonas o, si no tengo
    zona, todos los activos con formulario publicado."""
    opciones, propias = await svc.program_options(db, organization_id=organization_id, user=current_user)
    return {"assigned": propias, "options": [
        {"program": {"id": str(i["program"].id), "code": i["program"].code, "name": i["program"].name},
         "version_id": str(i["version"].id), "version": i["version"].version,
         "zones": [{"id": str(z.id), "code": z.code, "name": z.name, "state": z.state, "city": z.city}
                   for z in i["zones"]]} for i in opciones]}
