# Delivery Backlog (spec section 17)

Status of the suggested implementation sequence from
`CRM_Field_Operations_MVP_Specification.md` section 17.

## Domain context (confirmed with Mateo, Sept 2026)

This is not a generic sales CRM — it's the back office for a door-to-door
(PAP) enrollment operation for utility/government-funded free-AC/HVAC
installation programs (funders: CARE, MEDICAL, CalFresh, HEEHRA, LADWP),
operating as "Delta HVAC" / "Programa de Aires Gratis." The real workflow:
canvasser captures a lead at a property → qualifies for a benefit program →
submits an application to the funder → inspection/installation → signed
attestation (technician + customer) → funder reimbursement. Today this is
tracked entirely in per-park spreadsheets with no reporting/dashboards —
replacing that manual tracking with real reports is a core goal, not just
digitizing forms. Two requirements confirmed directly by Mateo carry through
every phase from here: (a) documents with signature sections must support
virtual/digital signing via the app, attached into the generated document;
(b) uploaded evidence photos must carry a **visible watermark with GPS
georeferencing**, not just hidden EXIF metadata.

Confirmed scope decisions: UI is Spanish-only; invoicing is a manual record
only (no generated pro-forma PDFs in the MVP); GPS capture on evidence is
mandatory whenever the browser allows it; quotes use automatic sequential
numbering with no internal approval step; a customer self-service portal is
out of scope; funder status/approval codes are entered manually (no
IRIS/HEEHRA API integration in the MVP); one Opportunity/Project per
property/space, not per customer (a customer can have several); attestation
requires both the technician's and the customer's signature.

## 1. Foundation — done
Organization model, auth, users, roles, permissions, audit logs, base UI,
docker-compose infra. See README for what's implemented.

## 2. CRM — done
- Customer, CustomerContact, Lead, PipelineStage, FunderStatus, Opportunity,
  Activity, Quote, QuoteLineItem models + migration (`0002_crm`).
- Opportunity carries the funder-program fields confirmed with Mateo:
  `benefit_type`, `funder_program`, `application_number`, `approval_code`,
  an org-configurable `funder_status` catalog (mirrors what the funder
  reports back — Pendiente/En revisión/Aprobado/Instalado/Rechazado/En
  espera, separate from our own pipeline stage), plus
  `utility_account_number`, `meter_number`, `unit_type`, and
  `scheduled_install_date` captured from the real intake forms.
- Lead → customer/contact/opportunity conversion, with duplicate-detection
  warning (normalized email/phone/address) — spec 7.2.
- Pipeline stages (configurable per org, seeded with the real funder-program
  workflow), opportunity CRUD, stage transitions (loss reason required on a
  "lost" stage).
- Activities (call/email/meeting/note/task/follow-up).
- Quotes: line items with computed totals, automatic sequential numbering
  (`COT-0001`, ...) — kept for the smaller share of paid, non-program work.
- Customer 360 view endpoint aggregating opportunities, activities, quotes.
- CSV importer (`POST /leads/import`) for the existing per-park spreadsheets,
  with a caller-supplied column mapping (sheets vary by mobile-home park)
  and the same duplicate detection used for manual entry.
- Frontend: leads list + inline create + duplicate warning + convert action;
  customers list + 360 detail; opportunity pipeline board with inline stage
  and funder-status changes.
- 9 CRM/import tests, 23 passing total (backend).

