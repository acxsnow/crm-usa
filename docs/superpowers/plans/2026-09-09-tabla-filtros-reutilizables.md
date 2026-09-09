# Tabla y filtros reutilizables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable `FilterBar` + `DataTable` frontend pair backed by real SQL filters on the `/leads`, `/customers`, `/projects`, and `/applications` list endpoints, and migrate `LeadsPage`, `CustomersPage`, `ProjectsPage`, and `ApplicationsAdminPage` to use them.

**Architecture:** Backend list endpoints already share one pagination helper (`app/shared/pagination.py`: `pagination_params` + `paginate()`, `X-Total-Count` header) and `list_leads` already proves the filter pattern (`Query(None, alias=...)` + conditional `stmt.where(...)`). We extend that same pattern to the other three endpoints. On the frontend, `fetchPage()` (`frontend/src/lib/pagination.ts`) already forwards an `extraParams` object as query params — a new `useTableFilters` hook produces exactly that shape from URL-synced state, and two new presentational components (`FilterBar`, `DataTable`) replace the hand-rolled `<table>` markup in each page.

**Tech Stack:** FastAPI + SQLAlchemy (async) on the backend; React + TanStack Query + react-router-dom v6 (`useSearchParams`) + axios on the frontend. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-09-tabla-filtros-reutilizables-design.md`

## Global Constraints

- Filters resolve in SQL (backend `stmt.where(...)`), never by filtering an already-fetched page client-side.
- Text filters use case-insensitive `ILIKE '%value%'`.
- `InvoicesPage`, `UsersPage`, and `AuditLogPage` are out of scope for this plan.
- No new CSS palette — reuse existing tokens/classes in `frontend/src/index.css` (`--ink`, `--red`, `.data-table`, `.primary-button`, `.link-button`, `.inline-form`).
- Existing `.data-table` header style (light background, uppercase mono label — see `index.css:879-887`) is kept as-is; it already matches the app's identity, so `DataTable` does not introduce a dark header.
- One clarification from the spec, decided while mapping real schemas: `ApplicationResponse` carries no applicant name (only `lead_id`/`customer_id`), so the applications text filter (`q`) searches `program_code` instead of a lead/customer name — searching a name would require joining `Lead`/`Customer` (nullable either way) for no field the table currently displays.

---

## File Structure

**Backend — modify only, no new files:**
- `backend/app/modules/crm/router.py` — add `q` to `list_leads`; add `q`/`status` to `list_customers`; convert `list_applications` to `paginate()` and add `status`/`q`.
- `backend/app/modules/field_ops/router.py` — add `status`/`q`/`technician_id` to `list_projects`; add `Query` to its fastapi import.

**Backend — new test files:**
- `backend/tests/test_list_filters.py` — one test class per endpoint's new filters.

**Frontend — new shared components:**
- `frontend/src/components/FilterBar.tsx` — filter panel (text/select fields, draft state, Buscar/Limpiar).
- `frontend/src/components/DataTable.tsx` — generic table renderer (columns, rows, loading/empty states).
- `frontend/src/lib/useTableFilters.ts` — URL-synced `{ filters, page }` state + `extraParams` for `fetchPage`.

**Frontend — modify:**
- `frontend/src/index.css` — add `.filter-bar` styles.
- `frontend/src/features/crm/api.ts` — extend `listLeadsPage`/`listCustomersPage` filter params; add `listApplicationsPage`; remove now-unused `listApplications`.
- `frontend/src/features/field-ops/api.ts` — extend `listProjectsPage` filter params.
- `frontend/src/features/crm/LeadsPage.tsx`, `frontend/src/features/crm/CustomersPage.tsx`, `frontend/src/features/crm/ApplicationsAdminPage.tsx`, `frontend/src/features/field-ops/ProjectsPage.tsx` — replace hand-rolled tables with `FilterBar` + `DataTable` + `useTableFilters`.

---

### Task 1: Backend — `q` filter on `/leads`

**Files:**
- Modify: `backend/app/modules/crm/router.py:55-67` (`list_leads`)
- Test: `backend/tests/test_list_filters.py` (new file)

**Interfaces:**
- Produces: `GET /api/v1/leads?q=<text>` — case-insensitive substring match on `full_name`, `phone`, or `email`. Combines with the existing `status` param via `AND`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_list_filters.py`:

