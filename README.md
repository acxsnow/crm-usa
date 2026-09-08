# CRM + Field Operations Platform

Implementation of `CRM_Field_Operations_MVP_Specification.md`, built in the phases from
section 17 of that spec, adapted to the real domain confirmed with Mateo: door-to-door
(PAP) enrollment into utility/government-funded HVAC programs (CARE, MEDICAL, CalFresh,
HEEHRA), inspection, installation, signed attestation, and per-unit reimbursement — see
`docs/delivery-backlog.md` for the full domain writeup. This repository currently
contains **Phase 1: Foundation**, **Phase 2: CRM**, **Phase 3: Field Operations**,
**Phase 4: Invoice control**, and the security/permissions portion of **Phase 5:
Hardening**.

## What's implemented

### Phase 1: Foundation

- **Backend** (`backend/`, FastAPI + SQLAlchemy 2 async + PostgreSQL):
  - Organization, PlanLimit, User, Role, Permission, UserRole, Invitation,
    PasswordResetToken, AuditEvent models + Alembic migration (`0001_initial`).
  - Auth: login (rate-limited, generic error message), JWT access/refresh tokens,
    refresh, logout, password-reset request/confirm (single-use, 60-minute token,
    never reveals whether an email exists), invitation accept.
  - RBAC: full permission catalog and default role → permission matrix from spec
    5.2/5.3, enforced server-side via a `require_permission(...)` dependency on
    every protected route.
  - Multi-tenant isolation: every business query is scoped by the authenticated
    user's `organization_id`, never a client-supplied value (spec 8.3).
  - Users administration: invite, activate/deactivate, 30-active-user plan limit
    enforcement with a clear error at the limit.
  - Organization settings and roles/permissions read endpoints.
  - Append-only audit log (`audit_events`) for login, password reset, invitations,
    user activation/deactivation, and organization settings changes.
  - `scripts/seed.py` seeds the permission catalog + default system roles, and
    optionally a demo organization with an admin login.
  - Test suite (pytest + httpx + in-memory SQLite): 14 tests covering login,
    generic error messages, inactive-user lockout, rate limiting, password reset,
    RBAC enforcement, plan-limit enforcement, and cross-tenant isolation. All pass.

- **Frontend** (`frontend/`, React 18 + TypeScript + Vite, PWA-enabled):
  - Auth pages: login, forgot password, reset password, accept invitation.
  - Axios API client with automatic access-token refresh on 401.
  - Auth context exposing the current user, roles, and permissions.
  - Permission-aware protected routing and sidebar navigation shell.
  - Type-checks clean (`tsc -b`) and builds clean (`vite build`).

- **Infrastructure**: `docker-compose.yml` (Postgres, Redis, API, Celery worker,
  frontend dev server) for local development; Dockerfiles for API and frontend.

### Phase 2: CRM

- **Backend**: Customer, CustomerContact, Lead, PipelineStage (org-configurable,
  seeded with the funder-program stages: Nueva → Contactada → Solicitud enviada →
  En revisión → Aprobada → Instalación → Ganada, plus Lista de espera / Rechazada /
  Perdida), FunderStatus (org-configurable catalog of the funder's own reported
  status — Pendiente/En revisión/Aprobado/Instalado/Rechazado/En espera — separate
  from our pipeline stage), Opportunity (with `benefit_type`, `funder_program`,
  `application_number`, `approval_code`, a `funder_status` FK, `utility_account_number`,
  `meter_number`, `unit_type`, `scheduled_install_date`, and a property address — one
  Opportunity per property/space), Activity, Quote + QuoteLineItem models + migration
  (`0002_crm`).
  - Lead duplicate detection by normalized email/phone/address (never auto-merges).
  - Lead → Customer + Contact + Opportunity conversion endpoint.
  - Opportunity pipeline stage changes (requires a loss reason on a "lost" stage)
    and an independent funder-status change (`funder_status_code` on create/update).
  - Customer 360 endpoint aggregating opportunities, activities, and quotes.
  - Quote line items with automatic total calculation and sequential numbering
    (`COT-0001`, ...).
  - **CSV importer** (`POST /leads/import`) for the existing spreadsheets, with a
    caller-supplied column mapping (the source sheets vary by mobile-home park) and
    the same duplicate detection used for manual entry.
  - 9 new tests (lead conversion, duplicate detection, stage-change validation,
    quote totals, customer 360, org isolation, CSV import, funder-status catalog) —
    23 passing total.
