"""Datos de demostración para las capturas del manual de usuario.

Crea expedientes con nombres y direcciones creíbles, cada uno detenido en la
etapa que se quiere capturar, reutilizando los pasos de `scripts/qa_e2e.py`.
Imprime en JSON los ids que usa el script de capturas (`docs/manual/capturas.py`).

Uso (con la app arriba y el atajo `docker` de qa_e2e disponible; ver docs/manual/README.md):
    docker compose exec -T api python -m scripts.manual_demo > manual_demo.json
"""
import json
import sys
from datetime import datetime, timedelta, timezone

from scripts import qa_e2e as qa

PROGRAMA = "AZ_EFFICIENCY"


def persona(n: int, nombre: str, calle: str) -> dict:
    return {"name": nombre, "email": f"{nombre.split()[0].lower()}.{n}@example.com", "phone": f"(602) 555-{2100 + n:04d}",
            "street": calle, "unit": f"Spc {10 + n}", "city": "Phoenix", "state": "AZ", "zip": "85001",
            "lat": "33.45", "lon": "-112.07"}


# Las respuestas de texto libre del QA dicen «QA respuesta de prueba»; en el manual, algo normal.
_valor_qa = qa.valor


def _valor(campo: dict, p: dict):
    v = _valor_qa(campo, p)
    return "Sin observaciones" if isinstance(v, str) and v.startswith("QA respuesta") else v


qa.valor = _valor


def vender(v, p: dict, *, firmar: bool, enviar: bool) -> str:
    r = qa.abrir_puerta(v, p, PROGRAMA)
    case_id = r["case"]["id"]
    qa.llenar_formulario(v, case_id, p)
    if firmar:
        v.post(f"/cases/{case_id}/terms-acceptance", json={"customer_name": p["name"], "signature": qa.png_signature()})
    if enviar:
        v.post(f"/cases/{case_id}/submit")
    return case_id


def aprobar(adm, admin, case_id: str, codigo: str) -> str:
    for d in adm.get(f"/cases/{case_id}/documents").json():
        adm.post(f"/case-files/{d['id']}/review", json={"status": "accepted"})
    for s in ("ready_to_submit", "submitted_to_program", "program_review"):
        adm.post(f"/cases/{case_id}/substatus", json={"substatus": s})
    admin.post(f"/cases/{case_id}/transition", json={"to_stage": "approved", "approval_code": codigo,
                                                      "application_number": codigo.replace("AP", "SOL")})
    return qa.proyecto_de(adm, case_id)["id"]


def permiso(adm, pid: str, numero: str, aprobado: bool) -> None:
    hoy = qa.HOY
    body = {"jurisdiction": "City of Phoenix", "permit_number": numero, "permit_type": "Mecánico",
            "filed_on": (hoy - timedelta(days=6)).isoformat()}
    if aprobado:
        body.update({"status": "approved", "approved_on": (hoy - timedelta(days=1)).isoformat(),
                     "expires_on": (hoy + timedelta(days=180)).isoformat()})
    adm.post(f"/projects/{pid}/permits", json=body)


def agendar(adm, tec, pid: str, dias: int) -> None:
    tid = next((t["id"] for t in adm.get("/dispatch/technicians").json() if t.get("email") == qa.USERS["tecnico"]),
               tec.me["id"])
    adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tid,
                                                 "scheduled_date": (qa.HOY + timedelta(days=dias)).isoformat()})


def materiales(adm, pid: str) -> None:
    for d, cant, unidad in (("Línea de refrigerante 3/8 x 3/4", 25, "ft"), ("Soporte antivibración", 4, "und"),
                            ("Breaker 30 A", 1, "und")):
        adm.post(f"/projects/{pid}/materials", json={"description": d, "quantity": cant, "unit": unidad})


def checklist(tec, pid: str, hasta: int | None = None) -> None:
    hechos = 0
    for it in tec.get(f"/projects/{pid}/checklist").json():
        if hasta is not None and hechos >= hasta:
            break
        if it["is_complete"] or it.get("not_applicable"):
            continue
        if it["requires_evidence"]:
            data = {"checklist_item_id": it["id"], "latitude": "33.45", "longitude": "-112.07"}
            if it.get("evidence_category"):
                data["category"] = it["evidence_category"]
            tec.post(f"/projects/{pid}/evidence", data=data,
                     files={"file": ("foto.jpg", qa.jpeg(it["label"][:24], (70, 110, 90)), "image/jpeg")})
        tec.patch(f"/checklist-items/{it['id']}", json={"is_complete": True})
        hechos += 1


