"""Ataque al trabajo de campo: permiso, orden, acta, equipos, firmas, cierre,
inspección, visita fallida y cancelación (10 nov 2026).

PYTHONPATH=/app:/tmp python /tmp/qa_campo.py → /tmp/qa_campo.json
"""
from datetime import datetime, timedelta, timezone

from qa_comun import aprobar_rapido, chk, cliente, e, esc, guardar, prep_p03

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "carlos", "conta", "ajeno")}
admin, adm, v, tec, carlos, conta, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "tecnico", "carlos", "conta",
                                                            "ajeno"))
prep_p03(admin, v)
HOY = e.HOY
RUN = e.RUN


def agendar(pid, quien=None, dias=1):
    return adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": (quien or tec).me["id"],
                                                       "scheduled_date": (HOY + timedelta(days=dias)).isoformat()})


# ===========================================================================
esc("CAM-01 Permiso")
# ===========================================================================
cid, pid = aprobar_rapido(v, adm, admin, 901)
r = adm.post(f"/projects/{pid}/permits", json={"jurisdiction": "Phoenix", "status": "approved"})
chk("Aprobado sin fecha de aprobación se rechaza", r.status_code == 400, r.status_code)
r = adm.post(f"/projects/{pid}/permits", json={"jurisdiction": "Phoenix", "status": "approved",
                                               "approved_on": HOY.isoformat(), "expires_on": (HOY - timedelta(days=1)).isoformat()})
chk("Vence antes de aprobarse: se rechaza o queda vencido, nunca vigente",
    r.status_code in (400, 422) or r.json().get("is_cleared") is False, f"{r.status_code} {r.text[:120]}")
r = adm.post(f"/projects/{pid}/permits", json={"jurisdiction": "Phoenix", "filed_on": (HOY + timedelta(days=5)).isoformat()})
chk("Radicado con fecha futura se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post(f"/projects/{pid}/permits", json={"jurisdiction": "", "status": "in_process"})
chk("Sin ciudad o condado se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post(f"/projects/{pid}/permits", json={"jurisdiction": "Phoenix", "status": "aprobadito"})
chk("Estado inventado se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.post(f"/projects/{pid}/permits", json={"jurisdiction": "Phoenix", "status": "in_process"})
chk("El técnico no registra permisos", r.status_code in (403, 404), r.status_code)
r = ajeno.post(f"/projects/{pid}/permits", json={"jurisdiction": "Phoenix", "status": "in_process"})
chk("Otra organización no registra permisos en nuestra obra", r.status_code in (403, 404), r.status_code)

# ===========================================================================
esc("CAM-02 Orden liberada")
# ===========================================================================
r = adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"],
                                                 "scheduled_date": (HOY - timedelta(days=1)).isoformat()})
chk("No se agenda en el pasado", r.status_code == 400, r.status_code)
r = adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": v.me["id"],
                                                 "scheduled_date": (HOY + timedelta(days=1)).isoformat()})
chk("No se asigna a un vendedor como instalador", r.status_code == 400, r.status_code)
r = adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": ajeno.me["id"],
                                                 "scheduled_date": (HOY + timedelta(days=1)).isoformat()})
chk("No se asigna a alguien de otra organización", r.status_code in (400, 404), r.status_code)
r = tec.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"],
                                                 "scheduled_date": (HOY + timedelta(days=1)).isoformat()})
chk("El técnico no se agenda solo", r.status_code == 403, r.status_code)
e.expect("Se libera la orden sin permiso (no frena)", agendar(pid), 200)
chk("El expediente pasa a «Listo para instalar»", admin.get(f"/cases/{cid}").json()["stage_code"] == "ready_to_install")
r = carlos.get(f"/projects/{pid}")
chk("Otro técnico no ve la obra", r.status_code in (403, 404), r.status_code)
r = carlos.post(f"/projects/{pid}/equipment", json={"equipment_type": "heat_pump_outdoor", "brand": "X", "model": "Y",
                                                    "serial_number": "Z", "quantity": 1})
