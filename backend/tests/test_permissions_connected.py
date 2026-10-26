"""D-014: siete permisos del catálogo no controlaban nada (barrido de SEC-003).
Cada prueba comprueba que el permiso ahora decide lo que dice su nombre, y la
última impide que vuelva a quedar un permiso del catálogo sin usar."""
from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.field_ops.models import Project, ProjectStatus
from app.shared.permissions import PERMISSION_CATALOG
from tests.field_helpers import approved_case_with_project, checklist_items, headers_for, jpeg_bytes

API = "/api/v1"


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _sin_permiso(app_client, admin, rol: str, permiso: str) -> None:
    roles = (await app_client.get(f"{API}/roles", headers=admin)).json()
    actuales = next(r for r in roles if r["code"] == rol)["permissions"]
    r = await app_client.patch(f"{API}/roles/{rol}", json={"permissions": [p for p in actuales if p != permiso]},
                               headers=admin)
    assert r.status_code == 200, r.text


async def test_customers_delete(app_client, db, seeded_org, login, active_admin_user, active_salesperson_user):
    admin = await login(active_admin_user.email)
    vendedor = await login(active_salesperson_user.email)
    nuevo = (await app_client.post(f"{API}/customers", json={"legal_name": "Creado por error",
                                                             "data_consent_accepted": True}, headers=admin)).json()
    assert (await app_client.delete(f"{API}/customers/{nuevo['id']}", headers=vendedor)).status_code == 403
    assert (await app_client.delete(f"{API}/customers/{nuevo['id']}", headers=admin)).status_code == 204
    assert (await app_client.get(f"{API}/customers/{nuevo['id']}", headers=admin)).status_code == 404

    # Un cliente con expediente y obra no se borra: se irían con él.
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    r = await app_client.delete(f"{API}/customers/{case.customer_id}", headers=admin)
    assert (r.status_code, r.json()["code"]) == (409, "customer_in_use")
    assert "expedientes" in r.json()["detail"] and "obras" in r.json()["detail"]


