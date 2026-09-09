from datetime import date, datetime, timedelta, timezone


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_heartbeat_sets_last_seen_at_and_throttles(app_client, db, active_admin_user, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 200
    await db.refresh(active_admin_user)
    first_seen = active_admin_user.last_seen_at
    assert first_seen is not None

    # A second request right away must NOT bump it again (throttled to 2 min).
    resp = await app_client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200
    await db.refresh(active_admin_user)
    assert active_admin_user.last_seen_at == first_seen

    # Force it stale, then confirm the next request does bump it.
    active_admin_user.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db.commit()

    resp = await app_client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200
    await db.refresh(active_admin_user)
    assert active_admin_user.last_seen_at > first_seen


async def test_technician_monitor_metrics_scoped_to_today(app_client, db, active_project_manager_user, active_technician_user, seeded_org):
    from app.modules.crm.models import Customer, CustomerStatus
    from app.modules.field_ops.models import Project, ProjectStatus

    org_id = seeded_org["org"].id
    customer = Customer(organization_id=org_id, legal_name="Acme Roofing", status=CustomerStatus.active)
    db.add(customer)
    await db.flush()

    tech = active_technician_user
    today = date.today()
    yesterday = today - timedelta(days=1)
    db.add_all([
        Project(organization_id=org_id, customer_id=customer.id, title="Open job", status=ProjectStatus.scheduled, primary_technician_user_id=tech.id),
        Project(organization_id=org_id, customer_id=customer.id, title="Cancelled job", status=ProjectStatus.cancelled, primary_technician_user_id=tech.id),
        Project(organization_id=org_id, customer_id=customer.id, title="Done today", status=ProjectStatus.completed, primary_technician_user_id=tech.id, completed_date=today),
        Project(organization_id=org_id, customer_id=customer.id, title="Done yesterday", status=ProjectStatus.completed, primary_technician_user_id=tech.id, completed_date=yesterday),
    ])
    await db.commit()

    token = await _login(app_client, "pm@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await app_client.get("/api/v1/technician-monitor", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["full_name"] for r in rows] == ["Tom Technician"]
    row = rows[0]
    assert row["casos_asignados"] == 1  # only the scheduled one; cancelled and completed don't count
    assert row["casos_gestionados_hoy"] == 1  # only "Done today"
    assert row["tiempo_gestion_hoy_dias"] is not None
    assert row["en_cola"] is False  # default


async def test_technician_monitor_requires_dashboards_operations_permission(app_client, active_technician_user, seeded_org):
    token = await _login(app_client, "tech@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await app_client.get("/api/v1/technician-monitor", headers=headers)
    assert resp.status_code == 403


async def test_availability_toggle_updates_is_available(app_client, db, active_project_manager_user, active_technician_user, seeded_org):
    token = await _login(app_client, "pm@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.patch(
        f"/api/v1/technicians/{active_technician_user.id}/availability",
        json={"is_available": True},
        headers=headers,
    )
    assert resp.status_code == 204

    await db.refresh(active_technician_user)
    assert active_technician_user.is_available is True


async def test_availability_toggle_404s_for_non_technician(app_client, active_project_manager_user, seeded_org):
    token = await _login(app_client, "pm@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.patch(
        f"/api/v1/technicians/{active_project_manager_user.id}/availability",
        json={"is_available": True},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_availability_toggle_requires_dashboards_operations_permission(app_client, active_technician_user, seeded_org):
    token = await _login(app_client, "tech@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.patch(
        f"/api/v1/technicians/{active_technician_user.id}/availability",
        json={"is_available": True},
        headers=headers,
    )
    assert resp.status_code == 403