def cerrar(tec, pid: str, cliente: str, serial: str) -> None:
    checklist(tec, pid)
    tec.post(f"/projects/{pid}/equipment", json={"equipment_type": "heat_pump_outdoor", "brand": "Carrier",
                                                 "model": "25HCE4", "serial_number": serial, "quantity": 1,
                                                 "unit_label": "Casa principal"})
    tec.post(f"/projects/{pid}/equipment", json={"equipment_type": "air_handler", "brand": "Carrier",
                                                 "model": "FV4C", "serial_number": serial.replace("HP", "AH"),
                                                 "quantity": 1, "unit_label": "Casa principal"})
    tec.post(f"/projects/{pid}/equipment/confirm")
    tec.post(f"/projects/{pid}/attestation/technician-sign", json={"signature_base64": qa.png_signature()})
    tec.post(f"/projects/{pid}/attestation/customer-sign", json={"signature_base64": qa.png_signature(),
                                                                 "customer_name": cliente})
    tec.post(f"/projects/{pid}/installation/close", json={"observations": "Instalación sin novedad."})


def main() -> int:
    c = {k: qa.Client(k) for k in ("admin", "adm", "vendedor", "tecnico")}
    admin, adm, v, tec = c["admin"], c["adm"], c["vendedor"], c["tecnico"]
    qa.asignar_zona_az(admin, v)
    sello = datetime.now().strftime("%m%d%H%M")
    out = {}

    p = persona(1, "Carmen Ruiz", "4120 W Desert Palms Dr")
    out["formulario"] = vender(v, p, firmar=False, enviar=False)

    p = persona(2, "María González", "4120 W Desert Palms Dr")
    out["revision"] = vender(v, p, firmar=True, enviar=True)

    p = persona(3, "Ana Torres", "2850 N 35th Ave")
    cid = vender(v, p, firmar=True, enviar=True)
    pid = aprobar(adm, admin, cid, f"AZ-AP-{sello}3")
    permiso(adm, pid, f"MEC-{sello}3", aprobado=False)
    materiales(adm, pid)
    out["permiso"] = {"case": cid, "project": pid}

    p = persona(4, "Roberto Sánchez", "1650 W Sunrise Mobile Park")
    cid = vender(v, p, firmar=True, enviar=True)
    pid = aprobar(adm, admin, cid, f"AZ-AP-{sello}4")
    permiso(adm, pid, f"MEC-{sello}4", aprobado=True)
    materiales(adm, pid)
    agendar(adm, tec, pid, 0)
    checklist(tec, pid, hasta=4)
    out["tecnico"] = {"case": cid, "project": pid}

    p = persona(5, "Luis Herrera", "3302 W Palm Ln")
    cid = vender(v, p, firmar=True, enviar=True)
    pid = aprobar(adm, admin, cid, f"AZ-AP-{sello}5")
    permiso(adm, pid, f"MEC-{sello}5", aprobado=True)
    agendar(adm, tec, pid, 0)
    cerrar(tec, pid, p["name"], f"HP{sello}5")
    out["acta"] = {"case": cid, "project": pid}

    p = persona(6, "Patricia Gómez", "915 E Cactus Rd")
    cid = vender(v, p, firmar=True, enviar=True)
    pid = aprobar(adm, admin, cid, f"AZ-AP-{sello}6")
    permiso(adm, pid, f"MEC-{sello}6", aprobado=True)
    agendar(adm, tec, pid, 0)
    cerrar(tec, pid, p["name"], f"HP{sello}6")
    adm.post(f"/projects/{pid}/review/confirm", json={})
    ins = adm.post(f"/projects/{pid}/inspections", json={
        "scheduled_for": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "inspector_name": "J. Ramírez"}).json()
    adm.post(f"/inspections/{ins['id']}/signed-permit", files={"file": ("permiso.jpg", qa.jpeg("Permiso firmado"), "image/jpeg")})
    adm.post(f"/inspections/{ins['id']}/result", json={"result": "passed"})
    out["cobro"] = {"case": cid, "project": pid}

    json.dump(out, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