async def test_evidence_delete(app_client, db, seeded_org, login, active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    item = next(i for i in await checklist_items(db, obra.id) if i.requires_evidence)
    r = await app_client.post(f"{API}/projects/{obra.id}/evidence", headers=tecnico,
                              files={"file": ("foto.jpg", jpeg_bytes(), "image/jpeg")},
                              data={"checklist_item_id": str(item.id), "category": item.evidence_category or "additional_photo"})
    assert r.status_code == 201, r.text
    ev = r.json()["id"]
    assert (await app_client.patch(f"{API}/checklist-items/{item.id}", json={"is_complete": True},
                                   headers=tecnico)).status_code == 200

    assert (await app_client.delete(f"{API}/evidence/{ev}", headers=tecnico)).status_code == 403
    assert (await app_client.delete(f"{API}/evidence/{ev}", headers=admin)).status_code == 204
    lista = (await app_client.get(f"{API}/projects/{obra.id}/evidence", headers=admin)).json()
    assert ev not in [x["id"] for x in lista]
    # Era la única foto del renglón: vuelve a pendiente.
    renglon = next(i for i in (await app_client.get(f"{API}/projects/{obra.id}/checklist", headers=admin)).json()
                   if i["id"] == str(item.id))
    assert renglon["is_complete"] is False
    assert (await app_client.delete(f"{API}/evidence/{ev}", headers=admin)).status_code == 404

    # Con la instalación cerrada, lo registrado no se toca.
    r = await app_client.post(f"{API}/projects/{obra.id}/evidence", headers=tecnico,
                              files={"file": ("otra.jpg", jpeg_bytes(), "image/jpeg")})
    proyecto = (await db.execute(select(Project).where(Project.id == obra.id))).scalar_one()
    proyecto.status = ProjectStatus.completed
    await db.commit()
    r = await app_client.delete(f"{API}/evidence/{r.json()['id']}", headers=admin)
    assert (r.status_code, r.json()["code"]) == (409, "installation_closed")


async def test_projects_assign(app_client, db, seeded_org, login, active_admin_user, active_admin_staff_user,
                               active_technician_user):
    from datetime import date, timedelta

    admin = await login(active_admin_user.email)
    oficina = await login(active_admin_staff_user.email)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    dia = (date.today() + timedelta(days=3)).isoformat()
    otro_dia = (date.today() + timedelta(days=4)).isoformat()
    cuerpo = {"technician_user_id": str(active_technician_user.id), "scheduled_date": dia}
    assert (await app_client.patch(f"{API}/projects/{obra.id}/schedule", json=cuerpo, headers=oficina)).status_code == 200

    await _sin_permiso(app_client, admin, "admin_staff", "projects.assign")
    # Mover la fecha con el mismo técnico sigue siendo de dispatch.manage...
    r = await app_client.patch(f"{API}/projects/{obra.id}/schedule", json={**cuerpo, "scheduled_date": otro_dia},
                               headers=oficina)
    assert r.status_code == 200, r.text
    # ...pero cambiar o poner el técnico exige projects.assign.
    _, otra = await approved_case_with_project(db, seeded_org["org"].id)
    r = await app_client.patch(f"{API}/projects/{otra.id}/schedule", json=cuerpo, headers=oficina)
    assert (r.status_code, r.json()["code"]) == (403, "assign_not_allowed")


async def test_organization_and_settings(app_client, db, seeded_org, login, active_admin_user, active_admin_staff_user,
                                         active_roleless_user):
    admin = await login(active_admin_user.email)
    assert (await app_client.get(f"{API}/organization/settings",
                                 headers=await login(active_admin_staff_user.email))).status_code == 403
    r = await app_client.post(f"{API}/roles", json={"code": "solo_config", "name": "Solo configuración",
                                                    "permissions": ["settings.manage"]}, headers=admin)
    assert r.status_code == 201, r.text
    r = await app_client.patch(f"{API}/users/{active_roleless_user.id}/roles", json={"role_codes": ["solo_config"]},
                               headers=admin)
    assert r.status_code == 200, r.text
    config = await login(active_roleless_user.email)
    assert (await app_client.get(f"{API}/organization/settings", headers=config)).status_code == 200
    r = await app_client.patch(f"{API}/organization/settings", json={"timezone": "America/Phoenix"}, headers=config)
    assert r.status_code == 200, r.text
    r = await app_client.patch(f"{API}/organization/settings", json={"name": "Otra empresa"}, headers=config)
    assert (r.status_code, r.json()["code"]) == (403, "organization_manage_required")
    r = await app_client.patch(f"{API}/organization/settings", json={"name": "Delta HVAC QA"}, headers=admin)
    assert (r.status_code, r.json()["name"]) == (200, "Delta HVAC QA")


async def test_profile_manage(app_client, login, active_technician_user, active_roleless_user):
    tecnico = await login(active_technician_user.email)
    r = await app_client.patch(f"{API}/auth/me", json={"full_name": "  Tito Técnico Ramírez "}, headers=tecnico)
    assert (r.status_code, r.json()["full_name"]) == (200, "Tito Técnico Ramírez")
    r = await app_client.patch(f"{API}/auth/me", json={"full_name": "Sin rol"},
                               headers=await login(active_roleless_user.email))
    assert r.status_code == 403


async def test_reports_by_permission(app_client, login, active_admin_staff_user, active_accounting_user,
                                     active_management_user):
    async def codigos(usuario):
        h = await login(usuario.email)
        return [(await app_client.get(f"{API}/reports/{k}", headers=h)).status_code
                for k in ("commercial", "operations", "finance")]
    assert await codigos(active_admin_staff_user) == [200, 403, 403]   # tablero comercial, sin generar reportes
    assert await codigos(active_accounting_user) == [403, 200, 200]    # genera reportes, sin tablero comercial
    assert await codigos(active_management_user) == [200, 200, 200]
    r = await app_client.get(f"{API}/reports/commercial/csv", headers=await login(active_accounting_user.email))
    assert r.status_code == 403


def test_every_permission_in_the_catalog_is_used():
    """Ningún permiso del catálogo puede quedar sin que lo revise el código."""
    app = Path(__file__).resolve().parents[1] / "app"
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in app.rglob("*.py")
                       if p.name != "permissions.py" and "__pycache__" not in p.parts)
    sin_uso = [c for c, _ in PERMISSION_CATALOG if f'"{c}"' not in codigo]
    assert not sin_uso, f"Permisos del catálogo que no revisa ningún código: {sin_uso}"


async def test_audit_shows_before_and_after(app_client, login, active_admin_user, active_management_user,
                                            active_technician_user):
    """D-020: la auditoría guardaba el antes y el después pero no los devolvía.
    La ven quienes tienen `audit.read` (Administrador, Administración,
    Contabilidad y Gerencia); el técnico y el vendedor no."""
    admin = await login(active_admin_user.email)
    r = await app_client.patch(f"{API}/organization/settings", json={"name": "Nombre auditado"}, headers=admin)
    assert r.status_code == 200, r.text
    eventos = (await app_client.get(f"{API}/audit-events", params={"action": "organization.settings_updated"},
                                    headers=admin)).json()
    assert eventos, "no quedó el evento"
    e = eventos[0]
    assert e["actor_user_id"] == str(active_admin_user.id) and e["created_at"]
    assert e["after_data"] == {"name": "Nombre auditado"} and "name" in e["before_data"]
    assert (await app_client.get(f"{API}/audit-events", headers=await login(active_management_user.email))).status_code == 200
    assert (await app_client.get(f"{API}/audit-events", headers=await login(active_technician_user.email))).status_code == 403
