"""Ataque a bodega: existencias, salidas, seriales, conteos y costos anotados (10 nov 2026).

PYTHONPATH=/app:/tmp python /tmp/qa_bodega.py → /tmp/qa_bodega.json
"""
import random
import threading
from datetime import timedelta
from decimal import Decimal

from qa_comun import aprobar_rapido, chk, cliente, e, esc, guardar, prep_p03

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "carlos", "gerencia", "ajeno")}
admin, adm, v, tec, carlos, ger, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "tecnico", "carlos", "gerencia",
                                                          "ajeno"))
prep_p03(admin, v)
HOY = e.HOY
RUN = e.RUN


def D(x):
    return Decimal(str(x))


def bodega():
    locs = adm.get("/warehouse/locations", params={"page_size": 50}).json()
    return next(l["id"] for l in locs if l.get("kind") in ("warehouse", "bodega") or "odega" in l.get("name", ""))


def existencia(item_id):
    filas = adm.get("/warehouse/stock", params={"q": item_id, "limit": 5}).json()
    fila = next((f for f in (filas if isinstance(filas, list) else []) if f.get("id") == item_id), None)
    if fila is None:
        item = adm.get(f"/warehouse/items/{item_id}").json()
        return D(item.get("total_quantity") or 0)
    return D(fila.get("total_quantity") or 0)


def articulo(nombre, costo="10.00", cantidad="5", **kw):
    it = e.expect(f"Artículo {nombre}", adm.post("/warehouse/items", json={
        "name": f"QA {RUN} {nombre} {random.randint(1, 99999)}", "unit_cost": costo, **kw}), 201) or {}
    if cantidad:
        adm.post("/warehouse/movements", json={"item_id": it.get("id"), "movement_type": "entrada", "quantity": cantidad,
                                               "unit_cost": costo, "location_id": bodega()})
    return it


# ===========================================================================
esc("BOD-A1 Catálogo y movimientos")
# ===========================================================================
r = adm.post("/warehouse/items", json={"name": f"QA {RUN} negativo", "unit_cost": "-5"})
chk("Costo negativo se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post("/warehouse/items", json={"name": "", "unit_cost": "5"})
chk("Artículo sin nombre se rechaza", r.status_code in (400, 422), r.status_code)
it = articulo("filtro", "10.00", "5")
for nombre, cuerpo in (("cantidad negativa", {"quantity": "-3"}), ("cantidad cero", {"quantity": "0"}),
                       ("cantidad con texto", {"quantity": "tres"}), ("cantidad gigante", {"quantity": "1e30"})):
    r = adm.post("/warehouse/movements", json={"item_id": it.get("id"), "movement_type": "entrada",
                                               "location_id": bodega(), **cuerpo})
    chk(f"Entrada con {nombre} se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post("/warehouse/movements", json={"item_id": it.get("id"), "movement_type": "salida", "quantity": "1"})
chk("Una salida a mano, sin orden, se rechaza", r.status_code == 400, r.status_code)
r = adm.post("/warehouse/movements", json={"item_id": it.get("id"), "movement_type": "traslado", "quantity": "99",
                                           "location_id": bodega(), "to_location_id": bodega()})
chk("Trasladar más de lo que hay (o a la misma bodega) se rechaza", r.status_code in (400, 409), r.status_code)
r = tec.post("/warehouse/movements", json={"item_id": it.get("id"), "movement_type": "entrada", "quantity": "100",
                                           "location_id": bodega()})
chk("El técnico no mete existencias", r.status_code == 403, r.status_code)
r = ajeno.get(f"/warehouse/items/{it.get('id')}")
chk("Otra organización no ve el artículo", r.status_code in (403, 404), r.status_code)
r = ajeno.post("/warehouse/movements", json={"item_id": it.get("id"), "movement_type": "entrada", "quantity": "1"})
chk("Otra organización no le mueve existencias", r.status_code in (400, 403, 404), r.status_code)
r = tec.get(f"/warehouse/items/{it.get('id')}")
cuerpo = r.json() if r.status_code == 200 else {}
chk("El técnico no ve el costo de los artículos", r.status_code in (403, 404) or not cuerpo.get("unit_cost") or
    str(cuerpo.get("unit_cost")) in ("None", ""), str(cuerpo)[:150])

# ===========================================================================
esc("BOD-A2 Salidas a obra")
# ===========================================================================
cid, pid = aprobar_rapido(v, adm, admin, 1101)
adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"],
                                             "scheduled_date": (HOY + timedelta(days=1)).isoformat()})
r = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": it.get("id"), "quantity": "-2"}]})
chk("Una salida con cantidad negativa se rechaza", r.status_code in (400, 422), r.status_code)
r = carlos.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": it.get("id"), "quantity": "1"}]})
chk("Otro técnico no pide material para una obra ajena", r.status_code in (400, 403, 404), r.status_code)
o = e.expect("Tito pide 8 filtros (hay 5)", tec.post("/warehouse/releases", json={
    "project_id": pid, "lines": [{"item_id": it.get("id"), "quantity": "8"}]}), 201) or {}
