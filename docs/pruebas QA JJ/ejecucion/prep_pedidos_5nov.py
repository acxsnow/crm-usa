"""Datos para la prueba de pantalla de los pedidos del 4 y 5 nov 2026.

Un juego por vista (pc y celular), con tres expedientes aprobados y su obra:
- A: sin permiso, para registrar «En trámite» en pantalla.
- B: sin permiso, para registrar «Radicado» en pantalla y ver el aviso.
- C: permiso «En trámite», instalación cerrada, acta confirmada y cobro radicado
  y pagado; en pantalla se intenta cerrar sin el aprobado.

PYTHONPATH=/app:/tmp python /tmp/prep_pedidos_5nov.py → /tmp/prep_pedidos_5nov_datos.json
"""
import json

from qa_comun import aprobar_rapido, chk, cliente, e, esc, guardar, prep_p03

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta")}
admin, adm, v, tec, conta = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["conta"]
prep_p03(admin, v)
D: dict = {}


def numero(cid):
    return admin.get(f"/cases/{cid}").json()["case_number"]


esc("PED-5NOV-prep")
for vista, base in (("pc", 490), ("celular", 500)):
    D[vista] = {}
    for clave, n in (("A", base + 1), ("B", base + 2)):
        cid, pid = aprobar_rapido(v, adm, admin, n)
        D[vista][clave] = {"case": cid, "project": pid, "number": numero(cid)}

    cid, pid = aprobar_rapido(v, adm, admin, base + 3)
    r = adm.post(f"/projects/{pid}/permits", json={"jurisdiction": "San Fernando", "status": "in_process"})
    chk(f"{vista} C: permiso «En trámite»", r.status_code == 201, r.text[:200])
    e.flujo_campo(adm, tec, cid, devolver_acta=False, permiso=False)
    e.flujo_cobro(adm, conta, admin, pid, cid, "TECH_CLEAN_CA", rechazar=False, cerrar=False)
    etapa = admin.get(f"/cases/{cid}").json()["stage_code"]
    D[vista]["C"] = {"case": cid, "project": pid, "permit": r.json().get("id"), "number": numero(cid), "stage": etapa}
    chk(f"{vista} C: con el permiso en trámite, el cobro se radicó y pagó", etapa == "paid", etapa)

json.dump(D, open("/tmp/prep_pedidos_5nov_datos.json", "w"), ensure_ascii=False, indent=1)
guardar("/tmp/prep_pedidos_5nov.json")
print(json.dumps(D, indent=1))