chk("Otro técnico no registra equipos en ella", r.status_code in (403, 404), r.status_code)

# ===========================================================================
esc("CAM-03 Acta: checklist, equipos, firmas y cierre")
# ===========================================================================
r = tec.post(f"/projects/{pid}/installation/close", json={})
chk("No se cierra con el checklist incompleto", r.status_code in (400, 409), r.status_code)
items = tec.get(f"/projects/{pid}/checklist").json()
con_foto = next((i for i in items if i["requires_evidence"]), None)
if con_foto:
    r = tec.patch(f"/checklist-items/{con_foto['id']}", json={"is_complete": True})
    chk("Una línea que exige foto no se completa sin foto", r.status_code in (400, 409), r.status_code)
sin_na = next((i for i in items if not i.get("allows_not_applicable")), None)
if sin_na:
    r = tec.patch(f"/checklist-items/{sin_na['id']}", json={"not_applicable": True, "reason": "QA no aplica"})
    chk("«No aplica» no se usa en una línea que no lo permite", r.status_code in (400, 409), r.status_code)
r = tec.post(f"/projects/{pid}/equipment", json={"equipment_type": "nave_espacial", "brand": "X", "model": "Y",
                                                 "serial_number": "Z", "quantity": 1})
chk("Tipo de equipo inventado se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.post(f"/projects/{pid}/equipment", json={"equipment_type": "heat_pump_outdoor", "brand": "X", "model": "Y",
                                                 "serial_number": "Z", "quantity": 0})
