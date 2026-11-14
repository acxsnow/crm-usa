"""Ataque a la venta: visita, formulario, documentos, revisión y cliente (10 nov 2026).

Lo que puede pasar en la calle y en la oficina: un vendedor que mira o toca el
expediente de otro, archivos de un expediente usados en otro, respuestas
inventadas, saltos de etapa, aprobar sin revisar, datos personales sin
autorización y enlaces públicos inventados.

PYTHONPATH=/app:/tmp python /tmp/qa_venta.py → /tmp/qa_venta.json
"""
import httpx

from qa_comun import API, chk, cliente, e, esc, guardar, prep_p03

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "vendedor2", "tecnico", "ajeno")}
admin, adm, v, v2, tec, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "vendedor2", "tecnico", "ajeno"))
prep_p03(admin, v)
RUN = e.RUN


def subir(cli, cid, key, data=None, mime="image/jpeg", nombre="f.jpg"):
    return cli.post(f"/cases/{cid}/files", data={"field_key": key, "latitude": "34.28", "longitude": "-118.44"},
                    files={"file": (nombre, data if data is not None else e.jpeg("QA"), mime)})


# ===========================================================================
esc("VEN-A1 Un vendedor no mira ni toca el expediente de otro")
# ===========================================================================
p1 = e.persona(801, "CA")
visita = e.abrir_puerta(v, p1, "TECH_CLEAN_CA")
cid = (visita.get("case") or {}).get("id")
f_id = subir(v, cid, "docs.electric_bill").json().get("id")
chk("Expediente de Vicky con un archivo", bool(cid and f_id), f"{cid} {f_id}")
for metodo, ruta, kw in (("GET", f"/cases/{cid}", {}), ("GET", f"/cases/{cid}/form", {}),
                         ("PUT", f"/cases/{cid}/steps/customer", {"json": {"answers": {"customer.full_name": "Robado"}}}),
                         ("POST", f"/cases/{cid}/submit", {}), ("GET", f"/case-files/{f_id}", {}),
                         ("GET", f"/cases/{cid}/documents", {})):
    r = v2.call(metodo, ruta, **kw)
    chk(f"Otro vendedor: {metodo} {ruta.split('/', 3)[-1][:30]} → no", r.status_code in (403, 404), r.status_code)
r = subir(v2, cid, "docs.electric_bill")
chk("Otro vendedor no sube archivos a ese expediente", r.status_code in (403, 404), r.status_code)
tablero = v2.get("/case-board").json()
chk("En el tablero del otro vendedor no aparece", cid not in str(tablero), "")
busca = v2.get("/search", params={"q": p1["street"][:12]}).json()
chk("El buscador del otro vendedor no lo encuentra", cid not in str(busca), str(busca)[:150])
r = ajeno.get(f"/cases/{cid}")
chk("Otra organización no lo ve", r.status_code in (403, 404), r.status_code)

# ===========================================================================
esc("VEN-A2 Archivos: lo que no se debe aceptar")
# ===========================================================================
p2 = e.persona(802, "CA")
cid2 = (e.abrir_puerta(v, p2, "TECH_CLEAN_CA").get("case") or {}).get("id")
r = v.put(f"/cases/{cid2}/steps/documents", json={"answers": {"docs.electric_bill": f_id}})
cuerpo = v.get(f"/cases/{cid2}/form").json()
usado = (cuerpo.get("answers") or {}).get("docs.electric_bill") == f_id
chk("El archivo de un expediente no se puede usar en otro", r.status_code in (400, 404, 422) or not usado,
    f"{r.status_code} {r.text[:150]}")
for nombre, data, mime, archivo in (("vacío", b"", "image/jpeg", "f.jpg"), ("exe como jpg", b"MZ\x90\x00" * 50, "image/jpeg", "f.jpg"),
                                    ("html", b"<script>alert(1)</script>", "text/html", "f.html"),
                                    ("PDF falso", b"%PDF-1.4 nada", "application/pdf", "f.pdf")):
    r = subir(v, cid2, "docs.electric_bill", data, mime, archivo)
    chk(f"Archivo {nombre} se rechaza", r.status_code in (400, 413, 415, 422), r.status_code)
