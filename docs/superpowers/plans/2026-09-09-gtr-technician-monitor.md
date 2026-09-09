# Monitor GTR de técnicos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a technician monitor page (`/technician-monitor`) showing, per active `field_technician`: logged-in status (session heartbeat), available/queued toggle (admin-controlled), assigned cases, cases handled today, and today's average handling time.

**Architecture:** Two new columns on `User` (`last_seen_at`, `is_available`) plus a throttled heartbeat write inside the existing `get_current_user` dependency (already runs on every authenticated request — no new middleware). Two new endpoints in `field_ops/router.py` computed in Python over already-existing `Project` rows (same simplicity tradeoff phase 1 used for `/invoices`). One new frontend page reusing the phase 1 `DataTable`, polling every 30s via React Query.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Alembic on the backend; React + TanStack Query + react-router-dom on the frontend. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-09-gtr-technician-monitor-design.md`

## Global Constraints

- No websockets — "logueado" derives from a heartbeat timestamp (5-minute freshness window), "en cola" is a manual boolean toggle.
- Only admin/supervisor (permission `dashboards.operations`) can change `is_available`; the technician has no self-service UI for it.
- "Casos gestionados" and "tiempo de gestión" are scoped to **today only** (`completed_date == date.today()`), not cumulative history.
- Heartbeat writes are throttled to once per 2 minutes per user; "logueado" freshness window is 5 minutes.
- Metrics are computed in Python per technician (one query for their projects), not a single SQL aggregate — matches the existing `/invoices` precedent for this codebase's current scale.
- **Path correction from the spec:** `field_ops/router.py`'s `APIRouter()` carries no prefix (its existing routes are flat, e.g. `/projects`, not `/field-ops/projects`) — the spec's `/field-ops/technician-monitor` and `/field-ops/technicians/{id}/availability` paths are corrected in this plan to `/technician-monitor` and `/technicians/{user_id}/availability`, matching the router's actual mount style. Confirmed by reading `app/api/v1/router.py`, which includes `field_ops_router` with no additional prefix.

---

## File Structure

**Backend — modify:**
- `backend/app/modules/users/models.py` — add `last_seen_at`, `is_available` to `User`.
- `backend/app/api/deps.py` — throttled heartbeat write in `get_current_user`.
- `backend/app/modules/field_ops/schemas.py` — add `TechnicianMonitorRow`, `AvailabilityUpdate`.
- `backend/app/modules/field_ops/router.py` — add `GET /technician-monitor`, `PATCH /technicians/{user_id}/availability`.

**Backend — new:**
- `backend/alembic/versions/0008_user_presence.py` — migration for the two new `users` columns.
- `backend/tests/test_technician_monitor.py` — tests for heartbeat throttling, monitor metrics, and the availability toggle.

**Frontend — new:**
- `frontend/src/features/field-ops/TechnicianMonitorPage.tsx` — the page.

**Frontend — modify:**
- `frontend/src/features/field-ops/api.ts` — add `listTechnicianMonitor`, `updateTechnicianAvailability`.
- `frontend/src/app/DashboardLayout.tsx` — add nav item.
- `frontend/src/app/router.tsx` — add route.

---

### Task 1: Backend — `User.last_seen_at` / `User.is_available` + migration

**Files:**
- Modify: `backend/app/modules/users/models.py:50-72` (`User` class)
- Create: `backend/alembic/versions/0008_user_presence.py`

**Interfaces:**
- Produces: `User.last_seen_at: datetime | None`, `User.is_available: bool` (default `False`) — consumed by Task 2 (heartbeat write) and Task 3 (monitor query).

- [ ] **Step 1: Add the columns to the model**

In `backend/app/modules/users/models.py`, inside the `User` class (after `token_version`, around line 67):

```python
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