```python
from app.modules.crm.models import Customer, Lead, LeadStatus


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_leads_q_filter_matches_name_phone_or_email(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    db.add_all([
        Lead(organization_id=org_id, full_name="Rosa Gutierrez", phone="7142320526", email="rosa@example.com", status=LeadStatus.new),
        Lead(organization_id=org_id, full_name="Miguel Vargas", phone="7142776702", email="miguel@example.com", status=LeadStatus.new),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/leads", params={"q": "rosa"}, headers=headers)
    assert resp.status_code == 200
    names = [lead["full_name"] for lead in resp.json()]
    assert names == ["Rosa Gutierrez"]

    resp = await app_client.get("/api/v1/leads", params={"q": "7142776702"}, headers=headers)
    assert [lead["full_name"] for lead in resp.json()] == ["Miguel Vargas"]

    resp = await app_client.get("/api/v1/leads", params={"q": "no-such-lead"}, headers=headers)
    assert resp.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_leads_q_filter_matches_name_phone_or_email -v`
Expected: FAIL — `q` param is silently ignored, so it returns both leads on the first assertion.

- [ ] **Step 3: Implement the filter**

In `backend/app/modules/crm/router.py`, `list_leads` (around line 55-67):

```python
@router.get("/leads", response_model=list[LeadResponse])
async def list_leads(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Lead).where(Lead.organization_id == organization_id).order_by(Lead.created_at.desc())
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Lead.full_name.ilike(like)) | (Lead.phone.ilike(like)) | (Lead.email.ilike(like))
        )
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_leads_q_filter_matches_name_phone_or_email -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/crm/router.py backend/tests/test_list_filters.py
git commit -m "$(cat <<'EOF'
Add text search filter to GET /leads

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Backend — `q`/`status` filters on `/customers`

**Files:**
- Modify: `backend/app/modules/crm/router.py:169-178` (`list_customers`)
- Test: `backend/tests/test_list_filters.py`

**Interfaces:**
- Produces: `GET /api/v1/customers?q=<text>&status=<active|inactive>` — `q` matches `legal_name`, `email`, or `main_phone`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_list_filters.py`:

```python
from app.modules.crm.models import CustomerStatus


async def test_customers_q_and_status_filters(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    db.add_all([
        Customer(organization_id=org_id, legal_name="Acme Roofing", email="ops@acme.test", status=CustomerStatus.active),
        Customer(organization_id=org_id, legal_name="Old Client Inc", email="old@client.test", status=CustomerStatus.inactive),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/customers", params={"q": "acme"}, headers=headers)
    assert [c["legal_name"] for c in resp.json()] == ["Acme Roofing"]

    resp = await app_client.get("/api/v1/customers", params={"status": "inactive"}, headers=headers)
    assert [c["legal_name"] for c in resp.json()] == ["Old Client Inc"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_customers_q_and_status_filters -v`
Expected: FAIL (both filters ignored, both customers come back for each call).

- [ ] **Step 3: Implement the filters**

In `backend/app/modules/crm/router.py`, `list_customers` (around line 169-178):

```python
@router.get("/customers", response_model=list[CustomerResponse])
async def list_customers(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.read")),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Customer).where(Customer.organization_id == organization_id).order_by(Customer.legal_name)
    if status_filter:
        stmt = stmt.where(Customer.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Customer.legal_name.ilike(like)) | (Customer.email.ilike(like)) | (Customer.main_phone.ilike(like))
        )
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_customers_q_and_status_filters -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/crm/router.py backend/tests/test_list_filters.py
git commit -m "$(cat <<'EOF'
Add text and status filters to GET /customers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Backend — `status`/`q`/`technician_id` filters on `/projects`

**Files:**
- Modify: `backend/app/modules/field_ops/router.py:1-8` (imports) and `:119-129` (`list_projects`)
- Test: `backend/tests/test_list_filters.py`

**Interfaces:**
- Produces: `GET /api/v1/projects?status=<ProjectStatus>&q=<text>&technician_id=<uuid>` — `q` matches `title` or `address_street`; existing `_scope_projects_stmt` role-scoping (self-only for `projects.read_assigned`) still applies after these filters.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_list_filters.py`:

