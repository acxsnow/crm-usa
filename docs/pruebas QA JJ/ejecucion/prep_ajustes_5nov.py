"""Datos para la prueba de pantalla de los ajustes del 5 nov 2026 (segunda tanda).

Por vista (pc y celular):
- E: expediente TECH aprobado con obra y sin permiso (permiso opcional, aviso,
  evidencias en el acta, inspección eléctrica, permiso cerrado en el cobro).
- Q: obra nacida de una cotización aceptada (sin checklist).
- P: acta confirmada (para el permiso cerrado del cobro).
- V: un expediente nuevo de TECH, para mirar el formulario del vendedor.

PYTHONPATH=/app:/tmp python /tmp/prep_ajustes_5nov.py → /tmp/prep_ajustes_5nov_datos.json
"""
import json

from qa_comun import aprobar_rapido, chk, cliente, e, esc, guardar, prep_p03

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta")}
admin, adm, v = c["admin"], c["adm"], c["vendedor"]
prep_p03(admin, v)
D: dict = {}
esc("AJ-5NOV-prep")
progs = {p["code"]: p for p in admin.get("/programs").json()}
for vista, base in (("pc", 550), ("celular", 560)):
    cid, pid = aprobar_rapido(v, adm, admin, base + 1)
    D[vista] = {"E": {"case": cid, "project": pid, "number": admin.get(f"/cases/{cid}").json()["case_number"]}}

    cli = adm.post("/customers", json={"legal_name": f"QA Cotización {vista} {e.RUN}", "main_phone": "6025550100",
                                       "billing_address": "77 Quote Rd, Phoenix", "data_consent_accepted": True}).json()
    q = adm.post("/billing/quotes", json={"customer_id": cli["id"], "title": f"Reparación de ductos {vista}",
                                          "lines": [{"kind": "labor", "description": "Reparación", "quantity": 1,
                                                     "unit_price": 150}]}).json()
    adm.post(f"/billing/quotes/{q['id']}/send")
    r = adm.post(f"/billing/quotes/{q['id']}/accept", json={})
    chk(f"{vista}: la cotización aceptada crea la obra", r.status_code == 200, r.text[:200])
    q = adm.get(f"/billing/quotes/{q['id']}").json()
    D[vista]["Q"] = {"project": q.get("project_id")}

    # P: acta confirmada, para subir el permiso cerrado desde el cobro.
    cid2, pid2 = aprobar_rapido(v, adm, admin, base + 7)
    e.flujo_campo(adm, c["tecnico"], cid2, devolver_acta=False, permiso=False)
    D[vista]["P"] = {"case": cid2, "project": pid2}

    visita = e.abrir_puerta(v, e.persona(base + 5, "CA"), "TECH_CLEAN_CA")
    chk(f"{vista}: expediente nuevo para el formulario", bool(visita.get("case")), str(visita)[:200])
    D[vista]["V"] = {"case": visita["case"]["id"]} if visita.get("case") else {}

json.dump(D, open("/tmp/prep_ajustes_5nov_datos.json", "w"), ensure_ascii=False, indent=1)
guardar("/tmp/prep_ajustes_5nov.json")
print(json.dumps(D, indent=1))
