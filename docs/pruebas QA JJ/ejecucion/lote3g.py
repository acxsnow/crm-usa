"""Lote 3, fase G: PER-002 (volumen). Solo en la base local de QA.

Copia un expediente existente 1,000 veces y un movimiento de bodega 5,000 veces
(filas nuevas, con su id y número), mide las listas en la página 1 y la 20, el
buscador, y corre EXPLAIN ANALYZE de las dos consultas más pesadas. Los
movimientos copiados no tocan el saldo: al terminar la QA se reinicia la base.

PYTHONPATH=/app:/tmp python /tmp/lote3g.py → /tmp/lote3g.json
"""
import asyncio
import json
import time
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from qa_comun import chk, cliente, e, esc, guardar, limpiar, sql

admin = cliente("admin")
ORG = admin.me["organization_id"]


async def cargar():
    motor = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    async with motor.begin() as cx:
        caso = (await cx.execute(text("select * from cases where organization_id = :o limit 1"), {"o": ORG})).mappings().first()
        mov = (await cx.execute(text("select * from warehouse_movements where organization_id = :o and "
                                     "movement_type = 'entrada' limit 1"), {"o": ORG})).mappings().first()
        cols_c = list(caso.keys())
        cols_m = list(mov.keys())
        filas_c = []
        for i in range(1000):
            f = dict(caso)
            f["id"] = uuid.uuid4()
            f["case_number"] = f"CASE-QAV-{i:05d}"
            filas_c.append(f)
        filas_m = []
        for i in range(5000):
            f = dict(mov)
            f["id"] = uuid.uuid4()
            f["source_key"] = None
            f["note"] = f"QA volumen {i}"
            filas_m.append(f)
        await cx.execute(text(f"insert into cases ({', '.join(cols_c)}) values ({', '.join(':' + x for x in cols_c)})"),
                         filas_c)
        await cx.execute(text(f"insert into warehouse_movements ({', '.join(cols_m)}) values "
                              f"({', '.join(':' + x for x in cols_m)})"), filas_m)
        await cx.execute(text("analyze cases"))
        await cx.execute(text("analyze warehouse_movements"))
    await motor.dispose()


def medir(ruta, params):
    ms = []
    for _ in range(3):
        t0 = time.perf_counter()
        r = admin.get(ruta, params=params)
        ms.append((time.perf_counter() - t0) * 1000)
    return round(max(ms)), r.status_code, r.headers.get("x-total-count")


def per002():
    asyncio.run(cargar())
    n_casos = sql(f"select count(*) from cases where organization_id = '{ORG}'")
    n_movs = sql(f"select count(*) from warehouse_movements where organization_id = '{ORG}'")
    chk(f"Volumen cargado: {n_casos} expedientes y {n_movs} movimientos", int(n_casos) >= 1000 and int(n_movs) >= 5000, "")
    tiempos = {
        "Expedientes p1": medir("/cases", {"limit": 50, "offset": 0}),
        "Expedientes p20": medir("/cases", {"limit": 50, "offset": 950}),
        "Tablero p1": medir("/case-board", {}),
        "Movimientos p1": medir("/warehouse/movements", {"limit": 50, "offset": 0}),
        "Movimientos p20": medir("/warehouse/movements", {"limit": 50, "offset": 950}),
        "Buscador «QAV»": medir("/search", {"q": "CASE-QAV-00999"}),
        "Buscador «QA volumen»": medir("/search", {"q": "QA volumen 4999"}),
    }
    lentas = {k: v for k, v in tiempos.items() if v[0] >= 500 or v[1] != 200}
    chk("Con el volumen cada lista responde en menos de 500 ms (3 veces cada una)", not lentas, json.dumps(tiempos))
    p1, p20 = tiempos["Expedientes p1"][0], tiempos["Expedientes p20"][0]
    m1, m20 = tiempos["Movimientos p1"][0], tiempos["Movimientos p20"][0]
    chk(f"La página 20 tan rápida como la 1 (expedientes {p1}→{p20} ms, movimientos {m1}→{m20} ms)",
        p20 <= max(2 * p1, p1 + 150) and m20 <= max(2 * m1, m1 + 150), "")
    plan_m = sql(f"explain analyze select * from warehouse_movements where organization_id = '{ORG}' order by "
                 f"movement_date desc, created_at desc, recorded_at desc nulls last, id desc limit 50 offset 950")
    plan_c = sql(f"explain analyze select * from cases where organization_id = '{ORG}' "
                 f"order by created_at desc limit 50 offset 950")
    for nombre, plan in (("movimientos", plan_m), ("expedientes", plan_c)):
        ejec = next((l for l in plan.split("\n") if "Execution Time" in l), "")
        chk(f"EXPLAIN ANALYZE de {nombre}: {ejec.strip()} (anotar el plan)", True, plan.replace("\n", " | ")[:700])


esc("PER-002")
try:
    per002()
except Exception as ex:  # noqa: BLE001
    chk(f"El bloque terminó sin error inesperado ({type(ex).__name__})", False, repr(ex)[:300])
limpiar()
guardar("/tmp/lote3g.json")
print("ok")