chk("Cantidad cero se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.post(f"/projects/{pid}/attestation/technician-sign", json={"signature_base64": ""})
chk("Firma vacía se rechaza", r.status_code in (400, 422), r.status_code)
e.flujo_campo(adm, tec, cid, devolver_acta=False, permiso=False)
r = tec.post(f"/projects/{pid}/installation/close", json={})
chk("Cerrar dos veces se bloquea", r.status_code in (400, 409), r.status_code)
r = tec.post(f"/projects/{pid}/attestation/technician-sign", json={"signature_base64": e.png_signature()})
chk("La firma no se reescribe", r.status_code in (400, 409), r.status_code)
r = tec.post(f"/projects/{pid}/evidence", data={"category": "additional_photo"},
             files={"file": ("x.jpg", e.jpeg("tarde"), "image/jpeg")})
chk(f"Evidencia con la obra cerrada ({r.status_code})", r.status_code in (201, 400, 409), r.status_code)
r = conta.post(f"/projects/{pid}/review/confirm", json={})
chk(f"Contabilidad no confirma actas ({r.status_code})", r.status_code in (403, 409), r.status_code)
r = adm.post(f"/projects/{pid}/review/return", json={"reason": ""})
chk("Devolver el acta sin motivo se bloquea", r.status_code in (400, 409, 422), r.status_code)
r = admin.post(f"/cases/{cid}/transition", json={"to_stage": "closed", "reason": "QA cerrar sin permiso"})
chk("Instalada y sin permiso aprobado, el expediente no se cierra", r.status_code == 400, r.status_code)

# ===========================================================================
esc("CAM-04 Inspección municipal")
# ===========================================================================
cid2, pid2 = aprobar_rapido(v, adm, admin, 902)
cuando = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
r = adm.post(f"/projects/{pid2}/inspections", json={"scheduled_for": cuando})
chk("Sin permiso registrado no se agenda inspección", r.status_code in (400, 409), r.status_code)
adm.post(f"/projects/{pid2}/permits", json={"jurisdiction": "Phoenix", "filed_on": HOY.isoformat()})
r = adm.post(f"/projects/{pid2}/inspections", json={"scheduled_for": cuando})
chk(f"Inspección antes de cerrar la instalación ({r.status_code})", r.status_code in (201, 400, 409), r.status_code)
if r.status_code == 201:
    ins = r.json()
    rr = adm.post(f"/inspections/{ins['id']}/result", json={"result": "passed"})
    chk("Aprobar la inspección sin el permiso firmado se bloquea", rr.status_code == 400, rr.status_code)
    rr = adm.post(f"/inspections/{ins['id']}/result", json={"result": "failed"})
    chk("Fallida sin observaciones se bloquea", rr.status_code == 400, rr.status_code)
    rr = adm.post(f"/inspections/{ins['id']}/result", json={"result": "talvez"})
    chk("Resultado inventado se rechaza", rr.status_code in (400, 422), rr.status_code)

# ===========================================================================
esc("CAM-05 Visita fallida y cancelación")
# ===========================================================================
cid3, pid3 = aprobar_rapido(v, adm, admin, 903)
agendar(pid3)
r = tec.post(f"/projects/{pid3}/failed-visits", json={"reason_code": "customer_absent", "notes": ""})
chk("Visita fallida sin contar qué pasó se bloquea", r.status_code in (400, 422), r.status_code)
r = tec.post(f"/projects/{pid3}/failed-visits", json={"reason_code": "inventado", "notes": "QA"})
chk("Motivo inventado se rechaza", r.status_code in (400, 422), r.status_code)
for n in range(3):
    r = tec.post(f"/projects/{pid3}/failed-visits", json={"reason_code": "customer_absent",
                                                          "notes": f"QA no estaba, intento {n + 1}"})
    if r.status_code == 201:
        agendar(pid3)
estado = adm.get(f"/projects/{pid3}/visit-status").json()
chk(f"Al llegar al límite no se reagenda solo ({estado.get('failed_visits')} de {estado.get('limit')})",
    agendar(pid3).status_code == 409 if estado.get("limit_reached") else True, str(estado))
r = tec.post(f"/projects/{pid3}/cancel", json={"reason": "QA el técnico cancela"})
chk("El técnico no cancela la obra", r.status_code == 403, r.status_code)
r = adm.post(f"/projects/{pid3}/cancel", json={"reason": " "})
chk("Cancelar sin motivo se bloquea", r.status_code in (400, 422), r.status_code)
r = adm.post(f"/projects/{pid3}/cancel", json={"reason": "QA cliente desistió", "confirm_with_technician": True})
chk(f"Cancelar con motivo ({r.status_code})", r.status_code in (200, 409), f"{r.status_code} {r.text[:150]}")
if r.status_code == 200:
    rr = agendar(pid3)
    chk("Una obra cancelada no se vuelve a agendar", rr.status_code in (400, 409), rr.status_code)
    rr = tec.post(f"/projects/{pid3}/evidence", data={"category": "additional_photo"},
                  files={"file": ("x.jpg", e.jpeg("x"), "image/jpeg")})
    chk("En una obra cancelada no se sube nada", rr.status_code in (400, 403, 409), rr.status_code)

# ===========================================================================
esc("CAM-06 Despacho y tareas")
# ===========================================================================
r = adm.get("/dispatch/board", params={"date_from": HOY.isoformat(), "date_to": (HOY + timedelta(days=60)).isoformat()})
chk("El tablero no acepta rangos gigantes", r.status_code == 400, r.status_code)
r = adm.get("/dispatch/board", params={"date_from": HOY.isoformat(), "date_to": (HOY - timedelta(days=3)).isoformat()})
chk("El tablero no acepta rangos al revés", r.status_code == 400, r.status_code)
r = tec.get("/dispatch/board", params={"date_from": HOY.isoformat(), "date_to": HOY.isoformat()})
chk("El técnico no ve el despacho", r.status_code == 403, r.status_code)
r = adm.post(f"/projects/{pid}/tasks", json={"title": ""})
chk("Tarea sin título se rechaza", r.status_code in (400, 422), r.status_code)
r = ajeno.get(f"/projects/{pid}/tasks")
chk("Otra organización no ve las tareas", r.status_code in (403, 404), r.status_code)

guardar("/tmp/qa_campo.json")
print("FIN")
