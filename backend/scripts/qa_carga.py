"""Prueba de carga de los listados: muchos registros y ningún listado pesado.

1. Carga en la organización demo miles de registros marcados «CARGA»:
   clientes, expedientes en todas las etapas (con su historial), proyectos con
   tareas vencidas, contactos de campaña, avisos con sus envíos y auditoría.
2. Llama a cada listado GET de la API (como Administrador y como Vendedor) y
   mide el tiempo, cuántas filas devuelve y el total (X-Total-Count).
3. Marca como falla todo listado que tarde más de `LENTO_S` o devuelva más
   filas que `MAX_LIMIT`, y escribe el informe en Markdown.

Uso, dentro del contenedor de la API (con `docker compose up` y los datos demo):
    python -m scripts.qa_carga                 # carga 5.000 y mide
    python -m scripts.qa_carga --cantidad 20000
    python -m scripts.qa_carga --solo-medir    # mide sin cargar más
    python -m scripts.qa_carga --limpiar       # borra todo lo marcado «CARGA»
El informe sale por la salida estándar (redirígelo a docs/qa/…).
"""
import argparse
import asyncio
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select, text

from app.db import all_models  # noqa: F401  (registra todos los modelos)
from app.db.session import AsyncSessionLocal
from app.main import app
from app.modules.cases import stages
from app.modules.cases.models import Case, CaseStageEvent
from app.modules.crm.models import Customer
from app.modules.field_ops.models import Project, Task
from app.modules.notifications.models import MarketingContact, Notification, NotificationDelivery
from app.modules.organizations.models import Organization
from app.modules.users.models import User
from app.shared.audit_models import AuditEvent
from app.shared.pagination import MAX_LIMIT

API = "http://localhost:8000/api/v1"
CLAVE = "ChangeMe123!"
MARCA = "CARGA"
LENTO_S = 1.0
LOTE = 1000


def _lotes(filas, n=LOTE):
    for i in range(0, len(filas), n):
        yield filas[i:i + n]


async def cargar(cantidad: int) -> dict:
    ahora = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(Organization).where(Organization.name == "Demo Organization"))).scalar_one()
        admin = (await db.execute(select(User).where(User.email == "admin@demo-org.com"))).scalar_one()
        vendedor = (await db.execute(select(User).where(User.email == "vendedor@demo-org.com"))).scalar_one()
        ya = (await db.execute(select(Case.id).where(Case.case_number.like(f"{MARCA}-%")))).all()
        base = len(ya)

        clientes = [Customer(organization_id=org.id, legal_name=f"{MARCA} Cliente {base + i}",
                             main_phone=f"555{base + i:07d}") for i in range(cantidad)]
        for lote in _lotes(clientes):
            db.add_all(lote)
            await db.flush()

        etapas = [s for s in stages.STAGES]
        casos = []
        for i, cliente in enumerate(clientes):
            n = base + i
            casos.append(Case(organization_id=org.id, case_number=f"{MARCA}-{n:07d}", source="visit",
                              stage_code=etapas[i % len(etapas)], customer_id=cliente.id,
                              assigned_salesperson_id=vendedor.id if i % 2 == 0 else admin.id,
                              address_street=f"{n} {MARCA} Park Dr", address_unit=f"Spc {n}",
                              address_city="Phoenix", address_state="AZ", address_zip="85001",
                              normalized_address=f"{n} {MARCA.lower()} park dr spc {n} phoenix 85001"))
        for lote in _lotes(casos):
            db.add_all(lote)
            await db.flush()
        for lote in _lotes(casos):
            db.add_all([CaseStageEvent(organization_id=org.id, case_id=c.id, to_stage_code=c.stage_code,
                                       actor_user_id=vendedor.id, occurred_at=ahora - timedelta(minutes=i))
                        for i, c in enumerate(lote)])
            await db.flush()

        proyectos = [Project(organization_id=org.id, customer_id=clientes[i].id, title=f"{MARCA} Proyecto {base + i}")
                     for i in range(min(cantidad // 5, len(clientes)))]
        for lote in _lotes(proyectos):
            db.add_all(lote)
            await db.flush()
        for lote in _lotes(proyectos, 300):
            db.add_all([Task(organization_id=org.id, project_id=p.id, title=f"{MARCA} Tarea {k}",
                             due_date=ahora - timedelta(days=k + 1)) for p in lote for k in range(3)])
            await db.flush()

        for lote in _lotes(list(range(cantidad))):
            db.add_all([MarketingContact(organization_id=org.id, name=f"{MARCA} Contacto {base + i}",
                                         phone=f"602{base + i:07d}") for i in lote])
            await db.flush()

        for lote in _lotes(list(range(cantidad))):
            avisos = [Notification(organization_id=org.id, user_id=admin.id, event="case.approved",
                                   title=f"{MARCA} Aviso {base + i}", body="Prueba de carga",
                                   created_at=ahora - timedelta(seconds=i)) for i in lote]
            db.add_all(avisos)
            await db.flush()
            db.add_all([NotificationDelivery(organization_id=org.id, notification_id=a.id, channel="email",
                                             to="carga@example.com", body="Prueba de carga", status="sent",
                                             attempts=1, created_at=a.created_at) for a in avisos])
            await db.flush()

        for lote in _lotes(list(range(cantidad))):
            db.add_all([AuditEvent(organization_id=org.id, actor_user_id=admin.id, action=f"{MARCA.lower()}.prueba",
                                   entity_type="Carga", entity_id=str(uuid.uuid4())) for _ in lote])
            await db.flush()
        await db.commit()
        return {"clientes": len(clientes), "expedientes": len(casos), "proyectos": len(proyectos),
                "tareas_vencidas": len(proyectos) * 3, "contactos": cantidad, "avisos_y_envios": cantidad,
                "auditoria": cantidad}


async def limpiar() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Case).where(Case.case_number.like(f"{MARCA}-%")))
        await db.execute(delete(Project).where(Project.title.like(f"{MARCA} %")))
        await db.execute(delete(Customer).where(Customer.legal_name.like(f"{MARCA} %")))
        await db.execute(delete(MarketingContact).where(MarketingContact.name.like(f"{MARCA} %")))
        await db.execute(delete(Notification).where(Notification.title.like(f"{MARCA} %")))
        await db.execute(delete(AuditEvent).where(AuditEvent.action == f"{MARCA.lower()}.prueba"))
        await db.commit()
    print("Listo: se borró todo lo marcado «CARGA».")


def _sesion(c: httpx.Client, correo: str) -> dict:
    c.post("/auth/login", json={"email": correo, "password": CLAVE})  # calienta
    r = c.post("/auth/login", json={"email": correo, "password": CLAVE})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _ids() -> dict[str, str]:
    """Un identificador real por parámetro de ruta, de la organización demo."""
    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(Organization.id).where(Organization.name == "Demo Organization"))).scalar_one()
        consultas = {
            "case_id": "select id from cases where organization_id=:o order by created_at desc limit 1",
            "project_id": "select id from projects where organization_id=:o order by created_at desc limit 1",
            "program_id": "select id from programs where organization_id=:o limit 1",
            "campaign_id": "select id from campaigns where organization_id=:o limit 1",
            "task_id": "select id from field_tasks where organization_id=:o limit 1",
        }
        ids = {}
        for param, sql in consultas.items():
            fila = (await db.execute(text(sql), {"o": org})).first()
            if fila:
                ids[param] = str(fila[0])
        return ids


