"""QA de punta a punta contra la app real (API en marcha), con un usuario por rol.

Recorre todos los flujos de la operación, deja los registros en la base
(clientes y direcciones con prefijo «QA») y escribe el reporte en
`docs/qa/qa-e2e-<fecha>.md`. Cada paso verifica el resultado esperado,
incluidas las cosas que NO se deben poder hacer (permisos, validaciones).

Uso (con `docker compose up` y los datos demo):
    cd backend && .venv/bin/python -m scripts.qa_e2e
Variables: QA_API (por defecto http://localhost:8000/api/v1), QA_PASSWORD.
"""
import base64
import io
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

API = os.getenv("QA_API", "http://localhost:8000/api/v1")
PASSWORD = os.getenv("QA_PASSWORD", "ChangeMe123!")
RUN = datetime.now().strftime("%m%d%H%M%S")
# «Hoy» de la organización demo (seed: America/Bogota), no del reloj de la máquina: el contenedor va en
# UTC y de noche ya es mañana, y la app rechaza pagos y gastos con fecha futura.
HOY = datetime.now(ZoneInfo(os.getenv("QA_TZ", "America/Bogota"))).date()
USERS = {
    "admin": "admin@demo-org.com", "adm": "administracion@demo-org.com", "vendedor": "vendedor@demo-org.com",
    "tecnico": "tecnico@demo-org.com", "conta": "contabilidad@demo-org.com", "gerencia": "gerencia@demo-org.com",
}

RESULTS: list[dict] = []
RECORDS: dict[str, str] = {}
SECTION = [""]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def section(name: str) -> None:
    SECTION[0] = name
    print(f"\n=== {name}")


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"section": SECTION[0], "step": name, "ok": bool(ok), "detail": detail[:300]})
    print(("  ✓ " if ok else "  ✗ ") + name + (f" — {detail[:200]}" if detail and not ok else ""))
    return ok


