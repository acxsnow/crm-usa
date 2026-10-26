"""Base común de los lotes de QA por API (desde el lote 3). Reusa `scripts/qa_e2e.py`.

Corre dentro del contenedor api con PYTHONPATH=/app:/tmp. Igual que el lote 2:
cada comprobación cae en el escenario activo (`esc`) y al final `guardar` deja
un JSON {escenario: [{check, ok, dato}]} que lee `registrar.py`.
"""
import asyncio
import json
from datetime import timedelta

import httpx
import redis
from sqlalchemy import text

from app.core.config import get_settings
from scripts import qa_e2e as e

R = redis.Redis.from_url(get_settings().REDIS_URL)
OUT: dict[str, list] = {}
API = e.API


def limpiar():
    for k in R.scan_iter("ratelimit:*"):
        R.delete(k)


def sql(q: str) -> str:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    async def _q():
        motor = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
        try:
            # `begin` confirma al salir: los UPDATE de prueba (TUR-008) quedan guardados.
            async with motor.begin() as cx:
                res = await cx.execute(text(q))
                filas = res.all() if res.returns_rows else []
                return "\n".join("|".join("" if v is None else str(v) for v in f) for f in filas)
        finally:
            await motor.dispose()
    return asyncio.run(_q())


e.clear_rate_limit = limpiar
_valor_original = e.valor


def _valor(campo, persona):
    """El estado de la dirección es una lista: qa_e2e tomaba la primera opción («CA»)."""
    opciones = [o["value"] for o in campo.get("options") or []]
    if campo["key"].endswith("state") and persona["state"] in opciones:
        return persona["state"]
    return _valor_original(campo, persona)


def _worker(code: str) -> str:
    """`qa_e2e.worker` llama a `docker compose exec`, que no existe dentro del
    contenedor: aquí la misma función corre con el Python del contenedor."""
    import subprocess
    import sys

    script = ("import asyncio\nfrom app.db.session import AsyncSessionLocal\n"
              "async def main():\n    async with AsyncSessionLocal() as db:\n" +
              "".join(f"        {line}\n" for line in code.splitlines()) + "asyncio.run(main())\n")
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd="/app",
                       env={"PYTHONPATH": "/app", **__import__("os").environ})
    return (r.stdout + r.stderr).strip()


e.valor = _valor
e.worker = _worker
e.sql = sql
e.section = lambda nombre: None
e.USERS.update({"vendedor2": "vendedor2@demo-org.com", "luis": "tecnico04@demo-org.com",
                "carlos": "tecnico03@demo-org.com", "ajeno": "admin@otra-org.com"})


def esc(eid: str):
    e.SECTION[0] = eid


def chk(nombre, ok, dato=""):
    e.check(nombre, bool(ok), str(dato))


def recoger():
    for r in e.RESULTS:
        OUT.setdefault(r["section"], []).append({"check": r["step"], "ok": r["ok"], "dato": r["detail"]})
    e.RESULTS.clear()


def seguro(eid, fn, *a, **kw):
    esc(eid)
    try:
        return fn(*a, **kw)
    except Exception as ex:  # noqa: BLE001
        chk(f"El bloque terminó sin error inesperado ({type(ex).__name__})", False, repr(ex)[:300])
        return None


def cliente(rol: str) -> e.Client:
    return e.Client(rol)


def login(correo: str, clave: str = e.PASSWORD) -> httpx.Response:
    limpiar()
    return httpx.post(f"{API}/auth/login", json={"email": correo, "password": clave}, timeout=30)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def prep_p03(admin, v) -> None:
    """P-03: zona de venta del vendedor, tarifa y zona de cobro de cada programa."""
    progs = {p["code"]: p for p in admin.get("/programs").json()}
    e.asignar_zona_az(admin, v)
    if not any(m["program"]["code"] == "TECH_CLEAN_CA" for m in v.get("/me/programs").json()):
        z = admin.post(f"/programs/{progs['TECH_CLEAN_CA']['id']}/zones", json={
            "name": f"QA San Fernando {e.RUN}", "state": "CA", "city": "San Fernando"}).json()
        admin.put(f"/zones/{z['id']}/salespeople", json={"user_ids": [v.me["id"]]})
    for codigo, ciudad in (("AZ_EFFICIENCY", "Phoenix"), ("TECH_CLEAN_CA", "San Fernando")):
        pid_prog = progs[codigo]["id"]
        if not admin.get(f"/billing/programs/{pid_prog}/rates").json():
            admin.post(f"/billing/programs/{pid_prog}/rates", json={
                "amount": "6500.00", "valid_from": (e.HOY - timedelta(days=30)).isoformat(),
                "notes": "Tarifa de prueba QA (P-03)"})
        if not admin.get(f"/billing/programs/{pid_prog}/jurisdictions").json():
            admin.post(f"/billing/programs/{pid_prog}/jurisdictions", json={
                "kind": "city", "value": ciudad, "valid_from": (e.HOY - timedelta(days=30)).isoformat()})
    e.configurar_tech(admin)


def aprobar_rapido(v, adm, admin, n, state="CA", programa="TECH_CLEAN_CA") -> tuple[str, str]:
    """Venta completa y aprobada: devuelve (expediente, obra)."""
    cid, _ = e.flujo_vendedor(v, adm, n, state, programa)
    for d in adm.get(f"/cases/{cid}/documents").json():
        adm.post(f"/case-files/{d['id']}/review", json={"status": "accepted"})
    for s in ("ready_to_submit", "submitted_to_program", "program_review"):
        adm.post(f"/cases/{cid}/substatus", json={"substatus": s})
    admin.post(f"/cases/{cid}/transition", json={"to_stage": "approved", "approval_code": f"QA-{n}-{e.RUN}"})
    return cid, e.proyecto_de(adm, cid)["id"]


def guardar(ruta: str) -> None:
    recoger()
    OUT.pop("_prep", None)
    json.dump(OUT, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
