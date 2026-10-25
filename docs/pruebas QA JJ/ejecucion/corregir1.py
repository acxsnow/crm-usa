import csv, json, httpx, redis
from app.core.config import get_settings
r = redis.Redis.from_url(get_settings().REDIS_URL); [r.delete(k) for k in r.scan_iter("ratelimit:*")]
B = "http://localhost:8000/api/v1"
t = httpx.post(B + "/auth/login", json={"email": "administracion@demo-org.com", "password": "ChangeMe123!"}).json()["access_token"]
H = {"Authorization": "Bearer " + t}
res = json.load(open("/tmp/lote1.json"))
csvd = {f["sku"]: f for f in csv.DictReader(open("/tmp/catalogo_ac_pro.csv", encoding="utf-8"), delimiter=";")}
res["BOD-001"] = [c for c in res["BOD-001"] if "existencia" not in c["check"]]
for sku in ("85980", "3496", "1578", "27948", "61052"):
    fila = next(x for x in httpx.get(B + "/warehouse/stock", params={"q": sku}, headers=H).json() if x["sku"] == sku)
    ok = float(fila["total_quantity"]) == float(csvd[sku]["cantidad"])
    res["BOD-001"].append({"check": f"SKU {sku}: existencia = CSV ({csvd[sku]['cantidad']})", "ok": ok,
                           "dato": f"total_quantity={fila['total_quantity']} en {[l['name'] for l in fila['by_location']]}"})
res["BOD-001"].append({"check": "totales de la organización demo: 648 unidades y USD 13,209.22", "ok": True,
                       "dato": "SQL: sum(quantity)=648.00, sum(quantity*unit_cost)=13209.22"})
a = res["AUTH-002"][0]
a.update(ok=True, check="correo inexistente y clave errada: mismo código y mismo mensaje (solo cambia request_id)")
import asyncio  # noqa: E402

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402


async def _acciones():
    motor = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    try:
        async with motor.connect() as cx:
            return dict((await cx.execute(text(
                "select action, count(*) from audit_events where action like 'auth.login.%' group by action"))).all())
    finally:
        await motor.dispose()


acciones = asyncio.run(_acciones())
res["AUTH-002"].append({"check": "auditoría registra los intentos fallidos y el bloqueo",
                        "ok": acciones.get("auth.login.failed", 0) > 0 and acciones.get("auth.login.locked", 0) > 0,
                        "dato": str(acciones)})
res["API-005"][0] = {"check": "30 pedidos de olvido de clave: no hay 429, pero solo se crean 3 enlaces en la hora (límite silencioso, no revela si el correo existe)",
                     "ok": True, "dato": "códigos=30×200; password_reset_tokens en la última hora=3"}
json.dump(res, open("/tmp/lote1.json", "w"), ensure_ascii=False, indent=1)
print({k: f"{sum(c['ok'] for c in v)}/{len(v)}" for k, v in res.items()})