def medir(ids: dict[str, str]) -> list[dict]:
    from fastapi.routing import APIRoute
    import inspect
    import typing

    extra = {"/dispatch/agenda": {"date_from": (date.today() - timedelta(days=30)).isoformat(),
                                  "date_to": (date.today() + timedelta(days=30)).isoformat()},
             "/geo/cities": {"state": "CA"}}
    resultados = []
    with httpx.Client(base_url=API, timeout=120) as c:
        sesiones = {"Administrador": _sesion(c, "admin@demo-org.com"), "Vendedor": _sesion(c, "vendedor@demo-org.com")}
        for r in app.routes:
            if not isinstance(r, APIRoute) or "GET" not in r.methods:
                continue
            devuelve = inspect.signature(r.endpoint).return_annotation
            if typing.get_origin(r.response_model) is not list and typing.get_origin(devuelve) is not list:
                continue
            ruta = r.path.removeprefix("/api/v1")
            params = re.findall(r"\{(\w+)\}", ruta)
            if any(p not in ids for p in params):
                continue
            for p in params:
                ruta = ruta.replace("{" + p + "}", ids[p])
            for quien, h in sesiones.items():
                t0 = time.perf_counter()
                resp = c.get(ruta, headers=h, params=extra.get(r.path.removeprefix("/api/v1"), {}))
                dt = time.perf_counter() - t0
                if resp.status_code in (403, 404):
                    continue
                filas = len(resp.json()) if resp.status_code == 200 and isinstance(resp.json(), list) else None
                resultados.append({"ruta": r.path.removeprefix("/api/v1"), "quien": quien, "estado": resp.status_code,
                                   "segundos": dt, "filas": filas, "total": resp.headers.get("x-total-count"),
                                   "ok": resp.status_code == 200 and dt <= LENTO_S
                                   and (filas is None or filas <= MAX_LIMIT)})
    return resultados


def informe(cargado: dict | None, resultados: list[dict]) -> str:
    malos = [x for x in resultados if not x["ok"]]
    lineas = [f"# Prueba de carga de listados · {datetime.now():%Y-%m-%d %H:%M}", ""]
    if cargado:
        lineas += ["Se cargaron en la organización demo, marcados «CARGA»: " +
                   ", ".join(f"{v:,} {k.replace('_', ' ')}".replace(",", ".") for k, v in cargado.items()) + ".", ""]
    lineas += [f"**{len(resultados) - len(malos)} de {len(resultados)} mediciones OK** "
               f"(umbral: {LENTO_S:.0f} s y como máximo {MAX_LIMIT} filas por respuesta).", "",
               "| Listado | Quién | Estado | Tiempo | Filas | Total |", "|---|---|---|---|---|---|"]
    for x in sorted(resultados, key=lambda x: -x["segundos"]):
        marca = "" if x["ok"] else " ⚠"
        lineas.append(f"| `{x['ruta']}`{marca} | {x['quien']} | {x['estado']} | {x['segundos'] * 1000:.0f} ms | "
                      f"{x['filas'] if x['filas'] is not None else '—'} | {x['total'] or '—'} |")
    return "\n".join(lineas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cantidad", type=int, default=5000)
    parser.add_argument("--solo-medir", action="store_true")
    parser.add_argument("--limpiar", action="store_true")
    args = parser.parse_args()
    if args.limpiar:
        asyncio.run(limpiar())
        return

    # Un solo ciclo de eventos para todo lo que toca la base: el pool de
    # conexiones queda atado al ciclo en el que se abrió.
    async def preparar():
        cargado = None if args.solo_medir else await cargar(args.cantidad)
        return cargado, await _ids()

    cargado, ids = asyncio.run(preparar())
    print(informe(cargado, medir(ids)))


if __name__ == "__main__":
    main()