r = subir(v, cid2, "campo.inventado")
chk("Un campo que no existe en el formulario se rechaza", r.status_code in (400, 404, 422), r.status_code)
r = subir(v, cid2, "customer.full_name")
chk("Subir un archivo a un campo de texto se rechaza", r.status_code in (400, 422), r.status_code)

# ===========================================================================
esc("VEN-A3 Respuestas inventadas")
# ===========================================================================
for nombre, respuestas in (("opción que no existe", {"home.residence_type": "castillo"}),
                           ("texto donde va número", {"home.bedrooms": "muchas"}),
                           ("número fuera de rango", {"home.bedrooms": 999}),
                           ("campo inventado", {"campo.secreto": "x"})):
    paso = "home" if nombre != "campo inventado" else "customer"
    r = v.put(f"/cases/{cid2}/steps/{paso}", json={"answers": respuestas})
    guardado = v.get(f"/cases/{cid2}/form").json().get("answers") or {}
    clave = next(iter(respuestas))
    chk(f"Respuesta con {nombre}: no queda guardada", r.status_code in (400, 422) or guardado.get(clave) !=
        respuestas[clave], f"{r.status_code} {str(guardado.get(clave))[:40]}")
r = v.put(f"/cases/{cid2}/steps/customer", json={"answers": {"customer.full_name": "A" * 100000}})
chk("Un nombre de 100.000 letras no entra", r.status_code in (400, 413, 422), r.status_code)
r = v.put(f"/cases/{cid2}/steps/paso_inventado", json={"answers": {}})
chk("Un paso que no existe se rechaza", r.status_code in (400, 404, 422), r.status_code)
r = v.post(f"/cases/{cid2}/submit")
chk("Enviar incompleto se rechaza", r.status_code in (400, 409, 422), r.status_code)
r = v.post(f"/cases/{cid2}/terms-acceptance", json={"customer_name": "X", "signature": ""})
chk("Términos sin firma se rechazan", r.status_code in (400, 422), r.status_code)
r = v.post(f"/cases/{cid2}/terms-acceptance", json={"customer_name": "X", "signature": "data:image/png;base64,AAAA"})
chk("Una firma que no es imagen se rechaza", r.status_code in (400, 422), r.status_code)

# ===========================================================================
esc("VEN-A4 Etapas: no se salta nada")
# ===========================================================================
cid3, _ = e.flujo_vendedor(v, adm, 803, "CA", "TECH_CLEAN_CA")
r = v.post(f"/cases/{cid3}/submit")
chk("Enviar dos veces se bloquea", r.status_code in (400, 409), r.status_code)
r = v.put(f"/cases/{cid3}/steps/customer", json={"answers": {"customer.full_name": "Cambiado"}})
chk("Editar después de enviar se bloquea", r.status_code in (400, 403, 409), r.status_code)
r = v.post(f"/cases/{cid3}/transition", json={"to_stage": "approved", "approval_code": "X"})
chk("El vendedor no aprueba su propio expediente", r.status_code == 403, r.status_code)
for destino in ("paid", "installed", "billing_in_progress", "ready_to_install"):
    r = admin.post(f"/cases/{cid3}/transition", json={"to_stage": destino})
    chk(f"El Administrador no salta a «{destino}» desde la revisión", r.status_code in (400, 409, 422), r.status_code)