```python
from app.modules.field_ops.models import Project, ProjectStatus


async def test_projects_status_q_and_technician_filters(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    customer = Customer(organization_id=org_id, legal_name="Acme Roofing", status=CustomerStatus.active)
    db.add(customer)
    await db.flush()

    tech_a = active_admin_user.id
    db.add_all([
        Project(organization_id=org_id, customer_id=customer.id, title="HVAC install - Main St", status=ProjectStatus.scheduled, primary_technician_user_id=tech_a),
        Project(organization_id=org_id, customer_id=customer.id, title="Roof repair - Oak Ave", status=ProjectStatus.completed, primary_technician_user_id=None),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/projects", params={"status": "completed"}, headers=headers)
    assert [p["title"] for p in resp.json()] == ["Roof repair - Oak Ave"]

    resp = await app_client.get("/api/v1/projects", params={"q": "main st"}, headers=headers)
    assert [p["title"] for p in resp.json()] == ["HVAC install - Main St"]

    resp = await app_client.get("/api/v1/projects", params={"technician_id": str(tech_a)}, headers=headers)
    assert [p["title"] for p in resp.json()] == ["HVAC install - Main St"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_projects_status_q_and_technician_filters -v`
Expected: FAIL — all three assertions return both projects.

- [ ] **Step 3: Implement the filters**

In `backend/app/modules/field_ops/router.py`, add `Query` to the fastapi import (line 4):

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
```

Then update `list_projects` (around line 119-129):

```python
@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    technician_id: uuid.UUID | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Project).where(Project.organization_id == organization_id).order_by(Project.created_at.desc())
    stmt = _scope_projects_stmt(stmt, current_user)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Project.title.ilike(like)) | (Project.address_street.ilike(like)))
    if technician_id:
        stmt = stmt.where(Project.primary_technician_user_id == technician_id)
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_projects_status_q_and_technician_filters -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/field_ops/router.py backend/tests/test_list_filters.py
git commit -m "$(cat <<'EOF'
Add status, text, and technician filters to GET /projects

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Backend — paginate `/applications` and add `status`/`q`

**Files:**
- Modify: `backend/app/modules/crm/router.py:253-262` (`list_applications`)
- Test: `backend/tests/test_list_filters.py`

**Interfaces:**
- Produces: `GET /api/v1/applications?status=<str>&q=<text>` — now paginated like the other list endpoints (`X-Total-Count` header, `limit`/`offset` via `pagination_params`) instead of a flat `.limit(500)`. `q` matches `program_code` (see Global Constraints for why — `ApplicationResponse` has no applicant name field).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_list_filters.py`:

```python
from app.modules.crm.models import Application