## 3. Field operations — done (core), some follow-ups remain
- Project (one per property/space, created from an Opportunity or manually),
  ChecklistTemplate + ChecklistTemplateItem (org-configurable, seeded with a
  default HVAC free-install checklist), ProjectChecklistItem (a **snapshot**
  copy of the template — later template edits never mutate an in-progress
  project's checklist), Task + TaskComment, Evidence, Attestation models +
  migration (`0003_field_ops`).
- Project creation, update, technician scoping enforced server-side:
  `projects.read_assigned` users (field technicians) only see projects where
  they're the assigned technician; `projects.read_all` sees everything.
- Checklists: required-item/required-evidence gating — an item flagged
  `requires_evidence` cannot be marked complete until at least one Evidence
  row exists for it.
- Evidence: multipart upload, GPS captured whenever the browser allows it.
  **Confirmed requirement delivered**: every uploaded photo gets a **visible
  watermark burned into the image** (timestamp + GPS coordinates), not just
  hidden EXIF (`app/modules/field_ops/watermark.py`).
- Attestation: **two-party digital signature workflow**. The technician signs
  from the authenticated CRM; the customer receives a secure, single-use,
  time-limited email link and signs from a public customer page without CRM
  credentials. Once both signatures are present, a PDF is generated
  automatically embedding both signature images, project/customer details,
  timestamps, and checklist status. The system must record request, delivery,
  opened, signed, expired, and revoked states for auditability.
- Frontend: projects list + create (auto-applies the default checklist);
  project detail with interactive checklist, evidence upload (auto-captures
  browser GPS), technician signature pad, customer-signature request/status,
  and PDF download once fully signed. Customer signing is intentionally
  outside the authenticated CRM experience.
- **Auto-project-creation** (confirmed with Mateo, Sept 2026): moving an
  Opportunity's stage to "Aprobada" or "Instalación" automatically creates
  its Project (idempotent — won't duplicate if it moves between both), with
  the default checklist applied and the opportunity owner pre-set as the
  technician, ready to reassign.
- **Evidence scope confirmed**: photos only for now (no video yet), with a
  40-file/15MB-per-file ceiling (real usage is ~10-20 per project) and a
  MIME allow-list (JPEG/PNG/WEBP/HEIC) enforced server-side.
- **Checklist scope confirmed**: one generic HVAC install checklist is
  enough for now — per-funder-program checklists (spec 18 item 1, CARE vs
  HEEHRA vs LADWP) can be added later as additional `ChecklistTemplate` rows
  via the existing API without code changes.
- 7 new tests (checklist template snapshot, evidence-required gating,
  watermarked evidence download, two-signature attestation + PDF
  generation, assigned-only project scoping, evidence MIME rejection,
  auto-project-creation on stage change) — 30 passing total.

Follow-ups not yet done (tracked, not blocking the MVP flow; confirmed
deferred to after Phase 4):
- **Kept local for now, on purpose** (confirmed with Mateo, Sept 2026):
  evidence/attestation files stay on local disk (`backend/storage/`) rather
  than moving to S3 — `field_ops/storage.py` is the one file that would
  change when this does happen.
- No async thumbnailing or soft-delete UI yet.
- **Task board — done (Phase 5 follow-up)**: three-column board (Pendiente /
  En progreso / Completada) added to the project detail page, with create
  (title, assignee, due date) and drag-free status moves via a per-card
  selector. Reuses the Phase 3 task endpoints, which had no frontend
  consumer until now.
- **Task comments — done (Phase 5 follow-up)**: `GET/POST /tasks/{id}/comments`
  (the `TaskComment` model existed since Phase 3 with no API), plus a
  "Comentarios" toggle on each task-board card. Fixed a scoping gap found
  while building this: `PATCH /tasks/{id}` only checked organization, not
  project assignment — a technician's `tasks.manage` could reach a task
  outside their assigned projects. Both the PATCH and the new comment
  routes now share one `_get_task_or_404` helper that enforces the same
  assigned-vs-all scoping as every other field_ops route.
- **Overdue-task visibility — done (Phase 5 follow-up)**: `Task.is_overdue`
  (computed on read, not stored) drives a "vencida" badge on the board and
  a new `GET /tasks/overdue` endpoint (scoped the same as everything else)
  feeds a "Tareas vencidas" widget on the dashboard home page. This is
  in-app visibility, not a push/email alert — no notification channel is
  wired up yet (tracked as an open item, same as the invoice-overdue case
  below).
- No standalone "project report" PDF beyond the attestation itself.
- Per-funder-program checklist templates (item 1) — generic template is
  sufficient for now per Mateo.

## 4. Invoice control — done (core)
- Invoice, InvoicePayment, InvoiceAttachment models + migration
  (`0004_billing`). **Confirmed scope**: one Invoice per Project (not per
  Customer — matches "one Project per property/space"), manual entry only,
  no generated pro-forma PDF (spec 18 item 4, reconfirmed).
- Outstanding balance calculation (amount − sum of payments); a partial
  payment moves Pendiente → Enviada, a payment that clears the balance moves
  it to Pagada. **Confirmed 4-state status set**: Pendiente / Enviada /
  Pagada / Vencida. Vencida is applied both lazily on read (unchanged) and,
  as of the Phase 5 follow-up below, proactively by a Celery beat sweep.
- Finance dashboard (`GET /finance/dashboard`): total invoiced/paid/
  outstanding/overdue, invoice count, overdue count, due-within-7-days count.
- CSV export for finance users (`GET /invoices-export.csv`, `invoices.export`
  permission). XLSX export not built — CSV covers the same use case for now.
- Frontend: Invoices page with the finance summary bar, create form (project
  + amount + due date), inline payment recording, mark-as-sent, CSV export,
  and (added in the Phase 4 follow-up review, confirmed "agrégala ahora")
  per-invoice attachment upload/view for payment/submission proof documents.
- 5 new tests (sequential numbering, partial→full payment transitions,
  overdue detection on read, dashboard aggregation, CSV export) — 35
  passing total.

**Celery beat sweep — done (Phase 5 follow-up)**: `docker-compose.yml` has a
new `beat` service (`celery -A app.workers.celery_app beat`) alongside
`worker`; `app/workers/tasks.py: sweep_overdue_invoices_task` runs daily at
06:00 UTC and calls `billing/service.py: sweep_overdue_invoices` — the same
status transition the API already applied lazily, now also applied
proactively across every organization so an invoice shows as overdue even
if nobody opens the Invoices page. No notification is sent when this
happens yet (see Known follow-ups) — it just keeps the stored status
correct. XLSX export is still a possible follow-up if CSV turns out not to
be enough for finance's workflow.

## 5. Hardening — in progress (security/permissions done; confirmed top priority)
- **Session/token security — done**: `POST /auth/logout` now revokes the
  presented refresh token (Redis-backed denylist, `app/core/token_denylist.py`,
  in-memory fallback); refresh rotation denylists the just-rotated-away token to
  prevent replay; a new `User.token_version` column (migration `0005`) is embedded
  in every issued token and checked on every request, and is bumped on password
  reset to invalidate every outstanding session at once (spec 6.3.7) — closes the
  "revoke all sessions" gap. The in-memory rate limiter (`app/core/rate_limit.py`)
  is now Redis-backed with the same transparent fallback, closing the
  multi-instance gap called out in the Phase 4 README follow-ups.
  Found and fixed a real latent bug along the way: naive/aware datetime comparison
  on `PasswordResetToken.expires_at` / `Invitation.expires_at` could raise
  `TypeError` depending on DB driver round-tripping — normalized via
  `app/shared/datetime_utils.as_utc()`.
- **Full permissions test suite across every endpoint — done**:
  `backend/tests/test_rbac_full.py` (11 new tests) extends the Phase 1
  `test_rbac.py` pattern to CRM, Field Operations, and Billing — every
  protected route is checked against a role that lacks the required
  permission (403) and, for cross-module reads, a role that has it (2xx),
  plus the zero-permission `read_only` role against every module and an
  org-isolation check on the newer modules. 49 backend tests passing total.
- **OWASP Top 10 review — done, findings fixed**: path traversal in
  `field_ops/storage.py` (filename wasn't sanitized before being joined into
  a filesystem path — fixed with `_sanitize_filename` + resolved-path
  containment check); unrestricted file upload on
  `POST /invoices/{id}/attachments` (no MIME/size limit — added the same
  allow-list/size-cap the evidence endpoint already had); missing security
  headers (nosniff, frame-deny, referrer-policy, permissions-policy, HSTS
  outside dev — `app/main.py`); startup now refuses to run outside
  `development` on the placeholder `JWT_SECRET_KEY`; CSV export now guards
  against Excel/Sheets formula injection. Reviewed and already sound:
  password hashing, JWT algorithm pinning, CORS scope, org-scoped queries
  (no IDOR found), docs disabled outside dev. CSRF: N/A, bearer-token auth
  only, no cookie sessions.
- **Pagination — done, backend and frontend** (leads, customers,
  opportunities, projects, project evidence, invoices): `?limit=&offset=`
  (default 100, max 500) with the total count in an `X-Total-Count` header;
  the corresponding list pages now have real Anterior/Siguiente controls
  (`frontend/src/lib/pagination.ts` + `components/PaginationControls.tsx`).
  The Opportunities pipeline board deliberately stays unpaginated (a kanban
  view has no "next page") but now fetches up to the 500-row cap instead of
  the 100-row default.
- **Users and Audit Log frontend screens — done**: filled the gap that had
  existed since Phase 1 (backend API existed, nav links pointed nowhere).
  Users page: list with plan-limit indicator, invite form (roles sourced
  from `GET /roles`), activate/deactivate. Audit Log page: paginated event
  list with actor-name lookup.
- Full performance pass against the p95 < 800ms target — not started (no
  load testing done yet).
- Dependency vulnerability scan (`pip-audit`/`npm audit`) wired into CI —
  not started.
- Backups, health checks, structured logs + alerting, budget alerts configured
  in AWS before go-live — not started.
- User acceptance testing, production release — not started.
- Email/push delivery for overdue-invoice and overdue-task detection remains
  pending. The dashboard widget, task-board badge, and finance dashboard are
  the current in-app fallback. Customer signature requests now have a secure
  public flow and development email logging; production requires a verified
  provider, templates, recipient rules, retries, delivery status, and user
  preferences.

## AWS infrastructure (spec section 12) — not started
CloudFront + static hosting, ALB, ECS Fargate (API + worker), RDS PostgreSQL,
S3 private bucket, Redis, secrets manager, least-privilege IAM, per-environment
separation, TLS/encryption at rest, daily backups.

## Open decisions (spec section 18) — status

Resolved with Mateo (Sept 2026): #2 GPS is mandatory and must be a visible
watermark, not just metadata (item 2); #4 invoicing is manual-record-only
(item 4); #5 quotes use automatic sequential numbering with no approval step
(item 5); #6 UI is Spanish-only (item 6); #7 migration data confirmed via 11
uploaded spreadsheets, caller-mapped CSV import built (item 7); #9 no
self-service portal in the MVP (item 9). Plus two decisions specific to the
funder-program model: funder/status integration stays manual for now (no
IRIS/HEEHRA API in the MVP), and Project granularity is one per
property/space, not per customer.

Resolved with Mateo (Sept 2026), item 8 — support hours, retention,
compliance:
- **Support/SLA: 24/7 con SLA formal.** This is a real operational
  commitment, not something the app currently provides — today there is no
  on-call rotation, uptime monitoring, alerting, or incident-response
  process. Treat this as a new Phase 5/6 deliverable (monitoring + alerting
  + an on-call process for Delta HVAC), not a box already checked by the
  Celery-beat sweep or the in-app "tareas vencidas" widget.
- **Data retention: indefinida** (leads, evidencia, facturas se conservan
  sin fecha de expiración una vez cerrado un caso). Revisit if a funder
  program or regulation later requires a fixed retention/purge window.

Resolved with Mateo (Sept 2026), item 10 — ownership/licensing:
- **Mateo / Delta HVAC es dueño exclusivo** del código y los datos. Sin
  proceso formal de change-request definido todavía; por ahora los cambios
  se coordinan directamente en esta misma sesión/proyecto.

Still open — needed before Phase 5 (Hardening) / go-live, not blocking
Phase 3:
1. Exact project types and required checklist templates per funder program
   (CARE vs. HEEHRA vs. LADWP forms likely differ) — will refine against the
   real intake PDFs when building Phase 3.