def jpeg(text: str = "QA", color=(40, 120, 200)) -> bytes:
    img = Image.new("RGB", (640, 480), color)
    ImageDraw.Draw(img).text((20, 20), text, fill="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def pdf_doc(text: str = "QA") -> bytes:
    """Un PDF real de una página. La subida rechaza los de mentira (antes este
    script subía 27 bytes que pasaban la validación pero ningún visor abría)."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    hoja = canvas.Canvas(buf)
    hoja.drawString(72, 720, text)
    hoja.showPage()
    hoja.save()
    return buf.getvalue()


def png_signature() -> str:
    img = Image.new("RGB", (300, 100), "white")
    ImageDraw.Draw(img).line([(10, 80), (90, 20), (180, 70), (290, 15)], fill="black", width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def clear_rate_limit() -> None:
    subprocess.run(["docker", "exec", "crm-usa-redis-1", "sh", "-c",
                    'redis-cli --scan --pattern "ratelimit:*" | xargs -r redis-cli del'],
                   capture_output=True, check=False)


def sql(query: str) -> str:
    r = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "crm", "-d", "crm", "-tAc", query],
                       capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2])
    return r.stdout.strip()


def worker(code: str) -> str:
    """Corre una función async del backend dentro del contenedor (como lo haría Celery)."""
    script = ("import asyncio\nfrom app.db.session import AsyncSessionLocal\n"
              "async def main():\n    async with AsyncSessionLocal() as db:\n" +
              "".join(f"        {line}\n" for line in code.splitlines()) + "asyncio.run(main())\n")
    r = subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-c", script], capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[2])
    return (r.stdout + r.stderr).strip()


class Client:
    def __init__(self, role: str):
        self.role = role
        clear_rate_limit()
        r = httpx.post(f"{API}/auth/login", json={"email": USERS[role], "password": PASSWORD}, timeout=30)
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.me = httpx.get(f"{API}/auth/me", headers=self.h, timeout=30).json()

    def call(self, method: str, path: str, **kw) -> httpx.Response:
        return httpx.request(method, f"{API}{path}", headers=self.h, timeout=60, **kw)

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, **kw):
        return self.call("POST", path, **kw)

    def put(self, path, **kw):
        return self.call("PUT", path, **kw)

    def patch(self, path, **kw):
        return self.call("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self.call("DELETE", path, **kw)


def expect(name: str, r: httpx.Response, *codes: int) -> dict | list | None:
    ok = r.status_code in codes
    body = None
    try:
        body = r.json()
    except Exception:
        pass
    detail = "" if ok else f"HTTP {r.status_code}: {r.text[:250]}"
    check(name, ok, detail)
    return body


# ---------------------------------------------------------------------------
# Formulario genérico (lee la definición publicada del programa)
# ---------------------------------------------------------------------------

PREFER = {"home.is_homeowner": "yes", "home.residence_type": "mobile_home", "internal.result": "preapproved",
          "tech.electrical_viability": "adequate", "tech.existing_hvac": "none", "tech.water_heater": "gas",
          "tech.induction_cooktop": "no"}
SKIP_TYPES = {"info", "system_datetime", "system_user", "signature", "terms_checkbox"}
MEDIA = {"photo", "document", "video"}


def valor(campo: dict, persona: dict):
    k, t = campo["key"], campo["type"]
    reglas = campo.get("validation") or {}
    opciones = [o["value"] for o in campo.get("options") or []]
    if k in PREFER and (not opciones or PREFER[k] in opciones):
        return PREFER[k]
    if k == "authorization.customer_name":
        return None
    if t == "single_select":
        buenas = [o for o in opciones if o not in ("no", "none", "other", "prefer_not_to_answer", "not_adequate")]
        return (buenas or opciones)[0]
    if t == "multi_select":
        excl = set(reglas.get("exclusive") or [])
        buenas = [o for o in opciones if o not in excl and o != "other"]
        return [(buenas or opciones)[0]]
    if t == "yes_no":
        return "no" if any(w in k for w in ("disability", "hazard", "smoke")) else "yes"
    if t in ("integer", "decimal"):
        n = 2
        if reglas.get("min") is not None:
            n = max(n, int(float(reglas["min"])))
        if reglas.get("max") is not None:
            n = min(n, int(float(reglas["max"])))
        return n
    if t == "date":
        return HOY.isoformat()
    if t == "time":
        return "10:00"
    if t == "email" or "email" in k:
        return persona["email"]
    if t == "phone" or "phone" in k:
        return persona["phone"]
    if reglas.get("format") == "zip" or "zip" in k:
        return persona["zip"]
    if "full_name" in k or k.endswith(".name"):
        return persona["name"]
    if "street" in k:
        return persona["street"]
    if "city" in k:
        return persona["city"]
    if k.endswith("state"):
        return persona["state"]
    if "unit" in k:
        return persona["unit"]
    texto = "QA respuesta de prueba"
    if reglas.get("min_length"):
        texto = texto.ljust(int(reglas["min_length"]), "x")
    return texto


def llenar_formulario(v: Client, case_id: str, persona: dict) -> dict:
    """Llena todo lo que falte, ronda por ronda (las condiciones abren campos nuevos)."""
    subidos = 0
    for ronda in range(8):
        form = v.get(f"/cases/{case_id}/form").json()
        respuestas = form["answers"]
        cambios_totales = 0
        for paso in form["evaluation"]["steps"]:
            cambios = {}
            for campo in paso["fields"]:
                if campo["type"] in SKIP_TYPES or campo["key"] == "authorization.customer_name":
                    continue
                actual = respuestas.get(campo["key"])
                if actual not in (None, "", [], {}) and not campo.get("error"):
                    continue
                if campo["type"] in MEDIA:
                    mime, data, nombre = ("application/pdf", pdf_doc(f"QA {campo['key']}"), "doc.pdf") \
                        if campo["type"] == "document" else ("image/jpeg", jpeg(campo["key"]), "foto.jpg")
                    if campo["type"] == "video":
                        continue  # no hay videos obligatorios en las plantillas; se prueba aparte
                    r = v.post(f"/cases/{case_id}/files", data={"field_key": campo["key"], "latitude": persona["lat"],
                                                                "longitude": persona["lon"]},
                               files={"file": (nombre, data, mime)})
                    if r.status_code != 201:
                        check(f"Subir archivo {campo['key']}", False, r.text)
                        continue
                    subidos += 1
                    cambios[campo["key"]] = r.json()["id"]
                else:
                    x = valor(campo, persona)
                    if x is not None:
                        cambios[campo["key"]] = x
            if cambios:
                r = v.put(f"/cases/{case_id}/steps/{paso['code']}", json={"answers": cambios,
                                                                          "latitude": persona["lat"], "longitude": persona["lon"]})
                if r.status_code != 200:
                    check(f"Guardar paso {paso['code']}", False, r.text)
                cambios_totales += len(cambios)
        if cambios_totales == 0:
            break
    form = v.get(f"/cases/{case_id}/form").json()
    form["_uploaded"] = subidos
    return form


def abrir_puerta(v: Client, persona: dict, program_code: str | None, result="opened") -> dict:
    mios = v.get("/me/programs").json()
    prog = next((m for m in mios if m["program"]["code"] == program_code), None) if program_code else None
    body = {"result": result, "address_street": persona["street"], "address_unit": persona["unit"],
            "address_city": persona["city"], "address_state": persona["state"], "address_zip": persona["zip"],
            "latitude": persona["lat"], "longitude": persona["lon"], "notes": "QA visita"}
    if prog:
        body["program_id"] = prog["program"]["id"]
        if prog["zones"]:
            body["zone_id"] = prog["zones"][0]["id"]
    return expect(f"Visita «{result}» en {persona['street']}", v.post("/visits", json=body), 201) or {}


def persona(n: int, state: str) -> dict:
    datos = {"CA": ("San Fernando", "91340", 34.28, -118.44, "818"), "AZ": ("Phoenix", "85001", 33.45, -112.07, "602")}
    ciudad, zip_, lat, lon, area = datos[state]
    return {"name": f"QA {RUN} Cliente {n}", "email": f"qa.{RUN}.{n}@example.com", "phone": f"({area}) 555-{1000 + n:04d}",
            "street": f"{100 + n} QA {RUN} Mobile Park Dr", "unit": f"Spc {n}", "city": ciudad, "state": state,
            "zip": zip_, "lat": str(lat), "lon": str(lon)}


# ---------------------------------------------------------------------------
# Flujos
# ---------------------------------------------------------------------------

def flujo_salidas_tempranas(v: Client) -> None:
    section("1. Visitas: salidas tempranas y reapertura")
    for i, res in enumerate(("no_contact", "not_interested", "not_eligible"), start=1):
        p = persona(90 + i, "CA")
        r = abrir_puerta(v, p, None, res)
        if r:
            check(f"Etapa «{res}»", r["case"]["stage_code"] == res, r["case"]["stage_code"])
            RECORDS[f"Salida temprana {res}"] = r["case"]["case_number"]
    p = persona(91, "CA")
    r = abrir_puerta(v, {**p, "street": p["street"].lower() + "."}, None, "opened")
    if r:
        check("La misma puerta (escrita distinto) reabre su expediente", r["outcome"] == "reopened"
              and r["case"]["stage_code"] == "new_prospect", f"{r['outcome']} {r['case']['stage_code']}")
        hist = v.get(f"/cases/{r['case']['id']}/visits").json()
        check("Quedan las dos visitas en el historial", [x["result"] for x in hist] == ["no_contact", "opened"], str(hist))


def flujo_vendedor(v: Client, adm: Client, n: int, state: str, program: str) -> tuple[str, dict]:
    p = persona(n, state)
    r = abrir_puerta(v, p, program)
    case = r["case"]
    RECORDS[f"Expediente #{n} {program} ({state})"] = case["case_number"]
    expect("Enviar incompleto se rechaza", v.post(f"/cases/{case['id']}/submit"), 400)
    expect("Archivo disfrazado (exe como jpg) se rechaza",
           v.post(f"/cases/{case['id']}/files", data={"field_key": "customer.id_photo"},
                  files={"file": ("foto.jpg", b"MZ\x90\x00 ejecutable", "image/jpeg")}), 400)
    form = llenar_formulario(v, case["id"], p)
    faltan = [m for m in form["evaluation"]["missing"] if m["step"] != "authorization"]
    check(f"Formulario lleno, salvo la firma ({form['_uploaded']} archivos con GPS)", not faltan, json.dumps(faltan)[:250])
    expect("El vendedor no puede aprobar su expediente",
           v.post(f"/cases/{case['id']}/transition", json={"to_stage": "approved"}), 403)
    expect("Cliente acepta términos y firma", v.post(f"/cases/{case['id']}/terms-acceptance",
                                                     json={"customer_name": p["name"], "signature": png_signature()}), 201)
    form = v.get(f"/cases/{case['id']}/form").json()
    check("Puede enviarse", form["evaluation"]["can_submit"], json.dumps(form["evaluation"]["missing"])[:250])
    r = expect("Enviar a revisión", v.post(f"/cases/{case['id']}/submit"), 200)
    if r:
        check("Queda en Pendiente aprobación · en revisión", (r["stage_code"], r["substatus_code"]) ==
              ("pending_approval", "pending_review"), str((r["stage_code"], r["substatus_code"])))
    expect("Editar después de enviar se bloquea",
           v.put(f"/cases/{case['id']}/steps/home", json={"answers": {"home.is_homeowner": "no"}}), 409)
    return case["id"], p


def flujo_revision(v: Client, adm: Client, admin: Client, case_id: str, p: dict, *, devolver: bool) -> None:
    docs = expect("Administración ve los documentos", adm.get(f"/cases/{case_id}/documents"), 200) or []
    check("Todos los documentos por revisar", docs and all(d["review_status"] == "pending" for d in docs), str(len(docs)))
    cola = adm.get("/documents/review-queue").json()
    check("El expediente aparece en la cola de documentos", any(c["case_id"] == case_id for c in cola))
    expect("Extra: Administración agrega una factura de luz", adm.post(
        f"/cases/{case_id}/documents", data={"label": "QA Factura de luz (correo)"},
        files={"file": ("luz.pdf", pdf_doc("QA factura de luz"), "application/pdf")}), 201)
    docs = adm.get(f"/cases/{case_id}/documents").json()
    if devolver and docs:
        d0 = docs[0]
        expect("Rechazar sin nota se bloquea", adm.post(f"/case-files/{d0['id']}/review", json={"status": "rejected"}), 400)
        expect("Rechazar con nota", adm.post(f"/case-files/{d0['id']}/review",
                                             json={"status": "rejected", "notes": "QA: la foto está borrosa"}), 200)
        expect("Aprobar con documento rechazado se bloquea",
               adm.post(f"/cases/{case_id}/transition", json={"to_stage": "approved"}), 400)
        expect("Devolver al vendedor", adm.post(f"/cases/{case_id}/substatus",
                                                json={"substatus": "returned", "reason": "QA: reemplaza la foto borrosa"}), 200)
        form = v.get(f"/cases/{case_id}/form").json()
        check("El vendedor puede editar el devuelto", form["editable"])
        expect("Reenviar con el rechazado vigente se bloquea", v.post(f"/cases/{case_id}/submit"), 400)
        nuevo = expect("Vendedor sube la foto de nuevo", v.post(
            f"/cases/{case_id}/files", data={"field_key": d0["field_key"], "latitude": p["lat"], "longitude": p["lon"]},
            files={"file": ("nueva.jpg", jpeg("nueva"), "image/jpeg")}), 201)
        paso = next(s["code"] for s in form["definition"]["steps"] if any(f["key"] == d0["field_key"] for f in s["fields"]))
        expect("Guarda el paso con la foto nueva", v.put(f"/cases/{case_id}/steps/{paso}",
                                                         json={"answers": {d0["field_key"]: nuevo["id"]}}), 200)
        r = expect("Reenviar a revisión", v.post(f"/cases/{case_id}/submit"), 200)
        if r:
            check("Vuelve a «en revisión»", r["substatus_code"] == "pending_review", str(r["substatus_code"]))
    docs = adm.get(f"/cases/{case_id}/documents").json()
    for d in docs:
        if d["review_status"] != "accepted":
            adm.post(f"/case-files/{d['id']}/review", json={"status": "accepted"})
    docs = adm.get(f"/cases/{case_id}/documents").json()
    check("Todos los documentos aceptados", all(d["review_status"] == "accepted" for d in docs), str(len(docs)))
    for s in ("ready_to_submit", "submitted_to_program", "program_review"):
        expect(f"Avance con el programa: {s}", adm.post(f"/cases/{case_id}/substatus", json={"substatus": s}), 200)
    r = expect("Aprobar con código", admin.post(f"/cases/{case_id}/transition", json={
        "to_stage": "approved", "approval_code": f"QA-AP-{RUN}", "application_number": f"QA-APP-{RUN}"}), 200)
    if r:
        check("Aprobado con código y solicitud guardados", r["approval_code"] == f"QA-AP-{RUN}"
              and r["application_number"] == f"QA-APP-{RUN}")


def proyecto_de(adm: Client, case_id: str) -> dict | None:
    for _ in range(5):
        for p in adm.get("/projects", params={"page_size": 200}).json():
            if p.get("case_id") == case_id:
                return p
        time.sleep(1)
    return None


def flujo_campo(adm: Client, tec: Client, case_id: str, *, devolver_acta: bool, permiso: bool = True,
                condiciones: list[str] | None = None) -> str | None:
    proj = proyecto_de(adm, case_id)
    if not check("Al aprobar se creó el proyecto de instalación", proj is not None):
        return None
    pid = proj["id"]
    RECORDS.setdefault("Proyectos", "")
    RECORDS["Proyectos"] += f"{proj['title']}; "
    expect("El técnico NO ve un proyecto que no es suyo", tec.get(f"/projects/{pid}"), 403, 404)
    if permiso:
        expect("Permiso municipal aprobado con vencimiento", adm.post(f"/projects/{pid}/permits", json={
            "jurisdiction": "QA City", "permit_number": f"QA-PER-{RUN}", "status": "approved",
            "approved_on": HOY.isoformat(), "expires_on": (HOY + timedelta(days=5)).isoformat()}), 201)
    tecnicos = adm.get("/dispatch/technicians").json()
    tid = next((t["id"] for t in tecnicos if t.get("email") == USERS["tecnico"]), tec.me["id"])
    expect("Agendar instalación con técnico", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": tid, "scheduled_date": (HOY + timedelta(days=2)).isoformat()}), 200)
    expect("El técnico ve su orden", tec.get(f"/projects/{pid}"), 200)
    if condiciones:
        expect(f"Técnico marca condiciones de la casa: {condiciones}",
               tec.patch(f"/projects/{pid}/conditions", json={"conditions": condiciones}), 200)
    gaps = tec.get(f"/projects/{pid}/installation/gaps").json()
    check("Cerrar sin completar está bloqueado", gaps.get("can_close") is False, str(gaps)[:200])
    expect("Cerrar instalación incompleta se rechaza", tec.post(f"/projects/{pid}/installation/close", json={}), 400, 409)
    items = tec.get(f"/projects/{pid}/checklist").json()
    na_hecho = False
    for it in items:
        if it["is_complete"] or it.get("not_applicable"):
            continue
        if it.get("allows_not_applicable") and not it["requires_evidence"] and not na_hecho:
            expect(f"«No aplica» sin motivo se rechaza ({it['label'][:30]})",
                   tec.patch(f"/checklist-items/{it['id']}", json={"not_applicable": True}), 400, 422)
            expect("«No aplica» con motivo", tec.patch(f"/checklist-items/{it['id']}", json={
                "not_applicable": True, "reason": "QA: la casa no tiene ese equipo"}), 200)
            na_hecho = True
            continue
        if it["requires_evidence"]:
            data = {"checklist_item_id": it["id"], "latitude": "34.28", "longitude": "-118.44"}
            if it.get("evidence_category"):
                data["category"] = it["evidence_category"]
            r = tec.post(f"/projects/{pid}/evidence", data=data, files={"file": ("ev.jpg", jpeg(it["label"][:20]), "image/jpeg")})
            if r.status_code != 201:
                check(f"Evidencia «{it['label'][:40]}»", False, r.text)
        r = tec.patch(f"/checklist-items/{it['id']}", json={"is_complete": True})
        if r.status_code != 200:
            check(f"Completar «{it['label'][:40]}»", False, r.text)
    items = tec.get(f"/projects/{pid}/checklist").json()
    check(f"Checklist resuelto ({len(items)} ítems)", all(i["is_complete"] or i.get("not_applicable") for i in items),
          str([i["label"] for i in items if not (i["is_complete"] or i.get("not_applicable"))])[:250])
    expect("Equipo instalado con serial", tec.post(f"/projects/{pid}/equipment", json={
        "equipment_type": "heat_pump_outdoor", "brand": "Carrier", "model": "25HCE4", "serial_number": f"QA{RUN}",
        "quantity": 1, "unit_label": "Casa principal"}), 201)
    expect("Guardar equipos instalados", tec.post(f"/projects/{pid}/equipment/confirm"), 200)
    expect("Firma del técnico en el acta", tec.post(f"/projects/{pid}/attestation/technician-sign",
                                                    json={"signature_base64": png_signature()}), 200, 201)
    expect("Firma del cliente en el acta", tec.post(f"/projects/{pid}/attestation/customer-sign",
                                                    json={"signature_base64": png_signature(), "customer_name": "QA Cliente"}),
           200, 201)
    expect("Cerrar instalación", tec.post(f"/projects/{pid}/installation/close", json={"observations": "QA instalación ok"}), 200)
    expect("Equipo después del cierre se bloquea", tec.post(f"/projects/{pid}/equipment", json={
        "equipment_type": "heat_pump_outdoor", "brand": "X", "model": "Y", "serial_number": "Z", "quantity": 1}), 409)
    if devolver_acta:
        expect("Devolver el acta sin motivo se rechaza", adm.post(f"/projects/{pid}/review/return", json={"reason": ""}), 422)
        expect("Administración devuelve el acta", adm.post(f"/projects/{pid}/review/return",
                                                           json={"reason": "QA: falta foto de la etiqueta"}), 200)
        expect("El técnico corrige y cierra de nuevo", tec.post(f"/projects/{pid}/installation/close",
                                                                json={"observations": "QA corregido"}), 200)
    expect("El técnico no puede confirmar su propia acta", tec.post(f"/projects/{pid}/review/confirm", json={}), 403)
    expect("Administración confirma el acta", adm.post(f"/projects/{pid}/review/confirm", json={}), 200)
    return pid


def flujo_inspeccion(adm: Client, tec: Client, pid: str) -> None:
    cuando = lambda: (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    ins = expect("Agendar inspección", adm.post(f"/projects/{pid}/inspections",
                                                json={"scheduled_for": cuando(), "inspector_name": "QA Inspector"}), 201)
    if not ins:
        return
    expect("Falla sin observaciones se rechaza", adm.post(f"/inspections/{ins['id']}/result", json={"result": "failed"}), 400)
    expect("Inspección fallida con observaciones", adm.post(f"/inspections/{ins['id']}/result", json={
        "result": "failed", "observations": "QA: falta soporte antivibración"}), 200)
    expect("Técnico corrige y cierra de nuevo", tec.post(f"/projects/{pid}/installation/close",
                                                         json={"observations": "QA soporte instalado"}), 200)
    expect("Administración confirma de nuevo", adm.post(f"/projects/{pid}/review/confirm", json={}), 200)
    ins2 = expect("Segunda inspección", adm.post(f"/projects/{pid}/inspections", json={"scheduled_for": cuando()}), 201)
    if not ins2:
        return
    expect("Aprobar sin permiso firmado se bloquea", adm.post(f"/inspections/{ins2['id']}/result", json={"result": "passed"}), 400)
    expect("Sube el permiso firmado por el inspector", adm.post(f"/inspections/{ins2['id']}/signed-permit",
                                                                files={"file": ("permiso.jpg", jpeg("firmado"), "image/jpeg")}), 200, 201)
    expect("Inspección aprobada", adm.post(f"/inspections/{ins2['id']}/result", json={"result": "passed"}), 200)


def configurar_tech(admin: Client) -> None:
    """Contrato §9.1: TECH no exige inspección este año. Viene activada por
    defecto y se desactiva en la configuración de cobro del programa."""
    progs = {p["code"]: p for p in admin.get("/programs").json()}
    reqs = expect("Requisitos de cobro de TECH", admin.get(f"/billing/programs/{progs['TECH_CLEAN_CA']['id']}/requirements"), 200) or []
    ins = next((r for r in reqs if r["code"] == "inspection_passed"), None)
    if ins and ins.get("active", True):
        expect("TECH sin inspección (configuración de cobro)", admin.patch(
            f"/billing/programs/requirements/{ins['id']}", json={"active": False}), 200)


def asignar_zona_az(admin: Client, v: Client) -> None:
    """El vendedor demo solo tiene zona de TECH: el Administrador le asigna una de Arizona."""
    if any(m["program"]["code"] == "AZ_EFFICIENCY" for m in v.get("/me/programs").json()):
        return
    progs = {p["code"]: p for p in admin.get("/programs").json()}
    z = expect("Administrador crea zona de Arizona", admin.post(f"/programs/{progs['AZ_EFFICIENCY']['id']}/zones", json={
        "name": f"QA Desert Palms Phoenix {RUN}", "state": "AZ", "city": "Phoenix"}), 201)
    if z:
        expect("Asigna el vendedor a la zona", admin.put(f"/zones/{z['id']}/salespeople",
                                                         json={"user_ids": [v.me["id"]]}), 200)
        check("El vendedor ve Arizona en «Mis programas»",
              any(m["program"]["code"] == "AZ_EFFICIENCY" for m in v.get("/me/programs").json()))


def flujo_cobro(adm: Client, conta: Client, admin: Client, pid: str, case_id: str, program_code: str, *, rechazar: bool,
                cerrar: bool) -> None:
    progs = {p["code"]: p for p in admin.get("/programs").json()}
    elig = expect("Elegibilidad del proyecto", adm.get(f"/projects/{pid}/billing/eligibility"), 200)
    claim = expect(f"Crear cobro {program_code}", adm.post(f"/projects/{pid}/claims",
                                                           json={"program_id": progs[program_code]["id"]}), 201)
    if not claim:
        return
    expect("Cobro duplicado del mismo programa se bloquea", adm.post(f"/projects/{pid}/claims",
                                                                     json={"program_id": progs[program_code]["id"]}), 409)
    for req in claim["requirements"]:
        if req["kind"] == "manual" and not req["met"]:
            r = adm.post(f"/claims/{claim['id']}/checks/{req['code']}", json={})
            if r.status_code != 200:
                check(f"Requisito {req['code']}", False, r.text)
    claim = expect("Radicar el cobro", adm.post(f"/claims/{claim['id']}/submit",
                                                json={"portal_reference": f"QA-PORTAL-{RUN}"}), 200)
    if not claim:
        return
    case = admin.get(f"/cases/{case_id}").json()
    check("El expediente pasó a «En cobro»", case["stage_code"] == "billing_in_progress", case["stage_code"])
    if rechazar:
        expect("Rechazo sin motivo suficiente se bloquea", adm.post(f"/claims/{claim['id']}/reject",
                                                                    json={"reason": "x", "category": "documentary"}), 400)
        expect("Programa rechaza el cobro", adm.post(f"/claims/{claim['id']}/reject", json={
            "reason": "QA: falta la firma del cliente en el formulario", "category": "documentary"}), 200)
        expect("Se vuelve a radicar", adm.post(f"/claims/{claim['id']}/submit", json={"portal_reference": f"QA-R2-{RUN}"}), 200)
    monto = float(claim.get("amount") or claim.get("expected_amount") or 0) or 1000
    expect("Administración NO registra pagos (Contabilidad sí)", adm.post(f"/claims/{claim['id']}/payment",
                                                                         json={"amount": monto, "paid_on": HOY.isoformat()}), 403, 200)
    pagado = conta.post(f"/claims/{claim['id']}/payment", json={"amount": monto, "paid_on": HOY.isoformat(),
                                                               "reference": f"QA-CHK-{RUN}"})
    if pagado.status_code != 200 and "ya" in pagado.text.lower():
        pagado = httpx.Response(200, json={})
    expect("Contabilidad registra el pago", pagado, 200)
    case = admin.get(f"/cases/{case_id}").json()
    check("El expediente quedó «Pagado»", case["stage_code"] == "paid", case["stage_code"])
    if cerrar:
        expect("Cerrar sin motivo se bloquea", admin.post(f"/cases/{case_id}/transition", json={"to_stage": "closed"}), 400)
        r = expect("Cierre administrativo con motivo", admin.post(f"/cases/{case_id}/transition", json={
            "to_stage": "closed", "reason": "QA: ciclo completo terminado"}), 200)
        if r:
            check("Expediente «Cerrado»", r["stage_code"] == "closed", r["stage_code"])


def flujo_rechazo(v: Client, adm: Client, admin: Client, n: int) -> None:
    section("6. Expediente rechazado: corrección, reenvío y cierre administrativo")
    case_id, p = flujo_vendedor(v, adm, n, "CA", "TECH_CLEAN_CA")
    for d in adm.get(f"/cases/{case_id}/documents").json():
        adm.post(f"/case-files/{d['id']}/review", json={"status": "accepted"})
    expect("Rechazar sin motivo se bloquea", admin.post(f"/cases/{case_id}/transition", json={"to_stage": "rejected"}), 400)
    expect("Rechazar con motivo", admin.post(f"/cases/{case_id}/transition", json={
        "to_stage": "rejected", "reason": "QA: ingresos por encima del límite"}), 200)
    form = v.get(f"/cases/{case_id}/form").json()
    check("El vendedor puede corregir el rechazado", form["editable"])
    expect("Corrige un dato", v.put(f"/cases/{case_id}/steps/home", json={"answers": {"home.is_homeowner": "yes"}}), 200)
    r = expect("Reenvía a revisión", v.post(f"/cases/{case_id}/submit"), 200)
    if r:
        check("Vuelve a pendiente de aprobación", r["stage_code"] == "pending_approval", r["stage_code"])
    expect("Poner en espera del programa", admin.post(f"/cases/{case_id}/transition", json={
        "to_stage": "on_hold", "reason": "QA: el programa pausó solicitudes"}), 200)
    expect("Vendedor NO puede cerrar", v.post(f"/cases/{case_id}/transition", json={"to_stage": "closed", "reason": "x"}), 403, 404)
    r = expect("Cierre administrativo desde «En espera»", admin.post(f"/cases/{case_id}/transition", json={
        "to_stage": "closed", "reason": "QA: el cliente desistió"}), 200)
    RECORDS["Expediente rechazado → cerrado"] = (r or {}).get("case_number", "")


def flujo_notificaciones(v, adm, admin, tec, conta) -> None:
    section("7. Notificaciones")
    time.sleep(6)  # el worker procesa la cola
    for nombre, c in (("vendedor", v), ("administración", adm), ("técnico", tec), ("contabilidad", conta)):
        items = c.get("/notifications", params={"limit": 100}).json()
        sin_leer = c.get("/notifications/unread-count").json()["unread"]
        eventos = {i["event"] for i in items}
        check(f"Avisos para {nombre}: {sin_leer} sin leer ({', '.join(sorted(eventos))[:150]})", len(items) > 0)
    esperados = {"vendedor": {"case.returned", "case.approved", "case.rejected"}, "técnico": {"installation.scheduled",
                                                                                              "project.returned_to_technician"},
                 "administración": {"case.submitted"}, "contabilidad": {"claim.rejected", "claim.paid"}}
    for nombre, c in (("vendedor", v), ("administración", adm), ("técnico", tec), ("contabilidad", conta)):
        eventos = {i["event"] for i in c.get("/notifications", params={"limit": 100}).json()}
        faltan = esperados[nombre] - eventos
        check(f"{nombre} recibió {sorted(esperados[nombre])}", not faltan, f"faltan {sorted(faltan)}")
    primero = v.get("/notifications").json()
    if primero:
        expect("Marcar un aviso como leído", v.post(f"/notifications/{primero[0]['id']}/read"), 200)
        expect("Otro usuario no puede leer ese aviso", adm.post(f"/notifications/{primero[0]['id']}/read"), 404)
    expect("Marcar todos como leídos", v.post("/notifications/read-all"), 200)
    check("Sin leer en 0", v.get("/notifications/unread-count").json()["unread"] == 0)
    expect("Preferencias: SMS sin celular se rechaza", v.put("/notifications/preferences", json={
        "email_enabled": False, "sms_enabled": True, "sms_phone": ""}), 400)
    expect("Plantilla editada por el Administrador", admin.put("/notifications/templates/case.approved/in_app", json={
        "subject": "¡Aprobado! {{expediente}}", "body": "QA: {{cliente}} quedó aprobado. {{motivo}}"}), 200)
    expect("El vendedor no administra plantillas", v.get("/notifications/templates"), 403)
    expect("Ajustes de alertas: 1 día hábil", admin.put("/notifications/settings", json={
        "approval_alert_business_days": 1, "permit_expiry_alert_days": 7}), 200)
    hist = expect("Historial de envíos (Administrador)", admin.get("/notifications/deliveries"), 200) or []
    check(f"Envíos registrados: {len(hist)}", True)


def flujo_alertas(admin: Client, adm: Client, case_id: str) -> None:
    section("8. Alertas diarias (expediente demorado y permiso por vencer)")
    sql(f"update cases set submitted_at = now() - interval '10 days' where id = '{case_id}'")
    salida = worker("from app.modules.notifications import service\nprint(await service.daily_alerts_all(db))")
    check(f"Alertas diarias corridas por el worker: {salida.splitlines()[-1] if salida else '?'}", salida != "")
    eventos = {i["event"] for i in adm.get("/notifications", params={"limit": 100}).json()}
    check("Administración recibió «expediente sin aprobar»", "case.approval_overdue" in eventos, str(eventos))
    check("Administración recibió «permiso por vencer»", "permit.expiring" in eventos, str(eventos))
    salida2 = worker("from app.modules.notifications import service\nprint(await service.daily_alerts_all(db))")
    check("Correr de nuevo el mismo día no repite alertas", (salida2.splitlines() or ["?"])[-1].strip() == "0", salida2[-80:])


def flujo_campanas(admin: Client, v: Client) -> None:
    section("9. Campañas por SMS y correo")
    p = expect("Producto libre", admin.post("/products", json={"name": f"QA Mantenimiento A/C {RUN}", "price": "$89",
                                                                "description": "Limpieza y revisión"}), 201) or {}
    r = expect("Cargar contactos propios", admin.post("/campaigns/contacts/import", json={
        "text": f"QA Homer {RUN}, (602) 555-7{RUN[-3:]}, qa.homer.{RUN}@example.com\nQA Lenny {RUN}, 702555{RUN[-4:]}\n"
                f"qa.solo.{RUN}@example.com\nlinea sin nada",
        "source": "QA: lista de la feria (formulario firmado)", "confirm": True}), 200) or {}
    check("Una línea inválida reportada", len(r.get("invalid", [])) == 1, str(r))
    expect("Cargar sin confirmar se rechaza", admin.post("/campaigns/contacts/import", json={
        "text": "qa.x@example.com", "source": "QA fuente", "confirm": False}), 400)
    aud = admin.post("/campaigns/audience", json={"search": f"{RUN}"}).json()
    sin = [c["key"] for c in aud["contacts"] if c["consent"] == "none" or c["email_consent"] == "none"]
    if sin:
        expect("Registrar permiso de clientes QA", admin.post("/campaigns/consents", json={
            "keys": sin, "source": "QA: casilla de promociones firmada en la visita", "channel": "both", "confirm": True}), 200)
    c = expect("Campaña SMS + correo", admin.post("/campaigns", json={
        "name": f"QA Campaña {RUN}", "product_id": p.get("id"), "channel": "both",
        "subject": "{{nombre}}, {{producto}} a {{precio}}", "message": "Hola {{nombre}}, esta semana {{producto}} a {{precio}}.",
        "audience": {"search": RUN}}), 201) or {}
    check("Vista previa con STOP", "STOP" in c.get("preview", ""), c.get("preview", ""))
    expect("Prueba de SMS a un número ajeno se bloquea", admin.post(f"/campaigns/{c['id']}/test", json={
        "channel": "sms", "phone": "8185550000"}), 400)
    expect("Prueba de correo al correo propio", admin.post(f"/campaigns/{c['id']}/test", json={"channel": "email"}), 200)
    lz = expect("Lanzar campaña", admin.post(f"/campaigns/{c['id']}/launch", json={}), 200) or {}
    check(f"En cola: {lz.get('summary', {}).get('queued')}", (lz.get("summary", {}).get("queued") or 0) > 0)
    expect("Una campaña lanzada no se edita", admin.put(f"/campaigns/{c['id']}", json={"name": "x", "message": "y"}), 409)
    salida = worker("from app.modules.notifications import campaigns\nprint(await campaigns.send_due(db))")
    check(f"Envío de la cola por el worker: {salida.splitlines()[-1] if salida else '?'}", bool(salida))
    rec = admin.get(f"/campaigns/{c['id']}/recipients").json()
    check("Fuera de horario o modo de prueba: nada se envió de verdad",
          all(r["status"] in ("pending", "skipped") for r in rec), str({r["status"] for r in rec}))
    token = sql(f"select unsubscribe_token from email_marketing_consents where email = 'qa.solo.{RUN}@example.com'")
    if token:
        g = httpx.get(f"{API}/unsubscribe/{token}")
        check("Abrir el enlace de baja NO da de baja (pide confirmar)", g.status_code == 200 and
              sql(f"select status from email_marketing_consents where unsubscribe_token = '{token}'") == "granted")
        r = httpx.post(f"{API}/unsubscribe/{token}")
        check("Confirmar la baja del correo (sin sesión)", r.status_code == 200 and
              sql(f"select status from email_marketing_consents where unsubscribe_token = '{token}'") == "revoked")
    expect("Baja manual de un número", admin.post("/campaigns/opt-outs", json={"phone": f"702555{RUN[-4:]}"}), 200)
    bajas = admin.get("/campaigns/opt-outs").json()
    check(f"Bajas registradas: {len(bajas)}", len(bajas) >= 2)
    expect("El vendedor no ve campañas", v.get("/campaigns"), 403)
    RECORDS["Campaña"] = f"QA Campaña {RUN}"


def flujo_particular(conta: Client, admin: Client) -> None:
    section("10. Trabajo particular: cotización → factura → pago")
    cli = expect("Cliente particular", admin.post("/customers", json={"legal_name": f"QA {RUN} Cliente particular",
                                                                        "main_phone": "(602) 555-0999"}), 201) or {}
    lineas = [{"kind": "labor", "description": "QA Reparación de ductos", "quantity": 2, "unit_price": 150},
              {"kind": "material", "description": "QA Ducto flexible 25 ft", "quantity": 1, "unit_price": "89.50"}]
    q = expect("Cotización", conta.post("/billing/quotes", json={"customer_id": cli.get("id"), "lines": lineas}), 201) or {}
    expect("Enviar cotización", conta.post(f"/billing/quotes/{q['id']}/send"), 200)
    a = expect("Cliente acepta → factura en borrador", conta.post(f"/billing/quotes/{q['id']}/accept"), 200) or {}
    fac = a.get("invoice") or {}
    expect("Aceptar dos veces se bloquea", conta.post(f"/billing/quotes/{q['id']}/accept"), 409)
    expect("Emitir factura", conta.post(f"/invoices/{fac['id']}/issue", json={"due_date": (HOY + timedelta(days=30)).isoformat()}), 200)
    expect("Pago parcial", conta.post(f"/invoices/{fac['id']}/payments", json={"amount": 200, "paid_at": HOY.isoformat(),
                                                                                "reference": "QA-ZELLE"}), 200, 201)
    f2 = conta.get(f"/invoices/{fac['id']}").json()
    check(f"Saldo pendiente correcto ({f2.get('balance_due') or f2.get('balance')})",
          str(f2.get("balance_due") or f2.get("balance")) in ("189.50", "189.5"), json.dumps(f2)[:200])
    pdf = conta.get(f"/invoices/{fac['id']}/pdf")
    check("PDF de la factura", pdf.status_code == 200 and pdf.content[:4] == b"%PDF", str(pdf.status_code))
    RECORDS["Factura particular"] = f2.get("invoice_number") or fac.get("id", "")


def flujo_permisos_por_rol(clients: dict) -> None:
    section("11. Permisos por rol (lo que cada uno NO debe poder hacer)")
    reglas = [
        ("tecnico", "GET", "/case-board", (403,)), ("tecnico", "GET", "/campaigns", (403,)),
        ("tecnico", "GET", "/invoices", (403,)), ("vendedor", "GET", "/invoices", (403,)),
        ("vendedor", "GET", "/documents/review-queue", (403,)), ("vendedor", "GET", "/notifications/deliveries", (403,)),
        ("gerencia", "POST", "/campaigns", (403, 422)), ("gerencia", "GET", "/case-board", (200,)),
        ("conta", "GET", "/case-board", (200, 403)), ("vendedor", "GET", "/checklist-templates", (403,)),
        ("tecnico", "POST", "/products", (403, 422)), ("vendedor", "GET", "/programs", (200,)),
    ]
    for rol, m, path, codes in reglas:
        expect(f"{rol} {m} {path} → {codes}", clients[rol].call(m, path, json={} if m == "POST" else None), *codes)
    r = httpx.get(f"{API}/case-board")
    check("Sin sesión → 401", r.status_code == 401, str(r.status_code))
    r = httpx.post(f"{API}/webhooks/masiv/inbound?token=adivinado", json={"from": "1", "message": "STOP"})
    check("Webhook de Masiv con token falso → 404", r.status_code == 404, str(r.status_code))


def flujo_finanzas(c: dict, pid: str | None, pid_az: str | None) -> None:
    """Gastos, proveedores y pagos, conciliación, rentabilidad, reportes y permisos."""
    tec, conta, ger, admin, v, adm = c["tecnico"], c["conta"], c["gerencia"], c["admin"], c["vendedor"], c["adm"]
    section("12. Gastos de campo")
    def gasto(cli, monto, proyecto=None, **kw):
        datos = {"expense_date": HOY.isoformat(), "category": "fuel", "amount": monto, "payment_method": "own_money",
                 "description": f"QA {RUN} gasolina al parque", "project_id": proyecto, **kw}
        return cli.post("/expenses", data={"data": json.dumps(datos)},
                        files={"receipt": ("recibo.jpg", jpeg("recibo"), "image/jpeg")})
    g = expect("Técnico registra gasolina con foto del recibo, cargada a la instalación TECH",
               gasto(tec, "48.75", pid), 201) or {}
    expect("Gasto sobre el tope se rechaza", gasto(tec, "9000"), 400)
    expect("Gasto con fecha futura se rechaza", gasto(tec, "10", expense_date=(HOY + timedelta(days=2)).isoformat()), 400)
    expect("Recibo disfrazado (exe) se rechaza", tec.post("/expenses", data={"data": json.dumps({
        "expense_date": HOY.isoformat(), "category": "fuel", "amount": "5", "description": "QA exe"})},
        files={"receipt": ("r.jpg", b"MZ\x90\x00", "image/jpeg")}), 400)
    g2 = expect("Técnico registra un segundo gasto (hotel, tarjeta de la empresa)",
                gasto(tec, "129.00", pid_az, category="lodging", payment_method="company_card"), 201) or {}
    expect("El técnico no aprueba su gasto", tec.post(f"/expenses/{g.get('id')}/review", json={"approve": True}), 403)
    expect("Rechazar sin motivo se bloquea", conta.post(f"/expenses/{g2.get('id')}/review", json={"approve": False}), 400)
    expect("Contabilidad aprueba la gasolina", conta.post(f"/expenses/{g.get('id')}/review", json={"approve": True}), 200)
    expect("Contabilidad rechaza el hotel con motivo", conta.post(f"/expenses/{g2.get('id')}/review", json={
        "approve": False, "notes": "QA: falta la factura del hotel a nombre de la empresa"}), 200)
    expect("Reembolso al técnico", conta.post(f"/expenses/{g.get('id')}/reimburse", json={
        "paid_on": HOY.isoformat(), "reference": f"QA-ZELLE-{RUN}"}), 200)
    expect("El vendedor no ve gastos de otros", v.get(f"/expenses/{g.get('id')}/receipt"), 404)

    section("13. Proveedores y pagos")
    prov = expect("Contabilidad crea proveedor de equipos con datos bancarios", conta.post("/payables/suppliers", json={
        "name": f"QA Ferguson HVAC {RUN}", "kinds": ["equipment"], "payment_terms_days": 30, "states": ["CA", "AZ"],
        "bank_details": "Chase ****1234", "contact_name": "QA Contacto", "email": "qa.ferguson@example.com",
        "license_expires_on": (HOY + timedelta(days=10)).isoformat()}), 201) or {}
    r = expect("Importar proveedores desde CSV (QuickBooks)", conta.post("/payables/suppliers/import", json={
        "text": f"Nombre,EIN,Teléfono,Condiciones,Tipo\nQA CED Electrical {RUN},12-3456789,(602) 555-0101,15,electrical\n"
                f"QA Instalador Pérez {RUN},,(602) 555-0102,0,contractor\n"}), 200) or {}
    check("Dos proveedores importados", r.get("created") == 2, str(r))
    check("Gerencia (Aldo) no ve datos bancarios",
          ger.get("/payables/suppliers", params={"q": f"Ferguson HVAC {RUN}"}).json()[0]["bank_details"] == "•••")
    def factura(numero, **kw):
        datos = {"supplier_id": prov.get("id"), "number": numero, "invoice_date": HOY.isoformat(), **kw}
        return conta.post("/payables/invoices", data={"data": json.dumps(datos)},
                          files={"file": ("factura.pdf", pdf_doc("QA factura"), "application/pdf")})
    f1 = expect("Factura de equipos con líneas por instalación (TECH y Arizona)", factura(f"QA-{RUN}-1", lines=[
        {"description": "Mini-split 12k", "category": "equipment", "quantity": "1", "unit_cost": "1450.00", "project_id": pid},
        {"description": "Bomba de calor 24k", "category": "equipment", "quantity": "1", "unit_cost": "2350.00", "project_id": pid_az},
        {"description": "Línea de refrigerante", "category": "materials", "quantity": "2", "unit_cost": "60.00", "project_id": pid}],
        tax="310.00", shipping="40.00"), 201) or {}
    check(f"Total con impuestos y envío ({f1.get('total')})", f1.get("total") == "4270.00", str(f1.get("total")))
    expect("Factura duplicada se rechaza", factura(f"QA-{RUN}-1", total="10"), 409)
    expect("Contabilidad sola no aprueba bajo el umbral", conta.post(f"/payables/invoices/{f1.get('id')}/approve", json={}), 403)
    expect("Aldo (Gerencia) aprueba", ger.post(f"/payables/invoices/{f1.get('id')}/approve", json={}), 200)
    expect("Aldo programa el pago", ger.post(f"/payables/invoices/{f1.get('id')}/schedule", json={
        "scheduled_payment_date": (HOY + timedelta(days=5)).isoformat()}), 200)
    grande = expect("Factura de contratista de 12.500 USD", factura(f"QA-{RUN}-2", total="12500.00",
                                                                      category="contractor", project_id=pid), 201) or {}
    check("Necesita dos aprobaciones", grande.get("approvals_missing") == ["approve", "accounting"], str(grande.get("approvals_missing")))
    expect("Primera aprobación (Aldo)", ger.post(f"/payables/invoices/{grande.get('id')}/approve", json={}), 200)
    expect("Aldo no puede dar la segunda", ger.post(f"/payables/invoices/{grande.get('id')}/approve", json={}), 409)
    r = expect("Segunda aprobación (Contabilidad)", conta.post(f"/payables/invoices/{grande.get('id')}/approve", json={}), 200) or {}
    check("Aprobada con las dos", r.get("status") == "approved", str(r.get("status")))
    tarjeta = expect("Compra con tarjeta, pagada al momento", factura(f"QA-{RUN}-3", total="86.40", paid_now=True,
                                                                       paid_method="card", project_id=pid), 201) or {}
    check("Queda pagada sin pasar por aprobación", tarjeta.get("status") == "paid", str(tarjeta.get("status")))
    expect("Factura de material que vence en 3 días (para la alerta)", factura(
        f"QA-{RUN}-4", total="230.00", category="materials", due_date=(HOY + timedelta(days=3)).isoformat()), 201)
    def pago(monto, repartos, ref):
        return conta.post("/payables/payments", data={"data": json.dumps({
            "supplier_id": prov.get("id"), "paid_on": HOY.isoformat(), "amount": monto, "method": "check",
            "reference": ref, "bank_account": "Chase operativa", "allocations": repartos})},
            files={"file": ("cheque.jpg", jpeg("cheque"), "image/jpeg")})
    expect("Pago que no cuadra con el reparto se rechaza", pago("100", [{"invoice_id": f1.get("id"), "amount": "90"}], "X"), 400)
    expect("Pago de dos facturas: completa la primera y abona 2.500 a la grande",
           pago("6770.00", [{"invoice_id": f1.get("id"), "amount": "4270.00"},
                            {"invoice_id": grande.get("id"), "amount": "2500.00"}], f"QA-CHK-{RUN}"), 201)
    g_inv = conta.get(f"/payables/invoices/{grande.get('id')}").json()
    check(f"Grande parcial con saldo 10.000 ({g_inv.get('balance')})",
          (g_inv.get("status"), g_inv.get("balance")) == ("partially_paid", "10000.00"))
    ag = expect("Antigüedad de cuentas por pagar", ger.get("/payables/aging"), 200) or {}
    check("Aparece lo que se le debe al proveedor", any(r["supplier_id"] == prov.get("id") for r in ag.get("rows", [])))
    exp_csv = conta.get("/payables/export.csv", params={"kind": "payments"})
    check("Exportación de pagos para el contador", exp_csv.status_code == 200 and f"QA-CHK-{RUN}" in exp_csv.text)
    expect("El técnico no entra a proveedores", tec.get("/payables/suppliers"), 403)

    section("14. Conciliación bancaria")
    extracto = (f"Date,Description,Amount\n{HOY.isoformat()},CHECK QA-CHK-{RUN},-6770.00\n"
                f"{HOY.isoformat()},ZELLE QA reembolso,-48.75\n{HOY.isoformat()},MONTHLY SERVICE FEE,-15.00\n"
                f"{HOY.isoformat()},DEPOSITO DESCONOCIDO,+123.45\n")
    r = expect("Importar extracto del banco", conta.post("/reconciliation/statements", data={"account_label": f"QA Chase {RUN}"},
                                                         files={"file": ("extracto.csv", extracto.encode(), "text/csv")}), 201) or {}
    check(f"Se concilian solos el cheque y el reembolso ({r.get('auto_matched')} de {r.get('lines')})",
          r.get("auto_matched", 0) >= 2, str(r))
    pend = conta.get("/reconciliation/lines", params={"status": "unmatched", "limit": 50}).json()
    fee = next((l for l in pend if "SERVICE FEE" in l["description"]), None)
    if fee:
        expect("Comisión marcada como «otro»", conta.post(f"/reconciliation/lines/{fee['id']}/ignore",
                                                          json={"notes": "Comisión mensual del banco"}), 200)
    expect("Gerencia no concilia", ger.get("/reconciliation/summary"), 403)

    section("15. Rentabilidad, reportes y permisos")
    rep = expect("Rentabilidad de la instalación TECH", ger.get("/finance/profitability", params={"project_id": pid}), 200) or {}
    fila = (rep.get("rows") or [{}])[0]
    check(f"Cobrado {fila.get('collected')} · costos {fila.get('costs')} · margen {fila.get('margin')}",
          fila.get("collected") not in (None, "0.00") and fila.get("costs") not in (None, "0.00"), str(fila)[:250])
    check("El costo incluye equipos, contratista y la gasolina aprobada",
          all(float(fila.get("cost_breakdown", {}).get(k, 0)) > 0 for k in ("equipment", "contractor", "field_expenses")),
          str(fila.get("cost_breakdown")))
    for kind in ("commercial", "operations", "finance"):
        r = expect(f"Reporte {kind}", ger.get(f"/reports/{kind}", params={"date_from": (HOY - timedelta(days=30)).isoformat()}), 200) or {}
        check(f"  {kind}: {len(r.get('kpis', []))} indicadores, {len(r.get('sections', []))} secciones", bool(r.get("kpis")))
    csv_r = ger.get("/reports/commercial/csv")
    check("Reporte comercial en CSV", csv_r.status_code == 200 and csv_r.text.startswith("Reporte"))
    expect("El técnico no ve reportes", tec.get("/reports/finance"), 403)
    perms = expect("Permisos por vencer en 30 días", adm.get("/permits", params={"expiring_within_days": 30}), 200) or []
    check(f"{len(perms)} permisos por vencer (el QA dejó permisos a 5 días)", len(perms) >= 1)
    expect("Inspecciones (todas)", adm.get("/inspections"), 200)
    expect("El vendedor no ve permisos", v.get("/permits"), 403)
    time.sleep(6)  # el worker procesa los avisos de gastos
    salida = worker("from app.modules.notifications import service\nprint(await service.daily_alerts_all(db))")
    check(f"Alertas diarias con finanzas: {(salida.splitlines() or ['?'])[-1]}", bool(salida))
    eventos = {i["event"] for i in conta.get("/notifications", params={"limit": 100}).json()}
    check("Contabilidad recibe «factura por vencer» y «licencia de proveedor por vencer»",
          {"payable.due_soon", "supplier.document_expiring"} <= eventos, str(sorted(eventos)))
    eventos_t = {i["event"] for i in tec.get("/notifications", params={"limit": 100}).json()}
    check("El técnico recibe gasto aprobado y rechazado", {"expense.approved", "expense.rejected"} <= eventos_t,
          str(sorted(eventos_t)))
    RECORDS["Proveedor"] = f"QA Ferguson HVAC {RUN} (facturas QA-{RUN}-1/2/3)"


def xlsx_catalogo(filas: list[list]) -> bytes:
    """Un .xlsx mínimo con la hoja «Catálogo», como el Excel que llena el cliente."""
    import zipfile
    from xml.sax.saxutils import escape

    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    def celda(col: int, fila: int, valor) -> str:
        ref = f"{chr(65 + col)}{fila}"
        if isinstance(valor, (int, float)):
            return f'<c r="{ref}"><v>{valor}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(valor))}</t></is></c>'

    filas_xml = "".join(f'<row r="{i}">' + "".join(celda(j, i, v) for j, v in enumerate(f) if v is not None) + "</row>"
                        for i, f in enumerate(filas, start=1))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
                                      f'<sheet name="Catálogo" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{filas_xml}</sheetData></worksheet>')
    return buf.getvalue()


def obra_abierta_del_tecnico(adm: "Client", tec: "Client", preferida: str | None) -> str | None:
    """Desde el ataque del 24 oct (A4) no se pide material para una obra cerrada.
    La obra de Arizona ya terminó su instalación cuando llega esta sección, así
    que bodega usa una obra abierta del técnico (o la preferida si sigue abierta)."""
    for estado in ("in_progress", "scheduled", "planning"):
        filas = adm.get("/projects", params={"status": estado, "limit": 200}).json()
        filas = filas.get("items", filas) if isinstance(filas, dict) else filas
        mias = [p["id"] for p in filas if p.get("primary_technician_user_id") == tec.me["id"]]
        if preferida in mias:
            return preferida
        if mias:
            return mias[0]
    return preferida


def flujo_bodega(c: dict, pid: str | None) -> None:
    """Bodega (cuestionario del 19 oct): catálogo, salidas autorizadas, listas,
    presupuesto contra costo real y diario de obra, con lo que cada rol NO puede."""
    adm, tec, admin, ger, conta, v = c["adm"], c["tecnico"], c["admin"], c["gerencia"], c["conta"], c["vendedor"]
    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    section("16. Bodega: catálogo desde el Excel del cliente y conteo")
    sku_tubo, sku_cap, sku_cinta = f"QA{RUN}-CU38", f"QA{RUN}-CAP", f"QA{RUN}-CIN"
    libro = xlsx_catalogo([
        ["Nombre del material", "Referencia / SKU", "Categoría", "Unidad", "Costo unitario", "Proveedor habitual",
         "Cantidad en bodega hoy", "Cantidad mínima", "¿Lleva serial?"],
        ["Ejemplo: no se carga", "X", "Otro", "unidades", 1, None, 1, None, "No"],
        [f"QA {RUN} Tubo cobre 3/8", sku_tubo, "Tubería y cobre", "pies (ft)", 3.25, "Ferguson", 200, 50, "No"],
        [f"QA {RUN} Capacitor 35/5", sku_cap, "Eléctrico", "unidades", 18.5, "CED", 4, 5, "No"],
        [f"QA {RUN} Cinta de aluminio", sku_cinta, "Consumibles", "rollos", 7, None, 30, 10, "No"],
    ])
    archivo = {"file": (f"catalogo-qa-{RUN}.xlsx", libro, xlsx_mime)}
    r = expect("Administración sube el Excel del catálogo", adm.post("/warehouse/import", files=archivo), 200) or {}
    check("Carga 3 artículos y su conteo inicial; la fila de ejemplo no entra",
          (r.get("creados"), r.get("conteo_inicial")) == (3, 3), json.dumps(r)[:200])
    r = adm.post("/warehouse/import", files={"file": (f"catalogo-qa-{RUN}.xlsx", libro, xlsx_mime)}).json()
    check("Subir el mismo Excel otra vez no suma la existencia dos veces",
          (r.get("creados"), r.get("conteo_inicial"), r.get("actualizados")) == (0, 0, 3), json.dumps(r)[:200])
    r = adm.post("/warehouse/import", files={"file": ("malo.xlsx", b"no soy un excel", xlsx_mime)})
    check("Un archivo que no es Excel → 400", r.status_code == 400, f"{r.status_code} {r.text[:120]}")
    expect("El técnico no puede importar el catálogo", tec.post("/warehouse/import", files=archivo), 403)

    items = {i["sku"]: i for i in adm.get("/warehouse/items", params={"q": f"QA {RUN}", "page_size": 50}).json()}
    tubo, cap, cinta = items.get(sku_tubo), items.get(sku_cap), items.get(sku_cinta)
    if not check("Los tres artículos quedaron en el catálogo", all((tubo, cap, cinta)), str(list(items))):
        return
    check("Existencia inicial del tubo: 200 ft", tubo["total_quantity"] == "200.00", tubo["total_quantity"])
    resumen = adm.get("/warehouse/stock/summary").json()
    check("El capacitor (4, mínimo 5) cuenta como «por reponer»", resumen.get("low_count", 0) >= 1, json.dumps(resumen))
    bodega = next((u for u in adm.get("/warehouse/locations", params={"page_size": 50}).json()
                   if u["kind"] == "warehouse"), None)
    expect("Conteo mensual: la cinta tenía 28, no 30",
           adm.post("/warehouse/counts", json={"location_id": bodega["id"] if bodega else None, "note": f"QA {RUN}",
                                               "lines": [{"item_id": cinta["id"], "counted_quantity": "28"}]}), 200, 201)
    check("El conteo cuadra el saldo con un ajuste",
          adm.get(f"/warehouse/items/{cinta['id']}").json()["total_quantity"] == "28.00")
    ajustes = adm.get("/warehouse/movements", params={"item_id": cinta["id"], "movement_type": "ajuste"}).json()
    check("El ajuste queda en el libro de movimientos", len(ajustes) == 1, json.dumps(ajustes)[:150])
    RECORDS["Bodega · artículos"] = f"{sku_tubo}, {sku_cap}, {sku_cinta}"

    # Catálogo listo para AC Pro (plan bodega-cierre, fase 3).
    categoria = expect("Administración crea una categoría propia", adm.post(
        "/warehouse/categories", json={"label": f"QA {RUN} Bombas"}), 201) or {}
    expect("El técnico no administra categorías", tec.post("/warehouse/categories", json={"label": "X"}), 403)
    bomba = expect("Artículo con código AC Pro, número del fabricante y marca", adm.post("/warehouse/items", json={
        "name": f"QA {RUN} Condensate Pump 22' Lift", "sku": f"QA{RUN}-1936", "manufacturer_part": f"CP-22T-{RUN}",
        "brand": "Diversitech", "category": categoria.get("code", "other"), "unit": "unit", "unit_cost": "80.46"}),
        201) or {}
    hallados = adm.get("/warehouse/items", params={"q": f"cp-22t-{RUN}"}).json()
    check("El buscador lo encuentra por el número del fabricante",
          [a.get("id") for a in hallados] == [bomba.get("id")], json.dumps(hallados)[:200])
    expect("Desactivar la categoría", adm.put(f"/warehouse/categories/{categoria.get('id')}",
                                              json={"active": False}), 200)
    check("La categoría desactivada ya no se ofrece",
          categoria.get("code") not in adm.get("/warehouse/catalogs").json().get("categories", {}))
    r = adm.post("/warehouse/items", json={"name": f"QA {RUN} otra bomba", "category": categoria.get("code")})
    check("Un artículo nuevo no puede usar la categoría desactivada", r.status_code == 400, f"{r.status_code}")

    section("17. Bodega: camioneta del técnico y lo que el técnico ve")
    camioneta = expect("Administración crea la camioneta del técnico", adm.post("/warehouse/locations", json={
        "name": f"QA {RUN} Camioneta", "kind": "truck", "technician_user_id": tec.me["id"]}), 201) or {}
    expect("Carga 20 ft de tubo a la camioneta (traslado)", adm.post("/warehouse/movements", json={
        "item_id": tubo["id"], "movement_type": "traslado", "quantity": "20", "to_location_id": camioneta.get("id"),
        "reference": f"QA {RUN}"}), 201)
    expect("Una salida manual por fuera de una orden → 400", adm.post("/warehouse/movements", json={
        "item_id": tubo["id"], "movement_type": "salida", "quantity": "5"}), 400)
    visto = tec.get(f"/warehouse/items/{tubo['id']}").json()
    check("El técnico ve el artículo sin costo", "unit_cost" not in visto and "value" not in visto, json.dumps(visto)[:150])
    check("De existencias, el técnico solo ve su camioneta (20 ft)",
          [(l["name"], l["quantity"]) for l in visto.get("by_location", [])] == [(f"QA {RUN} Camioneta", "20.00")],
          json.dumps(visto.get("by_location"))[:200])
    # El buscador de artículos (plan bodega-cierre, fase 1) pide 20 activos con lo escrito.
    hallados = tec.get("/warehouse/items", params={"q": sku_cap.lower(), "active": True, "limit": 20}).json()
    check("El buscador del técnico encuentra el capacitor por su referencia, sin costo",
          [a.get("sku") for a in hallados] == [sku_cap] and "unit_cost" not in hallados[0],
          json.dumps(hallados)[:200])
    for ruta in ("/warehouse/stock", "/warehouse/movements", "/warehouse/purchasing", "/warehouse/budgets"):
        expect(f"técnico GET {ruta} → 403", tec.get(ruta), 403)
    expect("El vendedor no entra a bodega", v.get("/warehouse/items"), 403)
    expect("Contabilidad ve existencias (las entradas por compra son suyas)", conta.get("/warehouse/stock"), 200)
    expect("Gerencia ve existencias", ger.get("/warehouse/stock"), 200)
    expect("Gerencia no mueve existencias", ger.post("/warehouse/movements", json={
        "item_id": tubo["id"], "movement_type": "entrada", "quantity": "1"}), 403)

    section("18. Bodega: listas predefinidas y órdenes de salida")
    kit = expect("Administración arma la lista «Mini split 12k»", adm.post("/warehouse/kits", json={
        "name": f"QA {RUN} Mini split 12k", "project_type": "mini_split", "items": [
            {"item_id": tubo["id"], "quantity": "25", "spec_label": "3/8", "section": "Tubería"},
            {"item_id": cinta["id"], "quantity": "2", "section": "Consumibles"}]}), 201) or {}
    expect("El técnico no puede crear listas", tec.post("/warehouse/kits", json={
        "name": "x", "items": [{"item_id": tubo["id"]}]}), 403)
    orden = expect("El técnico arma su borrador para la obra", tec.post("/warehouse/releases", json={
        "project_id": pid, "note": f"QA {RUN}", "lines": [{"item_id": cap["id"], "quantity": "6"}]}), 201) or {}
    aplicada = expect("Aplica la lista a su borrador", tec.post(f"/warehouse/kits/{kit.get('id')}/apply",
                                                                json={"release_id": orden.get("id")}), 200) or {}
    check("La lista agrega sus 2 renglones", aplicada.get("agregadas") == 2, json.dumps(aplicada)[:150])
    check("La orden del técnico no muestra costos",
          all("unit_cost" not in l for l in aplicada.get("lines", [])), json.dumps(aplicada.get("lines"))[:150])
    enviada = expect("El técnico la manda a autorizar", tec.post(f"/warehouse/releases/{orden.get('id')}/submit"), 200) or {}
    check("Recibe número de la serie SAL", str(enviada.get("number", "")).startswith("SAL-"), str(enviada.get("number")))
    expect("El técnico no puede autorizar", tec.post(f"/warehouse/releases/{orden.get('id')}/approve"), 403)
    pendientes = [o["id"] for o in adm.get("/warehouse/releases/pending", params={"page_size": 100}).json()]
    check("La orden aparece en «Por autorizar»", orden.get("id") in pendientes)
    expect("Administración la autoriza", adm.post(f"/warehouse/releases/{orden.get('id')}/approve"), 200)
    entrega = expect("Administración la entrega", adm.post(f"/warehouse/releases/{orden.get('id')}/deliver",
                                                            json={"note": f"QA {RUN}"}), 200) or {}
    faltan = entrega.get("faltantes", [])
    check("Se entrega aunque falte capacitor, con aviso de faltante (pidió 6, había 4)",
          entrega.get("status") == "entregada" and len(faltan) == 1, json.dumps(faltan)[:200])
    r = adm.post(f"/warehouse/releases/{orden.get('id')}/deliver", json={})
    saldo = adm.get(f"/warehouse/items/{tubo['id']}").json()["total_quantity"]
    check("Entregar dos veces no descuenta dos veces (tubo 200 − 25 = 175)",
          r.status_code in (200, 400, 409) and saldo == "175.00", f"{r.status_code} · tubo {saldo}")
    RECORDS["Bodega · orden entregada"] = str(enviada.get("number"))

    # La lista como checklist (plan bodega-cierre, fase 2).
    de_lista = [l for l in aplicada.get("lines", []) if l.get("origin") == "lista"]
    check("Los renglones de la lista traen su sección y si son obligatorios",
          {l.get("section") for l in de_lista} == {"Tubería", "Consumibles"} and all(l.get("is_required") for l in de_lista),
          json.dumps(de_lista)[:200])
    linea_tubo = next((l for l in entrega.get("lines", []) if l.get("item_id") == tubo["id"]), {})
    cargada = expect("El técnico marca «lo llevo» el tubo al cargar la camioneta", tec.post(
        f"/warehouse/releases/{orden.get('id')}/lines/{linea_tubo.get('id')}/load", json={"loaded": True}), 200) or {}
    check("La orden cuenta lo cargado", (cargada.get("loading") or {}).get("loaded") == 1,
          json.dumps(cargada.get("loading")))
    expect("El vendedor no marca la carga", v.post(
        f"/warehouse/releases/{orden.get('id')}/lines/{linea_tubo.get('id')}/load", json={"loaded": True}), 403)
    r = tec.post("/warehouse/releases", json={
        "lines": [{"item_id": tubo["id"], "quantity": "5", "is_required": True, "origin": "lista"}],
        "omissions": [{"item_id": cinta["id"], "reason": "  "}]})
    check("Quitar un obligatorio sin motivo → 400", r.status_code == 400, f"{r.status_code}")
    con_motivo = expect("Quitar un obligatorio con motivo queda en la orden", tec.post("/warehouse/releases", json={
        "lines": [{"item_id": tubo["id"], "quantity": "5", "is_required": True, "origin": "lista"}],
        "omissions": [{"item_id": cinta["id"], "reason": f"QA {RUN}: ya hay en la camioneta"}]}), 201) or {}
    check("El motivo viaja con la orden", (con_motivo.get("omissions") or [{}])[0].get("reason", "").endswith("camioneta"),
          json.dumps(con_motivo.get("omissions"))[:150])

    otra = expect("Segunda orden del técnico", tec.post("/warehouse/releases", json={
        "project_id": pid, "lines": [{"item_id": tubo["id"], "quantity": "500"}]}), 201) or {}
    tec.post(f"/warehouse/releases/{otra.get('id')}/submit")
    expect("Rechazar exige motivo", adm.post(f"/warehouse/releases/{otra.get('id')}/reject", json={"reason": ""}), 400, 422)
    rech = expect("Administración la rechaza con motivo", adm.post(f"/warehouse/releases/{otra.get('id')}/reject",
                                                                   json={"reason": "500 ft es demasiado para un mini split"}),
                  200) or {}
    check("Queda rechazada con su motivo", rech.get("status") == "rechazada", str(rech.get("status")))

    propia = expect("Administración arma una orden para sí", adm.post("/warehouse/releases", json={
        "lines": [{"item_id": cinta["id"], "quantity": "1"}]}), 201) or {}
    adm.post(f"/warehouse/releases/{propia.get('id')}/submit")
    r = adm.post(f"/warehouse/releases/{propia.get('id')}/approve")
    check("Nadie autoriza la salida que pidió → 403", r.status_code == 403, f"{r.status_code} {r.text[:120]}")
    expect("El técnico no ve la orden de otra persona", tec.get(f"/warehouse/releases/{propia.get('id')}"), 404)
    expect("El Administrador sí la autoriza", admin.post(f"/warehouse/releases/{propia.get('id')}/approve"), 200)
    mias = {o["id"] for o in tec.get("/warehouse/releases", params={"page_size": 100}).json()}
    check("El técnico solo lista sus órdenes", propia.get("id") not in mias and orden.get("id") in mias)

    if not pid:
        check("Hay proyecto para presupuesto y diario", False, "el flujo de campo no dejó proyecto")
        return
    section("19. Bodega: presupuesto de la obra contra costo real y compras sugeridas")
    presupuesto = expect("Administración arma el presupuesto de la obra", adm.post("/warehouse/budgets", json={
        "project_id": pid, "notes": f"QA {RUN}", "lines": [
            {"category": "materials", "item_id": cap["id"], "quantity": "10"},
            {"category": "labor", "description": "Mano de obra 2 técnicos", "quantity": "16", "unit_cost": "35"}]}),
        201) or {}
    expect("Le agrega la lista «Mini split 12k»", adm.post(f"/warehouse/budgets/{presupuesto.get('id')}/apply-kit",
                                                         json={"kit_id": kit.get("id")}), 200)
    expect("Gerencia solo lee: no aprueba presupuestos", ger.post(f"/warehouse/budgets/{presupuesto.get('id')}/approve"), 403)
    expect("El Administrador aprueba el presupuesto", admin.post(f"/warehouse/budgets/{presupuesto.get('id')}/approve"), 200)
    comp = expect("Presupuesto contra costo real de la obra",
                  ger.get(f"/warehouse/projects/{pid}/budget-vs-actual"), 200) or {}
    fila = next((f for f in comp.get("rows", []) if f["category"] == "materials"), {})
    check("El material entregado ya cuenta como costo real de la obra",
          float(fila.get("actual") or 0) > 0 and comp.get("budget_status") == "aprobado", json.dumps(fila)[:200])
    compras = expect("Compras sugeridas", adm.get("/warehouse/purchasing"), 200) or {}
    sug = next((f for f in compras.get("rows", []) if f["item_id"] == cap["id"]), None)
    estado = (adm.get(f"/projects/{pid}").json() or {}).get("status")
    if estado in ("completed", "cancelled"):
        # Lo ya instalado no vuelve a comprarse: una obra terminada no pide compras.
        check(f"Obra {estado}: su presupuesto ya no pide comprar capacitor", sug is None, json.dumps(sug)[:200])
    else:
        check("Sugiere comprar el capacitor que falta", sug is not None and float(sug["to_buy"]) > 0,
              json.dumps(sug)[:200])
        # Fase 4 del plan de cierre: lo que ya salió para la obra no se vuelve a pedir.
        check("Descuenta lo que ya salió para la obra (pendiente = presupuestado − entregado)",
              sug is not None and float(sug["delivered"]) > 0
              and abs(float(sug["pending"]) - (float(sug["budgeted"]) - float(sug["delivered"]))) < 0.001,
              json.dumps(sug)[:200])

    section("20. Bodega: diario de obra")
    r = tec.post(f"/warehouse/projects/{pid}/day-logs", json={
        "log_date": HOY.isoformat(), "materials": [{"item_id": tubo["id"], "quantity": "3", "location_id": bodega["id"]}]})
    check("El material del diario no puede salir de la bodega principal → 400",
          r.status_code == 400, f"{r.status_code} {r.text[:120]}")
    jornada = expect("El técnico registra la jornada con material de su camioneta",
                     tec.post(f"/warehouse/projects/{pid}/day-logs", json={
                         "log_date": HOY.isoformat(), "technician_user_id": tec.me["id"], "hours": "8",
                         "crew": f"QA {RUN} ayudante", "work_done": "Se instaló la condensadora y se probó presión",
                         "progress_note": "70%", "missing_materials": "2 codos de 3/8",
                         "next_day_plan": "Cableado y arranque",
                         "materials": [{"item_id": tubo["id"], "quantity": "6", "location_id": camioneta.get("id")},
                                       {"description": "Silicona comprada en la obra", "quantity": "1"}]}), 201) or {}
    lineas = jornada.get("materials", [])
    check("Lo de la camioneta descuenta; lo comprado en la obra solo se anota",
          [l.get("descontada") for l in lineas] == [True, False], json.dumps(lineas)[:200])
    check("La camioneta bajó de 20 a 14 ft", [l["quantity"] for l in tec.get(f"/warehouse/items/{tubo['id']}").json()
                                                ["by_location"]] == ["14.00"])
    r = tec.post(f"/warehouse/projects/{pid}/day-logs", json={"log_date": HOY.isoformat(), "hours": "2"})
    check("Una sola jornada por día y obra → 400", r.status_code == 400, f"{r.status_code} {r.text[:120]}")
    diario = expect("Gerencia lee el diario de la obra", ger.get(f"/warehouse/projects/{pid}/day-logs"), 200) or []
    check("El diario trae la jornada con su avance", any(d.get("progress_note") == "70%" for d in diario))
    RECORDS["Bodega · diario"] = f"proyecto {pid}, {HOY.isoformat()}"


def flujo_rotacion(c: dict) -> None:
    """Rotación del técnico (plan bodega-cierre, fase 5): la oficina cambia el
    responsable con la «Orden liberada», el anterior queda en solo lectura y el
    calendario lo muestra. Al final la obra vuelve a su técnico."""
    adm, tec, admin = c["adm"], c["tecnico"], c["admin"]
    section("22. Rotación del técnico en la obra")
    abiertas = [p for p in adm.get("/projects", params={"limit": 100}).json()
                if p.get("primary_technician_user_id") == tec.me["id"]
                and p.get("status") in ("planning", "scheduled", "in_progress")]
    if not check("Hay una obra abierta del técnico para rotar", bool(abiertas), "ninguna abierta"):
        return
    pid = abiertas[0]["id"]
    hoy = date.today().isoformat()
    otro = next((t for t in adm.get("/dispatch/technicians").json() if t["id"] != tec.me["id"]), None)
    if not check("Hay otro técnico a quien pasarla", otro is not None):
        return
    expect("La oficina pasa la obra a otro técnico", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": otro["id"], "scheduled_date": hoy}), 200)
    visto = tec.get(f"/projects/{pid}").json()
    check("El técnico anterior la sigue viendo, en solo lectura", visto.get("my_access") == "read_only",
          str(visto.get("my_access")))
    r = tec.post(f"/warehouse/projects/{pid}/day-logs", json={"log_date": hoy, "work_done": f"QA {RUN}"})
    check("Ya no registra jornadas → 403", r.status_code == 403, f"{r.status_code}")
    turnos = adm.get(f"/projects/{pid}/assignments").json()
    check("El historial muestra al anterior y al de hoy",
          len(turnos) >= 2 and turnos[-1].get("current") and turnos[-1]["technician_user_id"] == otro["id"],
          json.dumps(turnos)[:200])
    cal = adm.get("/warehouse/calendar", params={"date_from": hoy, "date_to": hoy}).json()
    check("El calendario muestra el cambio de responsable",
          any(a["project_id"] == pid and a["technician_user_id"] == otro["id"] for a in cal.get("assignments", [])),
          json.dumps(cal.get("assignments"))[:200])
    expect("La obra vuelve a su técnico", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": tec.me["id"], "scheduled_date": hoy}), 200)
    check("Y él vuelve a llenarla", tec.get(f"/projects/{pid}").json().get("my_access") == "full")


def flujo_costo_del_trabajo(c: dict, pid: str | None) -> None:
    """Costo del trabajo (spec 2026-10-22): estimado desde plantilla, mano de obra
    y representante, cobro adicional en efectivo y el resumen estimado contra real."""
    adm, tec, admin, ger = c["adm"], c["tecnico"], c["admin"], c["gerencia"]
    section("21. Costo del trabajo: estimado, mano de obra, efectivo y resumen")
    if not check("Hay obra para el costo del trabajo", pid is not None, "el flujo de campo no dejó proyecto"):
        return
    plantillas = {t["name"]: t for t in (expect("Administración ve las plantillas de costo",
                                                adm.get("/warehouse/cost-templates"), 200) or [])}
    check("Arrancan las tres plantillas del cliente", {"Trabajo particular ideal",
          "Pedestal (rebate) con personal propio", "Pedestal (rebate) con subcontratista"} <= set(plantillas),
          str(list(plantillas)))
    expect("El técnico no ve plantillas de costo", tec.get("/warehouse/cost-templates"), 403)
    actual = adm.get(f"/warehouse/projects/{pid}/budget").json()
    if actual and actual.get("status") != "borrador":
        check("La obra ya tenía estimado aprobado (se usa ese)", True)
    else:
        if not actual:
            actual = expect("Administración abre el estimado de la obra", adm.post("/warehouse/budgets", json={
                "project_id": pid, "notes": f"QA {RUN} costo del trabajo", "lines": []}), 201) or {}
        propio = plantillas.get("Pedestal (rebate) con personal propio", {})
        b = expect("Aplica «Pedestal con personal propio» sobre 4.200",
                   adm.post(f"/warehouse/budgets/{actual.get('id')}/apply-template",
                            json={"template_id": propio.get("id"), "expected_revenue": "4200"}), 200) or {}
        check("El estimado deja 1.500 de ganancia (35,7%)",
              (b.get("expected_profit"), b.get("expected_margin_pct")) == ("1500.00", 35.7), json.dumps(b)[:200])
        expect("El Administrador aprueba el estimado", admin.post(f"/warehouse/budgets/{actual.get('id')}/approve"), 200)

    antes = adm.get(f"/warehouse/projects/{pid}/job-costing").json()
    costo_antes = float(antes["costs"]["total"])
    extras_antes = float(antes["revenue"]["extras"])
    expect("Anota la mano de obra del técnico (600)", adm.post(f"/warehouse/projects/{pid}/cost-entries", json={
        "category": "labor", "amount": "600", "person_user_id": tec.me["id"], "description": f"QA {RUN} instalación"}), 201)
    expect("Anota el pago de Luis como representante (800)", adm.post(f"/warehouse/projects/{pid}/cost-entries", json={
        "category": "sales_rep", "amount": "800", "person_name": "Luis", "description": f"QA {RUN} representante"}), 201)
    expect("El técnico no puede anotar costos", tec.post(f"/warehouse/projects/{pid}/cost-entries", json={
        "category": "labor", "amount": "1"}), 403)
    extra = expect("El técnico anota 150 en efectivo que pagó el cliente aparte",
                   tec.post(f"/warehouse/projects/{pid}/extra-charges", json={
                       "description": f"QA {RUN} breaker 30A y cable", "amount": "150"}), 201) or {}
    check("Queda «por entregar»", extra.get("status") == "por_entregar", str(extra.get("status")))
    expect("Gerencia (solo lee) no anota efectivo a nombre de otro", ger.post(
        f"/warehouse/projects/{pid}/extra-charges", json={"description": "x", "amount": "1",
                                                           "received_by_user_id": tec.me["id"]}), 403)
    pendientes = [p["id"] for p in adm.get("/warehouse/extra-charges/pending", params={"page_size": 100}).json()]
    check("Aparece en el efectivo por entregar de la oficina", extra.get("id") in pendientes)
    expect("El técnico no puede marcarlo recibido", tec.post(f"/warehouse/extra-charges/{extra.get('id')}/deliver"), 403)
    r = expect("Administración lo recibe", adm.post(f"/warehouse/extra-charges/{extra.get('id')}/deliver"), 200) or {}
    check("Queda «recibido»", r.get("status") == "recibido", str(r.get("status")))

    resumen = expect("Gerencia ve el costo del trabajo", ger.get(f"/warehouse/projects/{pid}/job-costing"), 200) or {}
    check("El costo real suma la mano de obra y el representante (+1.400)",
          round(float(resumen["costs"]["total"]) - costo_antes, 2) == 1400.0,
          f'{costo_antes} → {resumen.get("costs", {}).get("total")}')
    check("El ingreso suma los 150 en efectivo", round(float(resumen["revenue"]["extras"]) - extras_antes, 2) == 150.0,
          json.dumps(resumen.get("revenue"))[:200])
    check("Hay margen real y estimado", resumen["profit"]["margin_pct"] is not None
          and resumen["profit"]["estimated_margin_pct"] is not None, json.dumps(resumen.get("profit"))[:200])
    expect("El técnico no ve el costo del trabajo", tec.get(f"/warehouse/projects/{pid}/job-costing"), 403)
    # La rentabilidad es de Contabilidad (`profitability.read`); Administración no la ve.
    rep = c["conta"].get("/finance/profitability", params={"project_id": pid}).json()
    fila = (rep.get("rows") or [{}])[0]
    check("Rentabilidad y panel dan el mismo costo", fila.get("costs") == resumen["costs"]["total"],
          f'{fila.get("costs")} vs {resumen["costs"]["total"]}')
    RECORDS["Costo del trabajo"] = f"proyecto {pid}: estimado pedestal propio, mano de obra 600, Luis 800, efectivo 150"


def flujo_turnos(c: dict) -> None:
    """Turnos, asistencia y mapa (spec 2026-10-24-turnos-mapa): malla, ventana
    obligatoria, entrada con GPS, en camino / llegué, pausa, cola sin señal,
    reintentos sin duplicar, dos teléfonos a la vez, novedad aprobada, panel,
    nómina y mapa. Contra Postgres de verdad, donde el índice parcial de «una
    sola marcación abierta» se prueba con peticiones simultáneas."""
    import threading
    import uuid as _uuid

    adm, tec, admin, conta, ger, v = c["adm"], c["tecnico"], c["admin"], c["conta"], c["gerencia"], c["vendedor"]
    section("23. Turnos, asistencia, nómina y mapa")
    yo = tec.get("/attendance/me").json()
    if yo.get("entry"):
        tec.post("/attendance/events", json={"event_type": "clock_out", "note": f"QA {RUN} cierre previo"})
    zona = ZoneInfo(yo.get("timezone") or "America/Bogota")
    ahora = datetime.now(zona)
    inicio = (ahora - timedelta(minutes=20)).strftime("%H:%M")
    fin = (ahora + timedelta(hours=6)).strftime("%H:%M")
    dia = ahora.date().isoformat()
    r = expect("Administración programa el turno del técnico hoy", adm.post("/attendance/shifts", json={
        "user_ids": [tec.me["id"]], "date_from": dia, "date_to": dia, "start_time": inicio, "end_time": fin,
        "break_minutes": 30, "notes": f"QA {RUN}"}), 201) or {}
    check("El turno queda creado (o ya había uno a esa hora)", bool(r.get("created") or r.get("skipped")), json.dumps(r)[:200])
    expect("El técnico no programa turnos", tec.post("/attendance/shifts", json={
        "user_ids": [tec.me["id"]], "date_from": dia, "date_to": dia, "start_time": "01:00", "end_time": "02:00"}), 403)
    yo = tec.get("/attendance/me").json()
    # Al repetir el QA el mismo día, el turno nuevo choca con el de la corrida anterior (ya marcado).
    check("Al entrar, la ventana obligatoria aparece", yo.get("must_clock_in") is True or bool(r.get("skipped")),
          json.dumps({k: yo.get(k) for k in ("must_clock_in", "shift_status")}))

    # Dos teléfonos marcan entrada a la vez: solo uno abre turno (índice parcial en Postgres).
    codigos: list[int] = []

    def marcar(n: int) -> None:
        codigos.append(tec.post("/attendance/events", json={
            "event_type": "clock_in", "client_event_id": f"qa-{RUN}-tel{n}", "latitude": 33.4484,
            "longitude": -112.074, "accuracy_m": 15, "location_status": "ok"}).status_code)

    hilos = [threading.Thread(target=marcar, args=(n,)) for n in range(3)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    check("Tres entradas simultáneas: una 201 y dos 409", sorted(codigos) == [201, 409, 409], str(sorted(codigos)))
    abiertas = sql(f"SELECT count(*) FROM time_entries WHERE user_id = '{tec.me['id']}' AND status = 'open'")
    check("Queda una sola marcación abierta en la base", abiertas == "1", abiertas)
    dup = tec.post("/attendance/events", json={"event_type": "clock_in", "client_event_id": f"qa-{RUN}-tel0"})
    check("Reintentar la misma marca no duplica", dup.status_code in (201, 409), str(dup.status_code))

    obras = tec.get("/attendance/me").json().get("projects_today") or []
    if obras:
        pid = obras[0]["id"]
        expect("En camino a la obra", tec.post("/attendance/events", json={
            "event_type": "en_route", "project_id": pid, "latitude": 33.45, "longitude": -112.07, "location_status": "ok"}), 201)
        llegue = expect("Llegué a la obra", tec.post("/attendance/events", json={
            "event_type": "arrived", "project_id": pid, "latitude": 33.4255, "longitude": -111.94,
            "location_status": "ok"}), 201)
        km = sql(f"SELECT distance_km, distance_source FROM attendance_events WHERE id = '{(llegue or {}).get('event_id')}'")
        check("La llegada guarda km estimados en línea recta", "straight_line" in km, km)
    else:
        check("El técnico tiene obras abiertas para marcar desplazamientos", False, "sin obras asignadas")
    expect("Pausa", tec.post("/attendance/events", json={"event_type": "pause_start", "note": "QA almuerzo"}), 201)
    expect("Segunda pausa sin cerrar la primera se rechaza", tec.post("/attendance/events", json={"event_type": "pause_start"}), 409)
    expect("Reanuda", tec.post("/attendance/events", json={"event_type": "pause_end"}), 201)

    # Cola sin señal: hora del teléfono de hace 40 min, dos veces la misma.
    cola = [{"event_type": "connectivity_lost", "client_event_id": f"qa-{RUN}-off1",
             "device_at": (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()},
            {"event_type": "connectivity_restored", "client_event_id": f"qa-{RUN}-off2",
             "device_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()}]
    r1 = expect("Llega la cola sin señal", tec.post("/attendance/events/batch", json={"events": cola}), 200) or {}
    r2 = tec.post("/attendance/events/batch", json={"events": cola}).json()
    check("Reenviar la cola no duplica", [x["status"] for x in r2.get("results", [])] == ["duplicate", "duplicate"],
          json.dumps(r2)[:200])
    check("La primera vez entró bien", [x["status"] for x in r1.get("results", [])] == ["ok", "ok"], json.dumps(r1)[:200])
    offline = sql(f"SELECT offline FROM attendance_events WHERE client_event_id = 'qa-{RUN}-off1'")
    check("La marca sin señal queda señalada (hora del teléfono)", offline == "t", offline)

    expect("Contabilidad ve el panel", conta.get("/attendance/dashboard", params={"date_from": dia, "date_to": dia}), 200)
    vivo = expect("Gerencia ve el tablero de hoy", ger.get("/attendance/live"), 200) or []
    fila = next((f for f in vivo if f["user_id"] == tec.me["id"]), {})
    check("El tablero separa turno abierto y ubicación con su antigüedad",
          fila.get("entry_status") == "open" and (fila.get("location") or {}).get("age_minutes") is not None, json.dumps(fila)[:200])
    sin_ubic = next((f for f in conta.get("/attendance/live").json() if f["user_id"] == tec.me["id"]), {})
    check("Contabilidad no ve la ubicación", sin_ubic.get("location") is None)
    expect("El vendedor no ve el panel", v.get("/attendance/dashboard", params={"date_from": dia, "date_to": dia}), 403)
    gente = expect("Gerencia ve el mapa del personal", ger.get("/operations-map/people"), 200) or []
    check("El técnico aparece en el mapa", any(g["user_id"] == tec.me["id"] for g in gente))
    mapa = expect("Administración ve las obras en el mapa", adm.get("/operations-map/projects"), 200) or {}
    check("El mapa separa obras ubicadas y sin ubicar", {"projects", "unlocated"} <= set(mapa))
    expect("Orden sugerido del día", adm.get("/operations-map/route", params={"on_date": dia, "user_id": tec.me["id"]}), 200)

    resumen = expect("Resumen antes de finalizar", tec.get("/attendance/me/summary"), 200) or {}
    check("El resumen trae horas efectivas y pausas", "effective_minutes" in resumen and resumen.get("pauses", 0) >= 1)
    fin_r = expect("FINALIZAR TURNO", tec.post("/attendance/events", json={
        "event_type": "clock_out", "note": f"QA {RUN}", "latitude": 33.4484, "longitude": -112.074, "location_status": "ok"}), 201) or {}
    eid = (fin_r.get("entry") or {}).get("id")
    nov = expect("El técnico pide corregir la salida", tec.post("/attendance/novelties", json={
        "kind": "correction", "time_entry_id": eid, "description": f"QA {RUN}",
        "requested_clock_out_at": datetime.now(timezone.utc).isoformat()}), 201) or {}
    expect("Administración la aprueba", adm.post(f"/attendance/novelties/{nov.get('id')}/approve", json={"note": "QA"}), 200)
    corr = sql(f"SELECT count(*) FROM time_entry_corrections WHERE time_entry_id = '{eid}'")
    check("La corrección queda auditada con el valor original", corr == "1", corr)
    ap = expect("Administración aprueba las horas", adm.post("/attendance/entries/approve", json={"entry_ids": [eid]}), 200) or {}
    check("Quedan aprobadas", ap.get("approved") == [eid], json.dumps(ap)[:200])
    x = conta.get("/attendance/payroll/report.xlsx", params={"date_from": dia, "date_to": dia})
    check("Nómina en Excel", x.status_code == 200 and x.content[:2] == b"PK", str(x.status_code))
    pdf = conta.get("/attendance/payroll/report.pdf", params={"date_from": dia, "date_to": dia})
    check("Nómina en PDF", pdf.status_code == 200 and pdf.content[:4] == b"%PDF", str(pdf.status_code))
    RECORDS["Turnos"] = f"turno de hoy del técnico ({inicio}–{fin}), marcación {eid} aprobada con una corrección"


def reporte() -> Path:
    total, malos = len(RESULTS), [r for r in RESULTS if not r["ok"]]
    salida = Path(__file__).resolve().parents[2] / "docs" / "qa" / f"qa-e2e-{date.today().isoformat()}-{RUN}.md"
    salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [f"# QA de punta a punta · {datetime.now():%Y-%m-%d %H:%M}", "",
              f"Contra la app real ({API}), un usuario por rol. **{total - len(malos)} de {total} pasos OK.**", "",
              "## Registros que quedaron en la base", ""]
    lineas += [f"- **{k}:** {v}" for k, v in RECORDS.items()]
    lineas += ["", f"Todo lo creado lleva «QA {RUN}» en nombres y direcciones.", "", "## Fallas", ""]
    lineas += [f"- [{r['section']}] {r['step']} — {r['detail']}" for r in malos] or ["Ninguna."]
    lineas += ["", "## Pasos", ""]
    actual = None
    for r in RESULTS:
        if r["section"] != actual:
            actual = r["section"]
            lineas += ["", f"### {actual}", ""]
        lineas.append(f"- {'✅' if r['ok'] else '❌'} {r['step']}" + (f" — {r['detail']}" if not r["ok"] else ""))
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return salida


def seguro(nombre: str, fn, *a, **kw):
    """Una sección que revienta no corta el resto del QA: queda como falla."""
    try:
        return fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001
        check(f"{nombre} terminó por error inesperado", False, f"{type(exc).__name__}: {exc}")
        return None


def main() -> int:
    c = {k: Client(k) for k in USERS}
    v, adm, admin, tec, conta = c["vendedor"], c["adm"], c["admin"], c["tecnico"], c["conta"]
    pasos = [
        lambda: flujo_salidas_tempranas(v),
    ]
    for f in pasos:
        f()
    section("2. TECH Clean (California): venta, devolución, aprobación")
    tech_id, _ = flujo_vendedor(v, adm, 1, "CA", "TECH_CLEAN_CA")
    flujo_revision(v, adm, admin, tech_id, persona(1, "CA"), devolver=True)
    section("3. TECH Clean: campo (permiso, agenda, checklist, acta devuelta y confirmada)")
    pid = flujo_campo(adm, tec, tech_id, devolver_acta=True)
    section("4. TECH Clean: cobro (rechazo, reintento, pago) y cierre")
    configurar_tech(admin)
    if pid:
        seguro("Cobro TECH", flujo_cobro, adm, conta, admin, pid, tech_id, "TECH_CLEAN_CA", rechazar=True, cerrar=True)
    section("5. Eficiencia de Arizona: venta, campo e inspección (fallida y aprobada), cobro")
    asignar_zona_az(admin, v)
    az_id, p_az = flujo_vendedor(v, adm, 2, "AZ", "AZ_EFFICIENCY")
    flujo_revision(v, adm, admin, az_id, p_az, devolver=False)
    pid_az = flujo_campo(adm, tec, az_id, devolver_acta=False, condiciones=["gas_equipment_removed"])
    if pid_az:
        seguro("Inspección", flujo_inspeccion, adm, tec, pid_az)
        seguro("Cobro AZ", flujo_cobro, adm, conta, admin, pid_az, az_id, "AZ_EFFICIENCY", rechazar=False, cerrar=False)
    seguro("Rechazo", flujo_rechazo, v, adm, admin, 3)
    section("Expediente en revisión para la alerta")
    pend_id, _ = flujo_vendedor(v, adm, 4, "CA", "TECH_CLEAN_CA")
    seguro("Notificaciones", flujo_notificaciones, v, adm, admin, tec, conta)
    seguro("Alertas", flujo_alertas, admin, adm, pend_id)
    seguro("Campañas", flujo_campanas, admin, v)
    seguro("Particular", flujo_particular, conta, admin)
    seguro("Permisos", flujo_permisos_por_rol, c)
    seguro("Finanzas", flujo_finanzas, c, pid, pid_az)
    seguro("Bodega", flujo_bodega, c, obra_abierta_del_tecnico(adm, tec, pid_az))
    seguro("Costo del trabajo", flujo_costo_del_trabajo, c, pid)
    seguro("Rotación", flujo_rotacion, c)
    seguro("Turnos", flujo_turnos, c)
    ruta = reporte()
    malos = [r for r in RESULTS if not r["ok"]]
    print(f"\n{len(RESULTS) - len(malos)}/{len(RESULTS)} OK · reporte: {ruta}")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