- **Frontend**: Leads list with inline create form, duplicate warning, and a
  one-click convert action; Customers list + a 360-view detail page; an
  Opportunity pipeline board grouped by stage with inline stage and
  funder-status changes.

### Phase 3: Field Operations

- **Backend**: Project (one per property/space — created from an Opportunity
  or manually), ChecklistTemplate + ChecklistTemplateItem (org-configurable,
  seeded with a default HVAC free-install checklist), ProjectChecklistItem
  (a **snapshot** copy of the template applied at creation time, so later
  template edits never mutate an in-progress project), Task + TaskComment,
  Evidence, Attestation models + migration (`0003_field_ops`).
  - Checklist items marked `requires_evidence` **block completion** until at
    least one Evidence row exists for that item.
  - **Evidence upload** (`POST /projects/{id}/evidence`): captures GPS
    (mandatory whenever the browser allows it) and burns a **visible
    watermark** (coordinates + timestamp) into the stored image —
    `app/modules/field_ops/watermark.py` — this was an explicit requirement,
    not just EXIF metadata. Files are stored on local disk under
    `backend/storage/` for now; swapping to S3 with signed URLs (spec
    section 12) only touches `field_ops/storage.py`.
  - **Digital signature capture**: the technician signs from the CRM and the
    customer signs from a secure, single-use link delivered by email; once both
    signatures are present, an attestation PDF is generated automatically
    (`app/modules/field_ops/pdf.py`, via ReportLab) embedding both signature
    images, the project/customer details, and the checklist status —
    downloadable at `GET /attestations/{id}/pdf`. This replaces the paper
    signature section on the current forms.
  - Project visibility is scoped server-side: users with only
    `projects.read_assigned` (e.g. field technicians) see only projects
    where they're the assigned technician; `projects.read_all` sees
    everything in the org.
  - **Auto-project-creation**: moving an Opportunity to "Aprobada" or
    "Instalación" creates its Project automatically (idempotent), with the
    default checklist applied and the opportunity owner pre-set as
    technician.
  - **Evidence scope**: photos only for now (JPEG/PNG/WEBP/HEIC), rejected
    with 400 otherwise; 15MB per file, 40 files per project ceiling.
  - 7 new tests (checklist template application, evidence-required gating,
    watermarked evidence download, two-signature attestation + PDF
    generation, assigned-only project scoping, evidence MIME rejection,
    auto-project-creation) — 30 passing total.
