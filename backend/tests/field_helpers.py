"""Ayudas compartidas por las pruebas del módulo 5 (campo).

Arman el escenario real: un expediente aprobado con cliente, que crea su
proyecto por el efecto de José, y ese proyecto asignado al técnico.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.modules.field_ops.models import Project, ProjectChecklistItem

PASSWORD = "SuperSecret123"


async def headers_for(app_client, email: str) -> dict:
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def jpeg_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (120, 90), color=(10, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def pdf_bytes(texto: str = "Documento de prueba") -> bytes:
    """Un PDF real de una página (la validación rechaza los de mentira)."""
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    hoja = canvas.Canvas(buf)
    hoja.drawString(72, 720, texto)
    hoja.showPage()
    hoja.save()
    return buf.getvalue()


async def approved_case_with_project(db, org_id, *, technician_id=None, program_id=None):
    """Expediente en `approved` con su proyecto de instalación, como lo deja
    Administración al aprobar. Devuelve (case, project)."""
    from app.modules.crm.models import Customer

    case_hooks.register()
    cliente = Customer(organization_id=org_id, legal_name="Marge Simpson")
    db.add(cliente)
    await db.flush()

    actor = uuid.uuid4()
    case = await case_service.create_case(
        db, organization_id=org_id, actor_id=actor, stage_code="new_prospect",
        customer_id=cliente.id, program_id=program_id,
        address_street="742 Evergreen Terrace", address_unit="Spc 7",
        address_city="Phoenix", address_state="AZ", address_zip="85001",
    )
    for destino in ("pending_approval", "approved"):
        case = await case_service.transition(
            db, case=case, to_stage=destino, actor_id=actor, actor_permissions=stages.SYSTEM_ACTOR
        )
    project = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalar_one()
    if technician_id is not None:
        project.primary_technician_user_id = technician_id
        await db.commit()
        await db.refresh(project)
    return case, project


async def checklist_items(db, project_id) -> list[ProjectChecklistItem]:
    return list(
        (
            await db.execute(
                select(ProjectChecklistItem)
                .where(ProjectChecklistItem.project_id == project_id)
                .order_by(ProjectChecklistItem.sort_order)
            )
        ).scalars().all()
    )


async def resolve_whole_checklist(db, project_id) -> None:
    """Deja el checklist completo sin pasar por la API: para las pruebas que
    necesitan llegar al cierre sin repetir la carga de 14 fotos."""
    for item in await checklist_items(db, project_id):
        item.is_complete = True
    await db.commit()


async def refreshed_case(db, case):
    """Relee el expediente de la base. La API corre en otra sesión, así que el
    objeto que esta sesión tiene en memoria está desactualizado."""
    org_id, case_id = case.organization_id, case.id
    db.expire_all()
    return await case_service.get_case_or_404(db, organization_id=org_id, case_id=case_id)


def item_by_label(items, fragment: str):
    return next(i for i in items if fragment in i.label)


async def ready_to_install_case(db, org_id, *, technician_id=None):
    """Expediente en `ready_to_install`: aprobado y con permiso despejado."""
    from datetime import date

    from app.modules.field_ops.models import Permit

    case, project = await approved_case_with_project(db, org_id, technician_id=technician_id)
    db.add(Permit(organization_id=org_id, project_id=project.id, jurisdiction="Phoenix",
                  status="approved", approved_on=date.today()))
    await db.flush()
    for destino in ("permit_in_progress", "ready_to_install"):
        case = await case_service.transition(
            db, case=case, to_stage=destino, actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
        )
    return case, project


async def add_equipment_directly(db, project) -> None:
    from app.modules.field_ops.models import InstalledEquipment

    db.add(InstalledEquipment(organization_id=project.organization_id, project_id=project.id,
                              equipment_type="heat_pump_outdoor", brand="Carrier", model="25HCE4",
                              serial_number="SN-0001"))
    # Lista guardada («Guardar equipos instalados»), como la deja el técnico.
    project.equipment_confirmed_at = datetime.now(timezone.utc)
    await db.commit()


async def installed_case(db, org_id, *, technician_id=None):
    """Expediente en `installed`: instalación cerrada con checklist y equipo."""
    case, project = await ready_to_install_case(db, org_id, technician_id=technician_id)
    await resolve_whole_checklist(db, project.id)
    await add_equipment_directly(db, project)
    case = await case_service.transition(
        db, case=case, to_stage="installed", actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
    )
    await db.refresh(project)
    return case, project
