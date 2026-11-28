"""Carga: de la caché en disco a la base del CRM. Una transacción por proyecto.

Idempotente: relanzar no duplica nada ni pisa lo que alguien editó después
(un expediente ya importado solo recibe notas y elementos de descarga que le
falten). `dry_run` hace todo igual y al final deshace; imprime lo que haría.

No toca etapas directamente: el expediente nace por `cases.service.import_case`.
Los binarios no se descargan aquí; quedan en `import_items` como `pending`."""
import csv
import secrets
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.cases import service as case_service
from app.modules.cases.models import Case, CaseNote
from app.modules.crm.models import Customer, CustomerContact
from app.modules.imports.companycam import mapping as m
from app.modules.imports.companycam.cache import ExportCache
from app.modules.imports.models import ImportItem
from app.modules.organizations.models import Organization
from app.modules.users.models import Role, User, UserRole, UserStatus
from app.shared.audit import record_audit_event
from app.shared.normalize import normalize_email, normalize_phone

SOURCE = m.SOURCE


class ImportAborted(Exception):
    pass


class Loader:
    def __init__(self, db: AsyncSession, organization_id: uuid.UUID, cache: ExportCache, *,
                 dry_run: bool = False, log=print) -> None:
        self.db = db
        self.org = organization_id
        self.cache = cache
        self.dry_run = dry_run
        self.log = log
        self.stats: Counter = Counter()
        self.ambiguous: list[dict] = []
        self.created_users: list[dict] = []
        # Lo que va acumulando el proyecto en curso; se fusiona con lo de arriba
        # solo si el proyecto se confirma (si falla, no cuenta nada).
        self._cstats: Counter = Counter()
        self._cambiguous: list[dict] = []
        self._cusers: list[dict] = []
        self.errors: list[dict] = []
        self.index = m.MatchIndex()
        self.users_by_email: dict[str, User] = {}
        self.users_by_name: dict[str, list[User]] = {}
        self.users_by_ref: dict[str, User] = {}
        self.cc_users: dict[str, dict] = {}
        self.tag_photos: dict[str, list[str]] = {}
        self._salesperson_role: Role | None = None

    # ------------------------------------------------------------------ run
    async def run(self, *, only: set[str] | None = None, limit: int | None = None) -> dict:
        org = await self.db.get(Organization, self.org)
        if org is None:
            raise ImportAborted(f"La organización {self.org} no existe.")
        todos = self.cache.projects()
        if not todos:
            raise ImportAborted("La caché no tiene proyectos: corre `extract` primero.")
        self.index.ignored = m.shared_values(todos)
        self.cc_users = {str(u["id"]): u for u in self.cache.users()}
        self.tag_photos = self.cache.tag_photos()
        await self._load_indexes()

        for p in self.cache.iter_projects(only=only, limit=limit):
            await self._load_project_safely(p)

        if self.dry_run:
            await self.db.rollback()
        self._write_reports()
        return dict(self.stats)

    async def _load_project_safely(self, p: dict) -> None:
        pid = str(p.get("id"))
        savepoint = None
        self._cstats, self._cambiguous, self._cusers = Counter(), [], []
        try:
            if self.dry_run and self.db.get_bind().dialect.name == "postgresql":
                savepoint = await self.db.begin_nested()
            pendiente = await self._load_project(p)
            if savepoint is not None:
                await savepoint.commit()
            elif not self.dry_run:
                await self.db.commit()
            for fn in pendiente:  # el índice solo aprende de lo que sí quedó
                fn()
            self.stats.update(self._cstats)
            self.ambiguous.extend(self._cambiguous)
            self.created_users.extend(self._cusers)
        except Exception as exc:  # un proyecto malo no frena a los demás
            if savepoint is not None:
                await savepoint.rollback()
            else:
                await self.db.rollback()
            await self._load_users()  # lo creado en el proyecto fallido ya no existe
            self.stats["errors"] += 1
            self.errors.append({"project_id": pid, "error": f"{type(exc).__name__}: {exc}"[:500]})
            self.log(f"proyecto {pid}: error {type(exc).__name__}")

    # -------------------------------------------------------------- índices
    async def _load_users(self) -> None:
        self.users_by_email, self.users_by_name, self.users_by_ref = {}, {}, {}
        for u in (await self.db.execute(select(User).where(User.organization_id == self.org))).scalars().all():
            self.users_by_email[u.email] = u
            self.users_by_name.setdefault(m.fold(u.full_name), []).append(u)
            if u.source == SOURCE and u.external_ref:
                self.users_by_ref[u.external_ref] = u

    async def _load_indexes(self) -> None:
        await self._load_users()
        clientes = (await self.db.execute(select(Customer).where(Customer.organization_id == self.org))).scalars().all()
        for c in clientes:
            self.index.add(c.id, ref=c.external_ref if c.source == SOURCE else None, emails=[c.email],
                           phones=[c.main_phone])
            for k in c.contacts:
                self.index.add(c.id, emails=[k.email], phones=[k.phone])
        # Dirección de otros expedientes del cliente, solo con unidad.
        filas = (await self.db.execute(select(Case.customer_id, Case.normalized_address).where(
            Case.organization_id == self.org, Case.customer_id.is_not(None), Case.address_unit.is_not(None),
            Case.address_unit != "", Case.normalized_address.is_not(None)))).all()
        for cid, dire in filas:
            self.index.add(cid, address=dire)

    # ------------------------------------------------------------- proyecto
    async def _load_project(self, p: dict) -> list:
        pid = str(p["id"])
        data = self.cache.project_data(pid)
        pendiente: list = []

        existente = (await self.db.execute(select(Case).where(
            Case.organization_id == self.org, Case.source == SOURCE, Case.external_ref == pid))).scalar_one_or_none()
        if existente is not None:
            case = existente
            self._cstats["cases_existing"] += 1
        else:
            case, pendiente = await self._create_case(p)
        await self._notes(case, p, data)
        await self._items(case, p, data)
        await self.db.flush()
        return pendiente

    async def _create_case(self, p: dict):
        addr = m.map_address(p)
        stage, reason = m.map_stage(p)
        salesperson = await self._creator_user(p)
        customer, pendiente = await self._customer(p, addr)
        case, creado = await case_service.import_case(
            self.db, organization_id=self.org, source=SOURCE, external_ref=str(p["id"]), stage_code=stage,
            reason=reason, created_at=m.to_dt(p.get("created_at")), customer_id=customer.id,
            assigned_salesperson_id=salesperson.id if salesperson else None, **addr,
        )
        if creado:
            self._cstats["cases_created"] += 1
            self._cstats[f"stage_{stage}"] += 1
        return case, pendiente

    # ---------------------------------------------------------- vendedor
    async def _salesperson(self) -> Role:
        if self._salesperson_role is None:
            roles = (await self.db.execute(select(Role).where(
                Role.code == "salesperson", (Role.organization_id == self.org) | Role.organization_id.is_(None)))
            ).scalars().all()
            if not roles:
                raise ImportAborted("La organización no tiene el rol «salesperson».")
            self._salesperson_role = next((r for r in roles if r.organization_id == self.org), roles[0])
        return self._salesperson_role

    async def _creator_user(self, p: dict) -> User | None:
        """El usuario del CRM que corresponde al creador del proyecto en
        CompanyCam: por correo, por nombre exacto o uno nuevo INACTIVO (sin
        acceso, sin invitación, sin gastar el límite de usuarios activos)."""
        if p.get("creator_type") not in (None, "User") or not p.get("creator_id"):
            return None
        cid = str(p["creator_id"])
        if cid in self.users_by_ref:
            return self.users_by_ref[cid]
        cc = self.cc_users.get(cid, {})
        nombre = (f"{cc.get('first_name') or ''} {cc.get('last_name') or ''}".strip()
                  or (p.get("creator_name") or "").strip())
        email = normalize_email(m.clean(cc.get("email_address")))
        user = self.users_by_email.get(email) if email else None
        if user is None and nombre:
            candidatos = self.users_by_name.get(m.fold(nombre), [])
            if len(candidatos) == 1:
                user = candidatos[0]
        if user is not None:
            self.users_by_ref.setdefault(cid, user)
            self._cstats["creators_matched"] += 1
            return user

        rol = await self._salesperson()
        real = email or f"cc-{cid}@import.invalid"
        conflicto = False
        if email:
            # El acceso busca el correo en TODAS las organizaciones y espera una
            # sola coincidencia: si ya existe en cualquiera, se usa el sintético.
            if (await self.db.execute(select(User.id).where(User.email == email).limit(1))).first():
                real, conflicto = f"cc-{cid}@import.invalid", True
        user = User(
            organization_id=self.org, email=real, email_display=real, full_name=nombre or f"CompanyCam {cid}",
            # Contraseña aleatoria que nadie conoce y estado inactivo: no entra ni recupera acceso.
            password_hash=hash_password(secrets.token_urlsafe(48)), status=UserStatus.inactive,
            source=SOURCE, external_ref=cid,
        )
        self.db.add(user)
        await self.db.flush()
        self.db.add(UserRole(user_id=user.id, role_id=rol.id))
        await record_audit_event(
            self.db, organization_id=self.org, actor_user_id=None, action="users.imported", entity_type="User",
            entity_id=str(user.id), after_data={"source": SOURCE, "external_ref": cid, "email": real,
                                                "status": "inactive", "role": "salesperson"})
        self.users_by_ref[cid] = user
        self.users_by_email[real] = user
        self.users_by_name.setdefault(m.fold(user.full_name), []).append(user)
        self._cstats["creators_created"] += 1
        self._cusers.append({"external_ref": cid, "name": user.full_name, "email": real,
                                   "synthetic_email": real.endswith("@import.invalid"),
                                   "email_conflict": conflicto, "companycam_email": email or ""})
        return user

    # ----------------------------------------------------------- cliente
    async def _customer(self, p: dict, addr: dict):
        cand = m.candidate_from_project(p)
        veredicto, ids = m.match_customer(cand, self.index)
        if veredicto == "match":
            self._cstats["customers_reused"] += 1
            return await self.db.get(Customer, ids[0]), []
        if veredicto == "ambiguous":
            self._cstats["customers_ambiguous"] += 1
            self._cambiguous.append({"project_id": p["id"], "name": cand.name, "email": cand.email or "",
                                   "phone": cand.phone or "", "candidates": " ".join(str(i) for i in ids)})
        contacto = p.get("primary_contact") or {}
        # En CompanyCam el mismo contacto puede venir con la clave repetida si
        # ya hay un cliente nuevo por ambigüedad: se usa el id del proyecto.
        ref = cand.ref
        ya = (await self.db.execute(select(Customer.id).where(
            Customer.organization_id == self.org, Customer.source == SOURCE, Customer.external_ref == ref))).first()
        if ya is not None:
            ref = f"project:{p['id']}"
        correo = m.clean(contacto.get("email"), 255)
        tel = m.clean(contacto.get("phone_number"), 32)
        cliente = Customer(organization_id=self.org, legal_name=cand.name, main_phone=tel, email=correo,
                           billing_address=m.address_line(addr)[:500] or None, source=SOURCE, external_ref=ref)
        self.db.add(cliente)
        await self.db.flush()
        if contacto.get("name"):
            self.db.add(CustomerContact(customer_id=cliente.id, full_name=contacto["name"][:255], email=correo,
                                        phone=tel, is_primary=True))
        self._cstats["customers_created"] += 1
        index, cid = self.index, cliente.id
        return cliente, [lambda: index.add(cid, ref=ref, emails=[correo], phones=[tel], address=cand.address)]

    # ------------------------------------------------------------- notas
    async def _notes(self, case: Case, p: dict, data: dict) -> None:
        ya = {(k, r) for k, r in (await self.db.execute(select(CaseNote.kind, CaseNote.external_ref).where(
            CaseNote.case_id == case.id))).all()}

        def agregar(kind: str, ref: str, body: str, author: str | None, when, payload=None) -> None:
            if (kind, ref) in ya:
                return
            self.db.add(CaseNote(organization_id=self.org, case_id=case.id, kind=kind, body=body,
                                 author_name=author, source=SOURCE, external_ref=ref, payload=payload,
                                 occurred_at=when))
            ya.add((kind, ref))
            self._cstats[f"notes_{kind}"] += 1

        agregar("notepad", "notepad", m.notepad_body(p), p.get("creator_name"), m.to_dt(p.get("created_at")))
        for c in data["comments"]:
            texto = m.comment_body(c)
            if texto:
                agregar("comment", str(c["id"]), texto, c.get("creator_name"), m.to_dt(c.get("created_at")), c)
        for c in data["checklists"]:
            agregar("checklist", str(c.get("id") or c.get("name")), m.checklist_body(c), c.get("creator_name"),
                    m.to_dt(c.get("created_at")), c)

    # ---------------------------------------------------------- descargas
    async def _items(self, case: Case, p: dict, data: dict) -> None:
        ya = {(k, e) for k, e in (await self.db.execute(select(ImportItem.kind, ImportItem.external_id).where(
            ImportItem.organization_id == self.org, ImportItem.source == SOURCE, ImportItem.case_id == case.id))).all()}
        ahora = datetime.now(timezone.utc)

        def agregar(kind: str, ext: str, url: str | None, payload: dict, status: str = "pending") -> None:
            if (kind, ext) in ya:
                return
            self.db.add(ImportItem(organization_id=self.org, source=SOURCE, kind=kind, external_id=ext,
                                   case_id=case.id, remote_url=url, payload=payload, status=status,
                                   downloaded_at=ahora if status == "downloaded" else None))
            ya.add((kind, ext))
            self._cstats[f"items_{kind}"] += 1

        # El «proyecto» no tiene binario: queda registrado como ya resuelto.
        agregar("project", str(p["id"]), p.get("project_url"),
                {"status": p.get("status"), "archived": p.get("archived"), "photo_count": p.get("photo_count")},
                status="downloaded")
        for f in data["photos"]:
            coords = f.get("coordinates") or {}
            lat, lon = coords.get("lat"), coords.get("lon")
            if not lat and not lon:
                lat = lon = None
            agregar("photo", str(f["id"]), m.photo_url(f), {
                "captured_at": f.get("captured_at") or f.get("created_at"), "latitude": lat, "longitude": lon,
                "author_name": f.get("creator_name"), "tags": self.tag_photos.get(str(f["id"]), []),
                "description": f.get("description"), "web_url": m.photo_web_url(f)})
        for d in data["documents"]:
            agregar("document", str(d["id"]), d.get("url"), {
                "name": d.get("name"), "content_type": d.get("content_type"), "byte_size": d.get("byte_size"),
                "author_name": d.get("creator_name"), "created_at": d.get("created_at"),
                "project_id": str(p["id"])})

    # ----------------------------------------------------------- informes
    def _write_reports(self) -> None:
        d = self.cache.reports_dir
        sufijo = "dry-run" if self.dry_run else "load"
        for nombre, filas in (("ambiguos", self.ambiguous), ("usuarios_creados", self.created_users),
                              ("errores", self.errors)):
            if not filas:
                continue
            with (d / f"{nombre}-{sufijo}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
                w.writeheader()
                w.writerows(filas)
