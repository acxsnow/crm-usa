"""Lote 3, fase F: SEC-010 (auditoría de dinero, permisos y datos personales).

Corre sobre la base del lote 3 (ya tiene facturas anuladas y pagadas, salidas
autorizadas y rotaciones). Genera las acciones de permisos y datos personales
que faltan y revisa que cada una quede con quién, qué, cuándo, antes y después.

PYTHONPATH=/app:/tmp python /tmp/lote3f.py → /tmp/lote3f.json
"""
import httpx

from qa_comun import API, chk, cliente, e, esc, guardar, limpiar, seguro

c = {k: cliente(k) for k in ("admin", "gerencia", "tecnico", "vendedor", "conta")}
admin = c["admin"]


def eventos(accion):
    return admin.get("/audit-events", params={"action": accion, "limit": 20}).json()


def sec010():
    # Permisos: cambiar los permisos de un rol y el rol de una persona.
    rol = next(r for r in admin.get("/roles").json() if r["code"] == "management")
    originales = list(rol["permissions"])
    admin.patch("/roles/management", json={"permissions": [p for p in originales if p != "reports.export"]})
    admin.patch("/roles/management", json={"permissions": originales})
    persona = next(u for u in admin.get("/users", params={"limit": 100}).json()["items"]
                   if u["email"] == "tecnico05@demo-org.com")
    admin.post(f"/users/{persona['id']}/deactivate")
    admin.post(f"/users/{persona['id']}/activate")
    # Datos personales: alta (con su autorización), corrección y borrado de un cliente.
    cli = admin.post("/customers", json={"legal_name": f"QA {e.RUN} Auditoría", "main_phone": "(602) 555-0101",
                                         "data_consent_accepted": True}).json()
    admin.patch(f"/customers/{cli['id']}", json={"main_phone": "(602) 555-0202", "data_consent_accepted": True})
    admin.delete(f"/customers/{cli['id']}")
    limpiar()
    httpx.post(f"{API}/auth/login", json={"email": "vendedor@demo-org.com", "password": "Errada123456!"}, timeout=30)

    casos = [
        ("roles.updated", "Permisos de un rol", True),
        ("users.deactivated", "Desactivar a una persona", False),
        ("users.activated", "Activarla otra vez", False),
        ("customer.consent_recorded", "Autorización de datos del cliente", False),
        ("customer.updated", "Corrección de un dato personal", False),
        ("customer.deleted", "Borrado de un cliente", True),
        ("invoices.voided", "Anulación de factura", False),
        ("invoices.payment_recorded", "Pago de factura", False),
        ("payables.payment_recorded", "Pago a proveedor", False),
        ("warehouse.release_authorized", "Autorización de salida de bodega", False),
        ("projects.installation_scheduled", "Asignación y cambio de técnico", True),
        ("auth.login.failed", "Ingreso fallido", False),
    ]
    for accion, nombre, con_antes in casos:
        lista = eventos(accion)
        ev = lista[0] if lista else {}
        quien = ev.get("actor_user_id") or ("sistema" if accion.startswith("auth.login") else None)
        detalle = ev.get("before_data") if con_antes else (ev.get("after_data") or ev.get("before_data"))
        chk(f"{nombre} ({accion}): con usuario, fecha{', antes' if con_antes else ''} y detalle",
            bool(lista) and bool(quien) and bool(ev.get("created_at")) and detalle not in (None, {}),
            f"{len(lista)} eventos; antes={str(ev.get('before_data'))[:120]} después={str(ev.get('after_data'))[:120]}")
    for usuario, esperado in (("gerencia", 200), ("conta", 200), ("tecnico", 403), ("vendedor", 403)):
        r = c[usuario].get("/audit-events")
        chk(f"{usuario} → {esperado}", r.status_code == esperado, r.status_code)


esc("SEC-010")
seguro("SEC-010", sec010)
limpiar()
guardar("/tmp/lote3f.json")
print("ok")