e.expect("La envía a autorizar", tec.post(f"/warehouse/releases/{o.get('id')}/submit"), 200)
r = tec.post(f"/warehouse/releases/{o.get('id')}/approve")
chk("El técnico no autoriza su propia salida", r.status_code == 403, r.status_code)
r = v.post(f"/warehouse/releases/{o.get('id')}/approve")
chk("El vendedor no autoriza salidas", r.status_code == 403, r.status_code)
r = adm.post(f"/warehouse/releases/{o.get('id')}/deliver", json={})
chk("No se entrega sin autorizar", r.status_code in (400, 409), r.status_code)
e.expect("Administración la autoriza", adm.post(f"/warehouse/releases/{o.get('id')}/approve"), 200)
antes = existencia(it.get("id"))
codigos = []


def entregar():
    codigos.append(adm.post(f"/warehouse/releases/{o.get('id')}/deliver", json={}).status_code)


hilos = [threading.Thread(target=entregar) for _ in range(3)]
[h.start() for h in hilos]
[h.join() for h in hilos]
despues = existencia(it.get("id"))
chk(f"Tres entregas a la vez: solo una pasa ({codigos})", codigos.count(200) <= 1, codigos)
chk(f"La existencia nunca queda negativa (antes {antes}, después {despues})", despues >= 0, despues)
r = adm.post(f"/warehouse/releases/{o.get('id')}/deliver", json={})
chk("Entregar de nuevo una salida ya entregada se bloquea", r.status_code in (400, 409), r.status_code)
r = adm.post(f"/warehouse/releases/{o.get('id')}/cancel", json={"reason": "QA anular entregada"})
chk("No se anula una salida ya entregada", r.status_code in (400, 409), r.status_code)

# ===========================================================================
esc("BOD-A3 Seriales")
# ===========================================================================
ser = f"QA-SER-{RUN}"
it_s = articulo("condensadora", "900.00", None, has_serial=True)
r = adm.post("/warehouse/movements", json={"item_id": it_s.get("id"), "movement_type": "entrada", "quantity": "2",
                                           "unit_cost": "900.00", "location_id": bodega(), "serials": [ser, ser]})
chk("El mismo serial dos veces en una entrada se rechaza", r.status_code in (400, 409, 422), r.status_code)
r = adm.post("/warehouse/movements", json={"item_id": it_s.get("id"), "movement_type": "entrada", "quantity": "2",
                                           "unit_cost": "900.00", "location_id": bodega(), "serials": [ser]})
chk("Dos unidades con un solo serial se rechazan", r.status_code in (400, 422), r.status_code)
e.expect("Entrada de 1 con su serial", adm.post("/warehouse/movements", json={
    "item_id": it_s.get("id"), "movement_type": "entrada", "quantity": "1", "unit_cost": "900.00",
    "location_id": bodega(), "serials": [ser]}), 201)
r = adm.post("/warehouse/movements", json={"item_id": it_s.get("id"), "movement_type": "entrada", "quantity": "1",
                                           "unit_cost": "900.00", "location_id": bodega(), "serials": [ser]})
chk("Un serial que ya está en bodega no entra otra vez", r.status_code in (400, 409), r.status_code)

# ===========================================================================
esc("BOD-A4 Costos anotados y presupuesto")
# ===========================================================================
r = adm.post(f"/warehouse/projects/{pid}/cost-entries", json={"category": "contractor", "amount": "-500",
                                                              "entry_date": HOY.isoformat(), "description": "QA"})
chk("Un costo anotado negativo se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.post(f"/warehouse/projects/{pid}/cost-entries", json={"category": "contractor", "amount": "500",
                                                              "entry_date": HOY.isoformat(), "description": "QA"})
chk("El técnico no anota costos internos", r.status_code == 403, r.status_code)
r = ajeno.post(f"/warehouse/projects/{pid}/cost-entries", json={"category": "contractor", "amount": "1",
                                                                "entry_date": HOY.isoformat(), "description": "QA"})
chk("Otra organización no anota costos en nuestra obra", r.status_code in (403, 404), r.status_code)
r = tec.post(f"/warehouse/projects/{pid}/extra-charges", json={"amount": "-40", "description": "QA efectivo"})
chk("Un cobro adicional negativo se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.post(f"/warehouse/projects/{pid}/extra-charges", json={"amount": "40", "description": "QA efectivo"})
cargo = r.json() if r.status_code == 201 else {}
chk(f"El técnico anota 40 en efectivo ({r.status_code})", r.status_code in (201, 400, 422), r.status_code)
if cargo.get("id"):
    rr = tec.post(f"/warehouse/extra-charges/{cargo['id']}/deliver", json={})
    chk("El técnico no marca como recibido su propio efectivo", rr.status_code == 403, rr.status_code)

guardar("/tmp/qa_bodega.json")
print("FIN")