async def test_applications_status_q_filters_and_pagination_header(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    db.add_all([
        Application(organization_id=org_id, program_code="CARE", form_version="1", status="pending_review"),
        Application(organization_id=org_id, program_code="CALFRESH", form_version="1", status="approved"),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/applications", params={"status": "approved"}, headers=headers)
    assert resp.status_code == 200
    assert [a["program_code"] for a in resp.json()] == ["CALFRESH"]
    assert resp.headers["x-total-count"] == "1"

    resp = await app_client.get("/api/v1/applications", params={"q": "care"}, headers=headers)
    assert [a["program_code"] for a in resp.json()] == ["CARE"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_applications_status_q_filters_and_pagination_header -v`
Expected: FAIL — `status`/`q` ignored, and `x-total-count` header is missing (current endpoint doesn't set it).

- [ ] **Step 3: Implement the filters and pagination**

In `backend/app/modules/crm/router.py`, `list_applications` (around line 253-262):

```python
@router.get("/applications", response_model=list[ApplicationResponse])
async def list_applications(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Application).where(Application.organization_id == organization_id).order_by(Application.created_at.desc())
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    if q:
        stmt = stmt.where(Application.program_code.ilike(f"%{q}%"))
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)
```

Note this adds a `response: Response` parameter that wasn't there before — confirm no other code calls `list_applications` directly as a Python function (it's only reached via the route).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_list_filters.py::test_applications_status_q_filters_and_pagination_header -v`
Expected: PASS

- [ ] **Step 5: Run the full filter test file plus existing CRM tests**

Run: `cd backend && python -m pytest tests/test_list_filters.py tests/test_lead_import.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/crm/router.py backend/tests/test_list_filters.py
git commit -m "$(cat <<'EOF'
Paginate GET /applications and add status/q filters

Matches the limit/offset + X-Total-Count pattern already used by
/leads, /customers, and /projects.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Frontend — `FilterBar`, `DataTable`, `useTableFilters`

**Files:**
- Create: `frontend/src/components/FilterBar.tsx`
- Create: `frontend/src/components/DataTable.tsx`
- Create: `frontend/src/lib/useTableFilters.ts`
- Modify: `frontend/src/index.css` (append `.filter-bar` rules)

**Interfaces:**
- Produces (consumed by Tasks 6-7):
  - `FilterBar`: `type FilterFieldDef = { key: string; label: string; type: "text"; placeholder?: string } | { key: string; label: string; type: "select"; options: { value: string; label: string }[] }`; `<FilterBar fields={FilterFieldDef[]} values={Record<string,string>} onApply={(v: Record<string,string>) => void} onClear={() => void} />`.
  - `DataTable`: `type Column<T> = { key: string; header: string; render?: (row: T) => ReactNode }`; `<DataTable<T> columns={Column<T>[]} rows={T[]} isLoading={boolean} emptyMessage?={string} getRowKey={(row: T) => string} />`.
  - `useTableFilters`: `function useTableFilters(): { filters: Record<string,string>; page: number; setFilters: (f: Record<string,string>) => void; clearFilters: () => void; setPage: (p: number) => void; extraParams: Record<string,string> }`.

This task has no backend dependency and no page migration — it ships the three files plus a manual smoke check. No automated test is written for these (per spec: presentational components, verified through the pages that use them in later tasks); this step is verified by a type-check + build instead.

- [ ] **Step 1: Create `useTableFilters`**

`frontend/src/lib/useTableFilters.ts`:

```ts
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export function useTableFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => {
    const result: Record<string, string> = {};
    for (const [key, value] of searchParams.entries()) {
      if (key !== "page") result[key] = value;
    }
    return result;
  }, [searchParams]);

  const page = Number(searchParams.get("page") ?? "1") || 1;

  const setFilters = useCallback(
    (next: Record<string, string>) => {
      const params: Record<string, string> = {};
      for (const [key, value] of Object.entries(next)) {
        if (value) params[key] = value;
      }
      setSearchParams(params);
    },
    [setSearchParams]
  );

  const clearFilters = useCallback(() => setSearchParams({}), [setSearchParams]);

  const setPage = useCallback(
    (nextPage: number) => {
      const params: Record<string, string> = {};
      for (const [key, value] of Object.entries(filters)) params[key] = value;
      params.page = String(nextPage);
      setSearchParams(params);
    },
    [filters, setSearchParams]
  );

  return { filters, page, setFilters, clearFilters, setPage, extraParams: filters };
}
```

- [ ] **Step 2: Create `FilterBar`**

`frontend/src/components/FilterBar.tsx`:

```tsx
import { useState, type FormEvent } from "react";

export type FilterFieldDef =
  | { key: string; label: string; type: "text"; placeholder?: string }
  | { key: string; label: string; type: "select"; options: { value: string; label: string }[] };

interface FilterBarProps {
  fields: FilterFieldDef[];
  values: Record<string, string>;
  onApply: (values: Record<string, string>) => void;
  onClear: () => void;
}

export function FilterBar({ fields, values, onApply, onClear }: FilterBarProps) {
  const [draft, setDraft] = useState<Record<string, string>>(values);
  const [open, setOpen] = useState(true);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onApply(draft);
  }

  function handleClear() {
    setDraft({});
    onClear();
  }

  return (
    <form className="filter-bar" onSubmit={handleSubmit}>
      <button type="button" className="filter-bar-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} FILTROS
      </button>
      {open && (
        <>
          <div className="filter-bar-fields">
            {fields.map((field) => (
              <label key={field.key} className="filter-bar-field">
                <span>{field.label}</span>
                {field.type === "text" ? (
                  <input
                    type="text"
                    placeholder={field.placeholder}
                    value={draft[field.key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
                  />
                ) : (
                  <select
                    value={draft[field.key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
                  >
                    <option value="">Todos</option>
                    {field.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                )}
              </label>
            ))}
          </div>
          <div className="filter-bar-actions">
            <button type="submit" className="primary-button">
              Buscar
            </button>
            <button type="button" className="link-button" onClick={handleClear}>
              Limpiar
            </button>
          </div>
        </>
      )}
    </form>
  );
}
```

- [ ] **Step 3: Create `DataTable`**

`frontend/src/components/DataTable.tsx`:

```tsx
import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  isLoading: boolean;
  emptyMessage?: string;
  getRowKey: (row: T) => string;
}

export function DataTable<T>({
  columns,
  rows,
  isLoading,
  emptyMessage = "Sin resultados para mostrar.",
  getRowKey,
}: DataTableProps<T>) {
  if (isLoading) return <p>Cargando...</p>;

  function cellValue(row: T, key: string): ReactNode {
    const value = (row as Record<string, unknown>)[key];
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)}>
              {columns.map((col) => (
                <td key={col.key}>{col.render ? col.render(row) : cellValue(row, col.key)}</td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="page-subtitle">
                {emptyMessage}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Add `.filter-bar` styles**

Append to `frontend/src/index.css` (after the `.data-table` block, around line 913):

```css
/* ---------- Filter bar ---------- */

.filter-bar {
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 0.9rem 1.1rem;
  margin-bottom: 1rem;
}

.filter-bar-toggle {
  background: none;
  border: none;
  padding: 0;
  font-family: var(--mono-font);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--ink-soft);
  cursor: pointer;
}

.filter-bar-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.filter-bar-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.78rem;
  color: var(--ink-soft);
  min-width: 180px;
}

.filter-bar-field input,
.filter-bar-field select {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.5rem 0.65rem;
  font: inherit;
  color: var(--ink);
  background: #fff;
}

.filter-bar-actions {
  display: flex;
  gap: 0.6rem;
  margin-top: 0.9rem;
}
```

- [ ] **Step 5: Type-check and build**

Run: `cd frontend && npx tsc --noEmit && npx vite build`
Expected: both succeed with no errors (these three files are unused by any page yet, so this only confirms they compile).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/FilterBar.tsx frontend/src/components/DataTable.tsx frontend/src/lib/useTableFilters.ts frontend/src/index.css
git commit -m "$(cat <<'EOF'
Add reusable FilterBar, DataTable, and useTableFilters

Foundation for migrating list pages to real, server-side filters.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Migrate `LeadsPage` and `CustomersPage`

**Files:**
- Modify: `frontend/src/features/crm/api.ts:22`, `:53` (`listLeadsPage`, `listCustomersPage`)
- Modify: `frontend/src/features/crm/LeadsPage.tsx`
- Modify: `frontend/src/features/crm/CustomersPage.tsx`
- Modify: `frontend/src/app/DashboardHome.tsx:32` (only caller passing `listLeadsPage`'s old positional `status` argument)

**Interfaces:**
- Consumes: `FilterBar`, `DataTable`, `useTableFilters` from Task 5; `fetchPage` (existing).
- Produces: `listLeadsPage(page, pageSize, extraParams?)`, `listCustomersPage(page, pageSize, extraParams?)` — both now take an optional filter-params object forwarded straight to `fetchPage`.

- [ ] **Step 1: Extend `listLeadsPage` and `listCustomersPage`**

In `frontend/src/features/crm/api.ts`, replace line 22-24:

```ts
export async function listLeadsPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Lead>> {
  return fetchPage<Lead>("/leads", page, pageSize, extraParams);
}
```

And replace line 53-55:

```ts
export async function listCustomersPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Customer>> {
  return fetchPage<Customer>("/customers", page, pageSize, extraParams);
}
```

This drops the old positional `status?: Lead["status"]` third argument from `listLeadsPage`. Grep shows one other caller besides `LeadsPage.tsx`: `frontend/src/app/DashboardHome.tsx:32` calls `listLeadsPage(1, 1, status as "new" | "contacted" | "qualified")`, passing a bare string — this now needs to pass `{ status }` instead. Update that line to:

```ts
const statuses = await Promise.all(
  ["new", "contacted", "qualified"].map((status) => listLeadsPage(1, 1, { status }))
);
```

(`listCustomersPage(1, 1)` at `DashboardHome.tsx:39` and `loadAllPages(listProjectsPage)` at `DashboardHome.tsx:44` both call with two args only, so the new optional third parameter on `listCustomersPage`/`listProjectsPage` doesn't affect them — TypeScript allows passing a function with an extra optional parameter wherever a two-parameter function type is expected.)

- [ ] **Step 2: Migrate `LeadsPage`'s table and add filters**

In `frontend/src/features/crm/LeadsPage.tsx`, add imports:

```ts
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
```

Replace the `page` state and query with `useTableFilters`:

```ts
const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
const { data, isLoading } = useQuery({
  queryKey: ["leads", page, extraParams],
  queryFn: () => listLeadsPage(page, PAGE_SIZE, extraParams),
});
const leads = data?.items;
```

Define filter fields and table columns above the `return`:

```ts
const filterFields: FilterFieldDef[] = [
  { key: "q", label: "Buscar", type: "text", placeholder: "Nombre, teléfono o email" },
  {
    key: "status",
    label: "Estado",
    type: "select",
    options: [
      { value: "new", label: "Nueva" },
      { value: "contacted", label: "Contactado" },
      { value: "qualified", label: "Calificado" },
      { value: "disqualified", label: "Descalificado" },
      { value: "converted", label: "Convertido" },
    ],
  },
];

const columns: Column<Lead>[] = [
  { key: "full_name", header: "Nombre" },
  {
    key: "address",
    header: "Dirección",
    render: (l) => [l.address_street, l.address_unit, l.address_city].filter(Boolean).join(", ") || "—",
  },
  { key: "phone", header: "Teléfono", render: (l) => l.phone ?? "—" },
  { key: "benefit_type", header: "Beneficio", render: (l) => l.benefit_type ?? "—" },
  { key: "status", header: "Estado", render: (l) => <span className={`status-pill status-${l.status}`}>{l.status}</span> },
  {
    key: "actions",
    header: "",
    render: (l) => (
      <>
        <Link className="link-button" to={`/applications/new?leadId=${l.id}`}>
          Abrir aplicación
        </Link>{" "}
        {l.status !== "converted" && (
          <button className="link-button" disabled={convertMutation.isPending} onClick={() => convertMutation.mutate(l.id)}>
            Convertir
          </button>
        )}
      </>
    ),
  },
];
```

Replace the existing `<table className="data-table">...</table>` block (and its surrounding `isLoading` ternary) with:

```tsx
<FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
<DataTable columns={columns} rows={leads ?? []} isLoading={isLoading} getRowKey={(l) => l.id} emptyMessage="Sin prospectos para mostrar." />
{data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
```

Leave the existing create-lead `<form>` above this untouched.

- [ ] **Step 3: Migrate `CustomersPage`'s table and add filters**

In `frontend/src/features/crm/CustomersPage.tsx`, same import additions, then:

```ts
const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
const { data, isLoading } = useQuery({
  queryKey: ["customers", page, extraParams],
  queryFn: () => listCustomersPage(page, PAGE_SIZE, extraParams),
});
const customers = data?.items;

const filterFields: FilterFieldDef[] = [
  { key: "q", label: "Buscar", type: "text", placeholder: "Nombre, email o teléfono" },
  {
    key: "status",
    label: "Estado",
    type: "select",
    options: [
      { value: "active", label: "Activo" },
      { value: "inactive", label: "Inactivo" },
    ],
  },
];

const columns: Column<Customer>[] = [
  { key: "legal_name", header: "Nombre", render: (c) => <Link to={`/customers/${c.id}`}>{c.legal_name}</Link> },
  { key: "main_phone", header: "Teléfono", render: (c) => c.main_phone ?? "—" },
  { key: "email", header: "Email", render: (c) => c.email ?? "—" },
  { key: "status", header: "Estado", render: (c) => <span className={`status-pill status-${c.status}`}>{c.status}</span> },
];
```

Replace the `isLoading ? <p>Cargando...</p> : (<div className="table-wrap">...)` block with:

```tsx
<FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
<DataTable columns={columns} rows={customers ?? []} isLoading={isLoading} getRowKey={(c) => c.id} emptyMessage="Sin clientes para mostrar." />
{data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
```

- [ ] **Step 4: Fix the `listLeadsPage` call site in `DashboardHome.tsx`**

Apply the `DashboardHome.tsx:32` change shown in Step 1 above.

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. Fix any prop/type mismatches (e.g. `Column<Lead>`'s `render` return type) before proceeding.

- [ ] **Step 6: Manual browser verification**

Run: `cd frontend && npm run dev` (and the backend dev server per the project's `run` skill/README), then in the browser:
- Open `/leads`: type a name fragment into the search box, click Buscar — list narrows; click Limpiar — list resets; pick a status — list narrows; combine both.
- Open `/customers`: same check with its `q`/`status` fields.
- Confirm pagination still works after applying a filter (page resets to 1 on a new filter application via `setFilters`).
- Open `/` (dashboard home): confirm the "active leads" stat still loads without a console error (this is what exercises the fixed `DashboardHome.tsx` call site).

Expected: filters visibly narrow results in both pages; dashboard home still loads its lead count; no console errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/crm/api.ts frontend/src/features/crm/LeadsPage.tsx frontend/src/features/crm/CustomersPage.tsx frontend/src/app/DashboardHome.tsx
git commit -m "$(cat <<'EOF'
Migrate LeadsPage and CustomersPage to FilterBar + DataTable

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Migrate `ProjectsPage` and `ApplicationsAdminPage`

**Files:**
- Modify: `frontend/src/features/field-ops/api.ts:32-34` (`listProjectsPage`)
- Modify: `frontend/src/features/crm/api.ts` (add `listApplicationsPage`, remove `listApplications`)
- Modify: `frontend/src/features/field-ops/ProjectsPage.tsx`
- Modify: `frontend/src/features/crm/ApplicationsAdminPage.tsx`

**Interfaces:**
- Consumes: `FilterBar`, `DataTable`, `useTableFilters` (Task 5); `listUsers` from `@/features/users/api` (existing, `users.manage`-gated — see step 2 for the graceful-degradation handling).
- Produces: `listProjectsPage(page, pageSize, extraParams?)`; `listApplicationsPage(page, pageSize, extraParams?): Promise<Page<Application>>`.

- [ ] **Step 1: Extend `listProjectsPage`; add `listApplicationsPage`**

In `frontend/src/features/field-ops/api.ts`, replace line 32-34:

```ts
export async function listProjectsPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Project>> {
  return fetchPage<Project>("/projects", page, pageSize, extraParams);
}
```

In `frontend/src/features/crm/api.ts`, replace line 77 (`listApplications`) with:

```ts
export async function listApplicationsPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Application>> {
  return fetchPage<Application>("/applications", page, pageSize, extraParams);
}
```

- [ ] **Step 2: Migrate `ProjectsPage`**

In `frontend/src/features/field-ops/ProjectsPage.tsx`, add imports:

```ts
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import { listUsers } from "@/features/users/api";
```

Replace the `page`/query setup:

```ts
const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
const { data, isLoading } = useQuery({
  queryKey: ["projects", page, extraParams],
  queryFn: () => listProjectsPage(page, PAGE_SIZE, extraParams),
});
const projects = data?.items;
const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });
// Best-effort: only users with users.manage (org admins) can list users, so
// technicians reading their own assigned projects simply won't get this
// filter option — same graceful-degradation pattern as AuditLogPage.
const { data: allUsers } = useQuery({ queryKey: ["users"], queryFn: listUsers, retry: false, throwOnError: false });
```

Define filter fields (built once `allUsers` is known) and columns above the `return`:

```ts
const filterFields: FilterFieldDef[] = [
  { key: "q", label: "Buscar", type: "text", placeholder: "Título o dirección" },
  {
    key: "status",
    label: "Estado",
    type: "select",
    options: [
      { value: "planning", label: "Planeación" },
      { value: "scheduled", label: "Programado" },
      { value: "in_progress", label: "En progreso" },
      { value: "completed", label: "Completado" },
      { value: "cancelled", label: "Cancelado" },
    ],
  },
  ...(allUsers && allUsers.items.length > 0
    ? [
        {
          key: "technician_id",
          label: "Técnico",
          type: "select" as const,
          options: allUsers.items.map((u) => ({ value: u.id, label: u.full_name })),
        },
      ]
    : []),
];

const columns: Column<Project>[] = [
  { key: "title", header: "Proyecto" },
  { key: "address", header: "Dirección", render: (p) => [p.address_street, p.address_unit].filter(Boolean).join(", ") || "—" },
  { key: "status", header: "Estado", render: (p) => <span className={`status-pill status-${p.status}`}>{p.status}</span> },
  { key: "scheduled_date", header: "Programado", render: (p) => p.scheduled_date ?? "—" },
  {
    key: "actions",
    header: "",
    render: (p) => (
      <Link className="link-button" to={`/projects/${p.id}`}>
        Ver
      </Link>
    ),
  },
];
```

Replace the existing `<table className="data-table">...</table>` with:

```tsx
<FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
<DataTable columns={columns} rows={projects ?? []} isLoading={isLoading} getRowKey={(p) => p.id} emptyMessage="Sin proyectos para mostrar." />
{data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
```

Remove the old top-level `if (isLoading) return <p>Cargando...</p>;` guard (the create-project form above the table needs to keep rendering even while the table area shows its own loading state) — `DataTable` now owns the loading display.

- [ ] **Step 3: Migrate `ApplicationsAdminPage`**

Rewrite `frontend/src/features/crm/ApplicationsAdminPage.tsx` in full (it's currently a single unpaginated, unfiltered listing with no `page` state):

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listApplicationsPage, updateApplication, type Application } from "./api";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import { PaginationControls } from "@/components/PaginationControls";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "pending_review", label: "Pendiente de revisión" },
  { value: "correction_requested", label: "Solicitar corrección" },
  { value: "ready_to_submit", label: "Lista para someter" },
  { value: "submitted", label: "Sometida" },
  { value: "approved", label: "Aprobada" },
  { value: "rejected", label: "Rechazada" },
];

export function ApplicationsAdminPage() {
  const client = useQueryClient();
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["applications", page, extraParams],
    queryFn: () => listApplicationsPage(page, PAGE_SIZE, extraParams),
  });
  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateApplication(id, { status }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["applications"] }),
  });

  const filterFields: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Código de programa" },
    { key: "status", label: "Estado", type: "select", options: STATUS_OPTIONS },
  ];

  const columns: Column<Application>[] = [
    {
      key: "program_code",
      header: "Programa",
      render: (app) => (
        <>
          <strong>{app.program_code}</strong>
          <br />
          <small>{app.id.slice(0, 8)}</small>
        </>
      ),
    },
    { key: "status", header: "Estado", render: (app) => <span className="status-pill">{app.status.split("_").join(" ")}</span> },
    { key: "created_at", header: "Creada", render: (app) => new Date(app.created_at).toLocaleDateString("es-CO") },
    {
      key: "review",
      header: "Revisión",
      render: (app) => (
        <select value={app.status} onChange={(e) => mutation.mutate({ id: app.id, status: e.target.value })}>
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ),
    },
  ];

  return (
    <div className="list-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">CONTROL ADMINISTRATIVO</p>
          <h1>Aplicaciones</h1>
          <p className="page-subtitle">Revisa la documentación antes de someter cada caso al programa.</p>
        </div>
      </div>
      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={data?.items ?? []} isLoading={isLoading} getRowKey={(app) => app.id} emptyMessage="Sin aplicaciones para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
```

(`useState` import is unused now — omit it, as shown above.)

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Manual browser verification**

With both dev servers running:
- Open `/projects`: filter by status, by text (title/address), and — logged in as the seeded admin — by técnico; confirm Limpiar resets all three and pagination still works.
- Open `/applications`: filter by status (dropdown already had these values before — confirm they still work), filter by program code text, confirm Limpiar and pagination work, and confirm changing the "Revisión" `<select>` still updates status as before.

Expected: all filters narrow results; existing status-change dropdown in Aplicaciones still functions; no console errors.

- [ ] **Step 6: Run the full backend test suite once more**

Run: `cd backend && python -m pytest -v`
Expected: all PASS (confirms Task 4's `response: Response` addition to `list_applications` didn't break anything else that touches that route).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/field-ops/api.ts frontend/src/features/crm/api.ts frontend/src/features/field-ops/ProjectsPage.tsx frontend/src/features/crm/ApplicationsAdminPage.tsx
git commit -m "$(cat <<'EOF'
Migrate ProjectsPage and ApplicationsAdminPage to FilterBar + DataTable

Also converts ApplicationsAdminPage from an unpaginated single fetch
to the same page/filter pattern as the other list pages.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
