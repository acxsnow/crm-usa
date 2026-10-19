"""Aviso a Administración al cerrar la instalación
(spec 2026-10-19-actas-por-confirmar)."""
from datetime import date

from sqlalchemy import select

from app.modules.notifications import service as notices
from app.modules.notifications.models import Notification
from tests.field_helpers import installed_case


async def _cerrada(db, org_id, technician_id, cerrada_el: date):
    _, project = await installed_case(db, org_id, technician_id=technician_id)
    project.completed_date = cerrada_el
    await db.commit()
    return project


async def test_closing_notifies_the_reviewers_with_a_link_to_the_review_step(
        db, seeded_org, active_admin_staff_user, active_technician_user):
    org = seeded_org["org"].id
    project = await _cerrada(db, org, active_technician_user.id, date(2026, 10, 10))
    creados = await notices.process_event(db, "installation.closed", {
        "organization_id": str(org), "project_id": str(project.id),
        "closed_by_user_id": str(active_technician_user.id)})
    assert creados >= 1
    aviso = (await db.execute(select(Notification).where(
        Notification.user_id == active_admin_staff_user.id))).scalars().one()
    assert aviso.event == "installation.closed"
    assert project.case_number in aviso.title
    assert aviso.link == f"/projects/{project.id}?paso=review"
    # El técnico que cerró no se avisa a sí mismo.
    assert (await db.execute(select(Notification).where(
        Notification.user_id == active_technician_user.id))).scalars().all() == []
