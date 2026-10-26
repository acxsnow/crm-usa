"""Datos para el lote 4b de pantalla. Corre en el contenedor api con la base QA
recién cargada: PYTHONPATH=/app:/tmp python /tmp/prep4b.py → /tmp/prep4b.json
"""
import json
from datetime import timedelta

from qa_comun import aprobar_rapido, cliente, e, limpiar, prep_p03, sql

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia")}
admin, adm, v, tec, conta, ger = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["conta"], c["gerencia"]
HOY = e.HOY
D: dict = {}
prep_p03(admin, v)


def agendar(pid, dias=1, tecnico=None):
    adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": (tecnico or tec.me["id"]),
                                                  "scheduled_date": (HOY + timedelta(days=dias)).isoformat()})


def salida(pid, item_id, cantidad, autorizar=True, entregar=False):
    o = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": item_id, "quantity": cantidad}]}).json()
    tec.post(f"/warehouse/releases/{o['id']}/submit")
    if autorizar:
        adm.post(f"/warehouse/releases/{o['id']}/approve")
    if entregar:
        adm.post(f"/warehouse/releases/{o['id']}/deliver", json={})
    return o["id"]


def articulo(sku):
    return next(i for i in admin.get("/warehouse/items", params={"q": sku}).json() if i["sku"] == sku)


# INS-010 / INS-011: obra programada a Tito para la visita fallida por pantalla.
_, D["pid_visita"] = aprobar_rapido(v, adm, admin, 401)
agendar(D["pid_visita"])
# INS-012: obra con material afuera y una salida por autorizar, para cancelar.
_, D["pid_cancelar"] = aprobar_rapido(v, adm, admin, 402)
agendar(D["pid_cancelar"])
pvc = articulo("3496")
salida(D["pid_cancelar"], pvc["id"], "2", entregar=True)
D["salida_abierta"] = salida(D["pid_cancelar"], pvc["id"], "1", autorizar=False)
# D-007: salida autorizada con el equipo con serial (85980), para entregar por pantalla.
_, D["pid_serial"] = aprobar_rapido(v, adm, admin, 403)
agendar(D["pid_serial"])
D["salida_serial"] = salida(D["pid_serial"], articulo("85980")["id"], "1")
# D-002 / FIN-005: obra con pérdida (factura de proveedor cargada y nada cobrado).
_, D["pid_perdida"] = aprobar_rapido(v, adm, admin, 404)
prov = conta.post("/payables/suppliers", json={"name": f"QA Proveedor pérdida {e.RUN}", "kinds": ["other"]}).json()
conta.post("/payables/invoices", data={"data": json.dumps({
    "supplier_id": prov["id"], "number": f"QA-PERD-{e.RUN}", "invoice_date": HOY.isoformat(),
    "lines": [{"description": "QA equipo de la obra con pérdida", "category": "equipment", "quantity": "1",
               "unit_cost": "80705.00", "project_id": D["pid_perdida"]}]})})
# VEN-001: dos puertas que no abrieron.
for n, res in ((405, "no_contact"), (406, "not_interested")):
    e.abrir_puerta(v, e.persona(n, "AZ"), "AZ_EFFICIENCY", res)
# REV-001: expediente enviado con documentos sin revisar.
D["cid_revisar"], _ = e.flujo_vendedor(v, adm, 407, "AZ", "AZ_EFFICIENCY")
# REV-002: expediente devuelto al vendedor con el motivo.
D["cid_devuelto"], _ = e.flujo_vendedor(v, adm, 408, "AZ", "AZ_EFFICIENCY")
docs = adm.get(f"/cases/{D['cid_devuelto']}/documents").json()
adm.post(f"/case-files/{docs[0]['id']}/review", json={"status": "rejected", "notes": "QA: la foto está borrosa"})
adm.post(f"/cases/{D['cid_devuelto']}/substatus", json={"substatus": "returned",
                                                        "reason": "QA: reemplaza la foto borrosa del panel"})
# TEC-003 / TUR-009: obras de la semana para 5 técnicos más.
tecnicos = adm.get("/dispatch/technicians").json()
for i, t in enumerate(tecnicos[:5]):
    _, pid = aprobar_rapido(v, adm, admin, 410 + i)
    agendar(pid, dias=1 + i % 4, tecnico=t["id"])
# TUR-001: turnos de la semana que viene para 5 técnicos.
lunes = HOY + timedelta(days=7 - HOY.weekday())
adm.post("/attendance/shifts", json={"user_ids": [t["id"] for t in tecnicos[:5]], "date_from": lunes.isoformat(),
                                     "date_to": (lunes + timedelta(days=4)).isoformat(), "start_time": "07:00",
                                     "end_time": "16:00", "break_minutes": 60})
D["lunes"] = lunes.isoformat()
# AUTH-007: rol sin permisos para tecnico06.
admin.post("/roles", json={"code": "qa_sin_permisos", "name": "QA sin permisos", "permissions": []})
t6 = next(u for u in admin.get("/users", params={"limit": 100}).json()["items"] if u["email"] == "tecnico06@demo-org.com")
admin.patch(f"/users/{t6['id']}/roles", json={"role_codes": ["qa_sin_permisos"]})
D["t6"] = t6["id"]
D["org"] = admin.me["organization_id"]
D["case_numbers"] = sql("select case_number from cases order by created_at desc limit 3").split("\n")
limpiar()
json.dump(D, open("/tmp/prep4b.json", "w"))
print(json.dumps(D))