- **Frontend**: Projects list + create (applies the default checklist);
  Project detail page with an interactive checklist, evidence upload
  (captures the browser's GPS position automatically), and an in-app
  signature pad for both technician and customer, with a PDF download once
  both have signed.

### Phase 4: Invoice control

- **Backend**: Invoice, InvoicePayment, InvoiceAttachment models + migration
  (`0004_billing`). **Confirmed scope**: one Invoice per Project (matches
  "one Project per property/space" — each installation gets its own
  reimbursement record), manual entry only — no generated pro-forma PDF
  (spec 18 item 4).
  - Statuses: Pendiente → Enviada → Pagada, or Vencida (confirmed 4-state
    set). A partial payment auto-moves Pendiente → Enviada; a payment that
    covers the full balance moves the invoice to Pagada. "Vencida" is
    computed on read (any pending/sent invoice past its due date with an
    outstanding balance) rather than by a separate scheduled job — no Celery
    beat task wired up yet, tracked as a follow-up.
  - `POST /invoices/{id}/payments` records a payment (partial or full);
    `POST /invoices/{id}/mark-sent`; file attachments per invoice.
  - `GET /finance/dashboard`: total invoiced/paid/outstanding/overdue, and
    invoices due within 7 days — spec 17 phase 4's finance dashboard.
  - `GET /invoices-export.csv` for finance users (`invoices.export`).
  - 5 new tests (sequential numbering, partial→full payment status
    transitions, overdue detection on read, dashboard aggregation, CSV
    export) — 35 passing total.
- **Frontend**: Invoices page with the finance summary bar, a create form
  (pick a project + amount + due date), inline payment recording per
  invoice, "mark as sent," a CSV export button, and — added after Mateo's
  Phase 4 follow-up review — per-invoice attachment upload/view (payment
  and submission proof documents, e.g. a funder's payment confirmation).

### Phase 5: Hardening (security/permissions — in progress)

Confirmed priority with Mateo: security and permissions first, ahead of pagination
and further OWASP items.

- **Session/token security** (`app/core/token_denylist.py`, `app/core/redis_client.py`,
  `app/modules/auth/service.py`):
  - `POST /auth/logout` now actually revokes the presented refresh token
    (previously a no-op) — it's added to a denylist for its remaining lifetime.
  - Refresh-token rotation denylists the just-rotated-away token immediately, so a
    captured old refresh token can't be replayed even for the few minutes it would
    otherwise still be valid.
  - A `token_version` counter on `User` is embedded in every issued token (`"ver"`
    claim) and checked on every authenticated request; a password reset bumps it,
    instantly invalidating **every** outstanding session at once (spec 6.3.7) —
    not just the one refresh token being rotated. Migration `0005`.
  - Both the denylist and the rate limiter are Redis-backed with an automatic,
    transparent in-process fallback when Redis isn't reachable (`redis_client.py`
    caches the down-check for 15s so a missing Redis never adds per-request
    latency) — this closes the two-instance/multi-worker gaps in the earlier
    single-process rate limiter and the previously nonexistent revocation.
  - Fixed a real latent bug found while testing this: `PasswordResetToken.expires_at`
    and `Invitation.expires_at` comparisons could throw
    `TypeError: can't compare offset-naive and offset-aware datetimes` depending on
    how the DB driver round-trips `DateTime(timezone=True)` columns — normalized via
    a new `app/shared/datetime_utils.as_utc()` helper.
- **RBAC test coverage** (`backend/tests/test_rbac_full.py`, 11 new tests): every
  protected endpoint across CRM, Field Operations, and Billing is now exercised
  against roles that legitimately lack the required permission (expect 403) as well
  as roles that carry it (expect 2xx), including the zero-permission `read_only`
  role hitting every module, and an org-isolation sanity check on the newer
  field_ops/billing modules. Combined with the Phase 1 `test_rbac.py` suite (Users
  module) and the RBAC assertions embedded in `test_field_ops.py`
  (assigned-vs-all project scoping), every permission code in
  `app/shared/permissions.py` now has at least one enforcement test.
- **Invoice attachments UI** (frontend, confirmed "add it now" rather than defer):
  see Phase 4 note above — the backend endpoints existed since Phase 4, the UI was
  the gap.
- **OWASP Top 10 pass — done** (findings fixed, not just reviewed):
  - **Path traversal (CWE-22, A01)**: `app/modules/field_ops/storage.py` built
    the stored filename by string-concatenating the caller-supplied filename
    straight into a `Path`, so a crafted multipart filename like
    `../../etc/passwd` could have written outside the org's storage
    directory. Fixed with `_sanitize_filename()` (strips any directory
    component) plus a resolved-path containment check on both save and read.
  - **Unrestricted file upload (A04)**: `POST /invoices/{id}/attachments` had
    no MIME-type or size validation (unlike the evidence-upload endpoint,
    which always had one) — added the same allow-list/size-cap pattern
    (`billing/service.py: validate_attachment`, 15MB, photos/scans/PDF only,
    20 attachments/invoice ceiling).
  - **Security headers (A05)**: added `X-Content-Type-Options: nosniff`,
    `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
    `Permissions-Policy`, and HSTS outside `development` (`app/main.py`).
  - **Insecure default secret (A02/A07)**: the API now refuses to start
    outside `development` if `JWT_SECRET_KEY` is still the placeholder
    default, instead of silently signing every token with a public secret.
  - **CSV/Excel formula injection (CWE-1236)**: `GET /invoices-export.csv`
    now prefixes any cell starting with `=`, `+`, `-`, or `@` so Excel/Sheets
    won't evaluate it as a formula on open.
  - Reviewed and found already sound: password hashing (Argon2id via
    passlib), JWT decode always pins an explicit algorithm allow-list (no
    algorithm-confusion exposure), CORS restricted to `FRONTEND_APP_URL`
    (never a wildcard), org-scoped queries throughout (no IDOR path found),
    API docs disabled outside development.
- **Pagination (OWASP API4:2023, unrestricted resource consumption) — done**
  for the endpoints most likely to grow large: leads, customers,
  opportunities, activities, quotes, projects, project evidence, and
  invoices now accept `?limit=&offset=` (default 100, max 500) and return
  the total row count in an `X-Total-Count` response header rather than
  changing the JSON body shape, so existing frontend code keeps working
  unchanged (`app/shared/pagination.py`). Frontend pagination controls
  aren't built yet — tracked below.
- 20 new backend tests total this phase (3 auth/session + 11 RBAC + 6
  security-hardening) — **55 passing**.
- **Users and Audit Log frontend screens — done**: closes the gap that had
  existed since Phase 1 (the backend API existed, the nav links pointed
  nowhere). `frontend/src/features/users/UsersPage.tsx`: user list with
  plan-limit indicator (`active_user_count`/`max_active_users`), an invite
  form (email, name, role checkboxes sourced from `GET /roles`), and
  activate/deactivate actions. `frontend/src/features/audit/AuditLogPage.tsx`:
  paginated audit event list (actor, action, entity, timestamp), with a
  best-effort actor-name lookup against the users list (falls back to the
  raw id if that lookup isn't available to the viewer).
- **Task board — done**: added to the project detail page
  (`ProjectDetailPage.tsx`'s `TaskBoard`), a three-column board (Pendiente /
  En progreso / Completada) per project — create a task (title, optional
  assignee picked from the org's users, optional due date) and move it
  between columns with a status selector on each card. Reuses the Phase 3
  task endpoints (`GET/POST /projects/{id}/tasks`, `PATCH /tasks/{id}`),
  which already existed with no frontend consumer.
- **List-page pagination UI — done**: Leads, Customers, Projects, Invoices,
  and a project's Evidence list now have real pagination controls
  (Anterior/Siguiente + "X–Y de Z"), backed by the `?limit=&offset=` +
  `X-Total-Count` API added earlier in Phase 5. New shared pieces:
  `frontend/src/lib/pagination.ts` (`fetchPage` helper) and
  `frontend/src/components/PaginationControls.tsx`. The Opportunities
  pipeline board stays unpaginated on purpose — a kanban view doesn't have
  a "next page" — but now explicitly fetches up to the API's 500-row cap
  instead of the 100-row default, so a growing pipeline doesn't silently
  get truncated.
- **Task comments — done**: `TaskComment` (existed in the DB since Phase 3,
  no API) now has `GET/POST /tasks/{id}/comments`; each task card on the
  board has a "Comentarios" toggle to read and add them. Fixed a real
  scoping gap while wiring this up: `PATCH /tasks/{id}` only checked
  `Task.organization_id`, so a field technician's `tasks.manage`
  permission could reach a task on a project they weren't assigned to —
  both the PATCH and the new comment endpoints now go through the same
  assigned-vs-all project check every other field_ops route already uses
  (`_get_task_or_404`, `test_field_technician_cannot_touch_task_on_unassigned_project`).
- **Overdue-task visibility — done**: `Task.is_overdue` (computed, not
  stored — TaskStatus has no separate "overdue" state to persist into,
  same reasoning as Invoice's lazy overdue check) shows a red "vencida"
  badge on the task board, and `GET /tasks/overdue` (scoped the same way as
  every other task/project read — a technician sees only their assigned
  projects' overdue tasks) feeds a new "Tareas vencidas" widget on the
  dashboard home page. This is visibility, not a push/email alert — there's
  no notification channel to alert through yet (see the deferred item
  below).
- **Celery beat for overdue invoices — done**: `docker-compose.yml` gained
  a `beat` service (`celery -A app.workers.celery_app beat`) alongside the
  existing `worker`; `app/workers/tasks.py` defines
  `sweep_overdue_invoices_task`, scheduled daily at 06:00 UTC
  (`celery_app.py`'s `beat_schedule`), which calls the same
  `_refresh_overdue_status` transition the API already applied lazily on
  read (`billing/service.py: sweep_overdue_invoices`) — now an invoice
  surfaces as overdue even if nobody opens the Invoices page that day.
- **Deferred, explicitly, per Mateo (keep local for now)**: swapping local
  disk storage for S3 with signed URLs. Local storage is intentional during
  testing and does not block the signature workflow.
- 4 new backend tests this round (overdue-tasks endpoint + scoping, task
  comments, unassigned-project 404, invoice sweep) — **59 passing**.
- **Not yet done** (tracked in `docs/delivery-backlog.md`): a dependency
  vulnerability scan (`pip-audit`/`npm audit` wired into CI) and production
  email-provider configuration. The customer-facing signature link workflow
  is implemented; development still logs emails to the console.
- **Section 18 decisions resolved with Mateo (Sept 2026)**: support/SLA is
  **24/7 con SLA formal** (a real operational commitment — on-call,
  uptime monitoring and alerting still need to be built, not covered by the
  Celery sweep or dashboard widget); data retention is **indefinida**;
  ownership/licensing is **Mateo/Delta HVAC como dueño exclusivo**, no
  formal change-request process yet. Full detail in
  `docs/delivery-backlog.md`.

## Running locally

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

This runs Alembic migrations automatically on API start. To seed a demo login:

```bash
docker compose exec api python -m scripts.seed --demo-org
# admin@demo-org.com / ChangeMe123!
```

### Gmail para pruebas de correo

Para el entorno de pruebas puedes usar una cuenta Gmail dedicada. Activa la
verificación en dos pasos y crea una contraseña de aplicación; usa esa clave,
no la contraseña normal de Gmail. Configura `backend/.env` así:

```dotenv
EMAIL_PROVIDER=smtp
EMAIL_FROM=tu-cuenta@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu-cuenta@gmail.com
SMTP_PASSWORD=la-contraseña-de-aplicación
SMTP_USE_TLS=true
```

Mantén esta cuenta en bajo volumen durante las pruebas: Gmail puede limitar
temporalmente los envíos si se superan sus cuotas. Para producción conviene
usar un proveedor transaccional con dominio propio y trazabilidad de entrega.

Frontend: http://localhost:5173 · API docs: http://localhost:8000/api/docs

### Running the backend test suite

```bash
cd backend
pip install -r requirements.txt
pytest
```

## What's next (Phase 5: Hardening)

See `docs/delivery-backlog.md` for the phase-by-phase backlog against spec section 17.
The "Open Decisions" (spec section 18) are now resolved with Mateo — 24/7 SLA,
indefinite data retention, Mateo/Delta HVAC as exclusive owner — see that doc for
detail; the one remaining open item is #1 (exact per-funder checklist templates),
to be refined against the real intake PDFs.

## Known follow-ups before production go-live

- **Kept local for now, on purpose** (confirmed with Mateo): evidence,
  attestation PDFs, and invoice attachments stay on local disk
  (`backend/storage/`), not S3 — `app/modules/field_ops/storage.py` is the
  one place that would change (it already stores a storage-relative path,
  not an absolute one, so no model changes needed when this does happen).
  Email delivery is required for invitations, password recovery, overdue
  alerts, and customer signature requests; the current development adapter
  logs messages to the console until a provider is configured.
- Overdue invoices and overdue tasks are both now *detected* proactively
  (Celery beat sweep for invoices; a computed flag + dashboard widget for
  tasks). The required next step is a real email provider plus templates and
  delivery tracking for the assigned tech/PM.
- A dependency vulnerability scan (`pip-audit` for the backend, `npm audit` for
  the frontend) hasn't been wired into CI yet.
- AWS infrastructure-as-code (ECS Fargate, RDS, S3, CloudFront, secrets manager,
  backups, budget alerts) is not part of this repository yet — spec section 12.
- Section 18 decisions resolved (Sept 2026): 24/7 SLA (still needs an actual
  on-call/monitoring/alerting process — not built yet), indefinite data
  retention, Mateo/Delta HVAC as exclusive owner. Only #1 (exact per-funder
  checklist templates) remains open, deferred to when the real intake PDFs
  are in hand.