r = admin.post(f"/cases/{cid3}/transition", json={"to_stage": "approved", "approval_code": f"QA-{RUN}"})
chk("No se aprueba con documentos sin revisar", r.status_code in (400, 409), f"{r.status_code} {r.text[:120]}")
r = admin.post(f"/cases/{cid3}/transition", json={"to_stage": "rejected"})
chk("Rechazar sin motivo se bloquea", r.status_code in (400, 422), r.status_code)
r = admin.post(f"/cases/{cid3}/transition", json={"to_stage": "etapa_inventada"})
chk("Una etapa inventada se rechaza", r.status_code in (400, 422), r.status_code)
docs = adm.get(f"/cases/{cid3}/documents").json()
r = v.post(f"/case-files/{docs[0]['id']}/review", json={"status": "accepted"})
chk("El vendedor no revisa documentos", r.status_code == 403, r.status_code)
r = adm.post(f"/case-files/{docs[0]['id']}/review", json={"status": "rejected"})
chk("Rechazar un documento sin nota se bloquea", r.status_code in (400, 422), r.status_code)
r = adm.post(f"/case-files/{docs[0]['id']}/review", json={"status": "aprobadisimo"})
chk("Un estado de revisión inventado se rechaza", r.status_code in (400, 422), r.status_code)
r = ajeno.post(f"/case-files/{docs[0]['id']}/review", json={"status": "accepted"})
chk("Otra organización no revisa nuestros documentos", r.status_code in (403, 404), r.status_code)

# ===========================================================================
esc("VEN-A5 Cliente y datos personales")
# ===========================================================================
r = adm.post("/customers", json={"legal_name": f"QA Sin autorización {RUN}", "main_phone": "6025550111"})
chk("Sin la autorización de datos no se crea el cliente", r.status_code in (400, 422), r.status_code)
cli = e.expect("Cliente con autorización", adm.post("/customers", json={
    "legal_name": f"QA Cliente datos {RUN}", "main_phone": "6025550112", "data_consent_accepted": True}), 201) or {}
r = adm.patch(f"/customers/{cli.get('id')}", json={"main_phone": "6025550999"})
chk("Cambiar el teléfono sin volver a autorizar se bloquea", r.status_code in (400, 422), r.status_code)
r = adm.patch(f"/customers/{cli.get('id')}", json={"notes": "QA nota interna"})
chk("Una nota no pide autorización", r.status_code == 200, r.status_code)
r = adm.patch(f"/customers/{cli.get('id')}", json={"legal_name": "<img src=x onerror=alert(1)>", "data_consent_accepted": True})
guardado = adm.get(f"/customers/{cli.get('id')}").json().get("legal_name")
chk("Un nombre con HTML se guarda como texto (no se ejecuta en pantalla)", r.status_code in (200, 400, 422), guardado)
r = v.get(f"/customers/{cli.get('id')}")
chk(f"El vendedor no ve clientes ajenos a sus expedientes ({r.status_code})", r.status_code in (403, 404), r.status_code)
r = ajeno.get(f"/customers/{cli.get('id')}")
chk("Otra organización no ve el cliente", r.status_code in (403, 404), r.status_code)
r = ajeno.delete(f"/customers/{cli.get('id')}")
chk("Otra organización no borra el cliente", r.status_code in (403, 404), r.status_code)
dueño = adm.get(f"/cases/{cid3}").json().get("customer_id")
if dueño:
    r = admin.delete(f"/customers/{dueño}")
    chk("No se borra un cliente con expediente", r.status_code in (400, 409), r.status_code)

# ===========================================================================
esc("VEN-A6 Enlaces públicos inventados")
# ===========================================================================
for ruta in ("/public/customer-signature?token=inventado", "/public/quotes/inventado", "/public/pay/inventado"):
    r = httpx.get(API + ruta, timeout=30)
    chk(f"Enlace público inventado {ruta.split('?')[0]} → no existe", r.status_code in (400, 404, 410), r.status_code)
r = httpx.post(API + "/public/quotes/inventado/accept", json={"signer_name": "X", "signature": "x"}, timeout=30)
chk("Aceptar una cotización con un enlace inventado → no", r.status_code in (400, 404, 410, 422), r.status_code)

guardar("/tmp/qa_venta.json")
print("FIN")