(`Boolean` and `DateTime` are already imported at the top of this file.)

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/0008_user_presence.py`:

```python
"""Add users.last_seen_at and users.is_available for the technician monitor

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_available")
    op.drop_column("users", "last_seen_at")
```

- [ ] **Step 3: Verify the test DB picks up the new columns**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_rbac.py -v`
Expected: all PASS (tests build their schema from the SQLAlchemy models via `Base.metadata.create_all()`, not from Alembic, so this confirms the model change alone doesn't break anything — the migration itself is exercised separately in real deployments via `alembic upgrade head`, not by the test suite).

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/users/models.py backend/alembic/versions/0008_user_presence.py
git commit -m "Add User.last_seen_at and User.is_available for technician presence"
```

---

### Task 2: Backend — throttled heartbeat in `get_current_user`

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/test_technician_monitor.py` (new file)

**Interfaces:**
- Consumes: `User.last_seen_at` (Task 1).
- Produces: every authenticated request updates `current_user.last_seen_at` if it was `None` or more than 2 minutes stale — consumed by Task 3's "logueado" calculation.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_technician_monitor.py`:

```python
from datetime import datetime, timedelta, timezone


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py::test_heartbeat_sets_last_seen_at_and_throttles -v`
Expected: FAIL — `active_admin_user.last_seen_at` is `None` after the first request (nothing writes it yet).

- [ ] **Step 3: Implement the heartbeat**

In `backend/app/api/deps.py`, add to the imports:

```python
from datetime import datetime, timedelta, timezone
```

and add `from app.shared.datetime_utils import as_utc` to the imports.

Then, in `get_current_user`, right after the `if user.status != UserStatus.active:` block and before `request.state.current_user = user` (around line 48-51):

```python
    now = datetime.now(timezone.utc)
    if user.last_seen_at is None or (now - as_utc(user.last_seen_at)) > timedelta(minutes=2):
        user.last_seen_at = now
        await db.commit()

    request.state.current_user = user
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py::test_heartbeat_sets_last_seen_at_and_throttles -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite once**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: same 4 pre-existing unrelated failures as before this plan (`test_password_reset_request_always_generic`, `test_password_reset_full_flow`, `test_evidence_upload_rejects_non_photo_file_types`, `test_admin_can_invite_user_and_it_counts_toward_limit`), everything else passing — confirms the extra commit-per-request in `get_current_user` doesn't break any existing flow (in particular, any test that asserts on mock/exact DB write counts, if any — there are none currently, but this is the check for it).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_technician_monitor.py
git commit -m "Add throttled last_seen_at heartbeat to get_current_user"
```

---

### Task 3: Backend — `GET /technician-monitor`

**Files:**
- Modify: `backend/app/modules/field_ops/schemas.py` (add `TechnicianMonitorRow`)
- Modify: `backend/app/modules/field_ops/router.py` (add endpoint + imports)
- Test: `backend/tests/test_technician_monitor.py`

**Interfaces:**
- Consumes: `User.last_seen_at`/`is_available` (Task 1), heartbeat behavior (Task 2), existing `Project` model (`primary_technician_user_id`, `status`, `completed_date`, `created_at`).
- Produces: `GET /api/v1/technician-monitor` → `list[TechnicianMonitorRow]` where `TechnicianMonitorRow = { user_id: UUID, full_name: str, logueado: bool, en_cola: bool, casos_asignados: int, casos_gestionados_hoy: int, tiempo_gestion_hoy_dias: float | None }`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_technician_monitor.py`:

```python
from datetime import date


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py -k monitor_metrics -v`
Expected: FAIL — 404 (route doesn't exist yet).

- [ ] **Step 3: Add the response schema**

In `backend/app/modules/field_ops/schemas.py`, add (anywhere after the imports, e.g. right before the "Projects" section):

```python
class TechnicianMonitorRow(BaseModel):
    user_id: uuid.UUID
    full_name: str
    logueado: bool
    en_cola: bool
    casos_asignados: int
    casos_gestionados_hoy: int
    tiempo_gestion_hoy_dias: float | None
```

- [ ] **Step 4: Implement the endpoint**

In `backend/app/modules/field_ops/router.py`, extend the top-of-file imports:

```python
from datetime import datetime, timedelta, timezone, date
```

(replacing the existing `from datetime import datetime` line), and extend the `from app.modules.users.models import User` line to:

```python
from app.modules.users.models import Role, User, UserRole, UserStatus
```

and add:

```python
from app.shared.datetime_utils import as_utc
```

Add `TechnicianMonitorRow` to the existing `from app.modules.field_ops.schemas import (...)` block.

Then add the endpoint (a sensible place is right after the `/projects` endpoints, before the "Checklists" section — anywhere at module level after the imports works, since route order doesn't affect matching for these distinct static paths):

```python
@router.get("/technician-monitor", response_model=list[TechnicianMonitorRow])
async def technician_monitor(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dashboards.operations")),
):
    technicians = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.organization_id == organization_id,
                Role.code == "field_technician",
                User.status == UserStatus.active,
            )
            .distinct()
            .order_by(User.full_name)
        )
    ).scalars().all()

    today = date.today()
    now = datetime.now(timezone.utc)
    rows: list[TechnicianMonitorRow] = []
    for tech in technicians:
        projects = (
            await db.execute(
                select(Project).where(
                    Project.organization_id == organization_id,
                    Project.primary_technician_user_id == tech.id,
                )
            )
        ).scalars().all()
        assigned = sum(
            1 for p in projects
            if p.status in (ProjectStatus.planning, ProjectStatus.scheduled, ProjectStatus.in_progress)
        )
        completed_today = [p for p in projects if p.completed_date == today]
        avg_days = (
            sum((p.completed_date - p.created_at.date()).days for p in completed_today) / len(completed_today)
            if completed_today else None
        )
        logueado = tech.last_seen_at is not None and (now - as_utc(tech.last_seen_at)) <= timedelta(minutes=5)
        rows.append(
            TechnicianMonitorRow(
                user_id=tech.id,
                full_name=tech.full_name,
                logueado=logueado,
                en_cola=tech.is_available,
                casos_asignados=assigned,
                casos_gestionados_hoy=len(completed_today),
                tiempo_gestion_hoy_dias=avg_days,
            )
        )
    return rows
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py -k monitor_metrics -v`
Expected: PASS

- [ ] **Step 6: Run the permission test**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py -k requires_dashboards -v`
Expected: PASS (a `field_technician` doesn't hold `dashboards.operations` per `DEFAULT_ROLE_PERMISSIONS`, so this should already pass once the endpoint exists).

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/field_ops/schemas.py backend/app/modules/field_ops/router.py backend/tests/test_technician_monitor.py
git commit -m "Add GET /technician-monitor with today-scoped assigned/managed/handling-time metrics"
```

---

### Task 4: Backend — `PATCH /technicians/{user_id}/availability`

**Files:**
- Modify: `backend/app/modules/field_ops/schemas.py` (add `AvailabilityUpdate`)
- Modify: `backend/app/modules/field_ops/router.py` (add endpoint)
- Test: `backend/tests/test_technician_monitor.py`

**Interfaces:**
- Consumes: `User.is_available` (Task 1).
- Produces: `PATCH /api/v1/technicians/{user_id}/availability` with body `{ "is_available": bool }` → `TechnicianMonitorRow`-shaped subset is not required; returns `204` on success (simplest contract — the frontend re-fetches the monitor list on success rather than trusting a partial response).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_technician_monitor.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py -k availability_toggle -v`
Expected: FAIL — 404/405 (route doesn't exist yet).

- [ ] **Step 3: Add the request schema**

In `backend/app/modules/field_ops/schemas.py`, next to `TechnicianMonitorRow`:

```python
class AvailabilityUpdate(BaseModel):
    is_available: bool
```

- [ ] **Step 4: Implement the endpoint**

In `backend/app/modules/field_ops/router.py`, add `AvailabilityUpdate` to the schemas import block, then add (right after the `technician_monitor` endpoint from Task 3):

```python
@router.patch("/technicians/{user_id}/availability", status_code=204)
async def update_technician_availability(
    user_id: uuid.UUID,
    payload: AvailabilityUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dashboards.operations")),
):
    technician = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.id == user_id,
                User.organization_id == organization_id,
                Role.code == "field_technician",
            )
        )
    ).scalar_one_or_none()
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found.")
    technician.is_available = payload.is_available
    await db.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_technician_monitor.py -v`
Expected: all PASS (every test added in Tasks 2-4).

- [ ] **Step 6: Run the full backend suite once**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: same 4 pre-existing unrelated failures, everything else passing.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/field_ops/schemas.py backend/app/modules/field_ops/router.py backend/tests/test_technician_monitor.py
git commit -m "Add PATCH /technicians/{user_id}/availability"
```

---

### Task 5: Frontend — `TechnicianMonitorPage`, nav, and route

**Files:**
- Modify: `frontend/src/features/field-ops/api.ts`
- Create: `frontend/src/features/field-ops/TechnicianMonitorPage.tsx`
- Modify: `frontend/src/app/DashboardLayout.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `DataTable`, `Column<T>` from `@/components/DataTable` (phase 1); backend `GET /technician-monitor` and `PATCH /technicians/{user_id}/availability` (Tasks 3-4).
- Produces: route `/technician-monitor`, nav item gated on `hasPermission("dashboards.operations")`.

- [ ] **Step 1: Add API functions**

In `frontend/src/features/field-ops/api.ts`, add near the other project-related functions:

```ts
export interface TechnicianMonitorRow {
  user_id: string;
  full_name: string;
  logueado: boolean;
  en_cola: boolean;
  casos_asignados: number;
  casos_gestionados_hoy: number;
  tiempo_gestion_hoy_dias: number | null;
}

export async function listTechnicianMonitor(): Promise<TechnicianMonitorRow[]> {
  const res = await apiClient.get<TechnicianMonitorRow[]>("/technician-monitor");
  return res.data;
}

export async function updateTechnicianAvailability(userId: string, isAvailable: boolean): Promise<void> {
  await apiClient.patch(`/technicians/${userId}/availability`, { is_available: isAvailable });
}
```

- [ ] **Step 2: Create the page**

Create `frontend/src/features/field-ops/TechnicianMonitorPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listTechnicianMonitor, updateTechnicianAvailability, type TechnicianMonitorRow } from "./api";
import { DataTable, type Column } from "@/components/DataTable";

export function TechnicianMonitorPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["technician-monitor"],
    queryFn: listTechnicianMonitor,
    refetchInterval: 30_000,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ userId, isAvailable }: { userId: string; isAvailable: boolean }) =>
      updateTechnicianAvailability(userId, isAvailable),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["technician-monitor"] }),
  });

  const columns: Column<TechnicianMonitorRow>[] = [
    { key: "full_name", header: "Técnico" },
    {
      key: "logueado",
      header: "Logueado",
      render: (r) => <span className={`status-pill ${r.logueado ? "status-active" : "status-inactive"}`}>{r.logueado ? "Sí" : "No"}</span>,
    },
    {
      key: "en_cola",
      header: "En cola",
      render: (r) => (
        <button
          className="link-button"
          disabled={toggleMutation.isPending}
          onClick={() => toggleMutation.mutate({ userId: r.user_id, isAvailable: !r.en_cola })}
        >
          {r.en_cola ? "Disponible" : "No disponible"}
        </button>
      ),
    },
    { key: "casos_asignados", header: "Casos asignados" },
    { key: "casos_gestionados_hoy", header: "Casos gestionados hoy" },
    {
      key: "tiempo_gestion_hoy_dias",
      header: "Tiempo de gestión (hoy)",
      render: (r) => (r.tiempo_gestion_hoy_dias === null ? "—" : `${r.tiempo_gestion_hoy_dias.toFixed(1)} días`),
    },
  ];

  return (
    <div>
      <h1>Monitor de técnicos</h1>
      <p className="page-subtitle">Estado en vivo del equipo de campo — se actualiza automáticamente cada 30 segundos.</p>
      <DataTable columns={columns} rows={data ?? []} isLoading={isLoading} getRowKey={(r) => r.user_id} emptyMessage="Sin técnicos activos para mostrar." />
    </div>
  );
}
```

- [ ] **Step 3: Add the nav item**

In `frontend/src/app/DashboardLayout.tsx`, add to `NAV_ITEMS` (after the `Proyectos` entry, before `Facturación`):

```ts
  { to: "/technician-monitor", label: "Monitor de técnicos", icon: "◉", permissions: ["dashboards.operations"] },
```

- [ ] **Step 4: Add the route**

In `frontend/src/app/router.tsx`, add the import:

```ts
import { TechnicianMonitorPage } from "@/features/field-ops/TechnicianMonitorPage";
```

and add to the children array (after the `projects/:projectId` route):

```ts
      { path: "technician-monitor", element: <TechnicianMonitorPage /> },
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Build**

Run: `cd frontend && npx vite build`
Expected: succeeds.

- [ ] **Step 7: Manual browser verification**

With both dev servers running, logged in as a user with `dashboards.operations` (e.g. `pm@acme-demo.com` from the demo seed, or an org admin):
- Confirm "Monitor de técnicos" appears in the sidebar and navigates to `/technician-monitor`.
- Confirm each active field technician shows a row with their assigned/handled-today/handling-time numbers.
- Click a technician's "En cola" button — confirm it flips and the row refreshes.
- Confirm the page doesn't error when there are zero field technicians (empty state message shows).

Expected: page renders correctly, toggle works, no console errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/field-ops/api.ts frontend/src/features/field-ops/TechnicianMonitorPage.tsx frontend/src/app/DashboardLayout.tsx frontend/src/app/router.tsx
git commit -m "Add TechnicianMonitorPage (GTR-style technician monitor)"
```
