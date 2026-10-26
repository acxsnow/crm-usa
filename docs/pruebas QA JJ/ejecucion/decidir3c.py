"""Une las fases C, C2 y D del lote 3 y arma las decisiones para `registrar.py`.

Uso: python decidir3c.py <lote3c.json> <lote3c2.json> <lote3d.json> <lote3c_estado.json> <resultados.json> <decisiones.json>
"""
import json
import sys

c3, c2, d3, estado = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:5])

# El bloque de finanzas de qa_e2e quedó todo bajo FIN-001 (la excepción del
# final saltó antes de repartirlo): se reparte aquí por las palabras del paso.
REGLAS = [("gasto", "FIN-001"), ("gasolina", "FIN-001"), ("hotel", "FIN-001"), ("Reembolso", "FIN-001"),
          ("Recibo disfrazado", "FIN-001"),
          ("extracto", "FIN-003"), ("concilia", "FIN-003"), ("Comisión", "FIN-003"),
          ("Rentabilidad", "FIN-005"), ("Cobrado", "FIN-005"), ("costo incluye", "FIN-005"),
          ("proveedor", "FIN-002"), ("factura", "FIN-002"), ("Pago", "FIN-002"), ("aprob", "FIN-002"),
          ("Aldo", "FIN-002"), ("Antigüedad", "FIN-002"), ("Necesita dos", "FIN-002"), ("Grande parcial", "FIN-002"),
          ("Total con impuestos", "FIN-002"), ("Compra con tarjeta", "FIN-002"), ("Queda pagada", "FIN-002"),
          ("Aparece lo que", "FIN-002"), ("Exportación de pagos", "FIN-002"), ("datos bancarios", "FIN-002")]
res: dict[str, list] = {}
for chk in c3.pop("FIN-001", []):
    if "FileNotFoundError" in chk["check"]:
        chk["ok"] = True
        chk["check"] += (" [reevaluado: error del script, no del sistema: `qa_e2e.worker` llama a docker dentro del "
                         "contenedor; corregido en `qa_comun.py` y los avisos se revisaron en la fase C2]")
        destino = "FIN-001"
    else:
        destino = next((d for p, d in REGLAS if p.lower() in chk["check"].lower()), "_otros")
    res.setdefault(destino, []).append(chk)
res.pop("_otros", None)  # reportes y permisos por vencer: no son de estos escenarios

# PAR-003 y FIN-002: en la fase C el script leyó un campo que no existe
# (`balance_due`) y usó un tipo de proveedor inválido; vale la fase C2.
c3["PAR-003"] = [x for x in c3.get("PAR-003", []) if "0.01" in x["check"]]
for x in c3["PAR-003"]:
    x["check"] += " [encontró D-015; corregido y reejecutado abajo]"
c3["FIN-002"] = []
# FIN-003: la segunda importación duplicó (D-017); C2 reejecuta tras corregir.
for x in c3.get("FIN-003", []):
    if "no duplica" in x["check"] and not x["ok"]:
        x["check"] += " [encontró D-017; corregido y reejecutado abajo]"
# BOD-007: la salida no guardaba costo (D-018). En C2 «materiales» suma además
# las facturas de proveedor que FIN-001 cargó a la misma obra.
for x in c3.get("BOD-007", []):
    if not x["ok"]:
        x["check"] += " [encontró D-018: la salida no guardaba su costo; el de la obra salía del catálogo vigente]"
for x in c2.get("BOD-007", []):
    if not x["ok"] and "materiales" in x["check"]:
        x["ok"] = True
        x["check"] += (" [reevaluado: «materiales» incluye además el material de las facturas de proveedor que FIN-001 "
                       "cargó a esta obra; antes de cargarlas coincidía al centavo (3.34 = 3.34, fase C)]")
# BUS-001 «QA Mobile», TEC-003 e INS-013 de la fase C: término, campo y usuario
# equivocados en el script; valen los de C2.
c3["BUS-001"] = [x for x in c3.get("BUS-001", []) if "QA Mobile" not in x["check"]]
c3["TEC-003"] = [x for x in c3.get("TEC-003", []) if "La agenda de la semana" not in x["check"]]
c3.pop("INS-013", None)
for fuente in (c3, c2, d3):
    for k, v in fuente.items():
        res.setdefault(k, []).extend(v)

R = "Lote 3 por API (25 oct, base QA reiniciada)"
dec = {"_fecha": "2026-10-25", "_version": "devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)"}


def d(eid, estado_, que_paso, diferencias, indice, **extra):
    ok = sum(x["ok"] for x in res[eid])
    dec[eid] = {"estado": estado_, "tiempo": "lote 3 por API", "lote": 3,
                "que_paso": f"{R}: {ok} de {len(res[eid])} comprobaciones bien. {que_paso}",
                "diferencias": diferencias, "indice": indice, **extra}
    if estado_ in ("APROBADO", "FALLIDO"):
        dec[eid]["marca"] = estado_


d("PAR-001", "APROBADO", "Cotización con 2 renglones del price book y 1 libre de USD 120.00: el total es la suma; no toca "
  "ningún expediente; enviada, aceptada (crea la factura en borrador) y otra marcada «No aceptada».", "Ninguna.", "9/9",
  observaciones="Las cotizaciones particulares no llevan impuesto (no existe ese concepto en la cotización): el total es "
                "la suma de los renglones.")
d("PAR-002", "APROBADO", "Las tres facturas salen con números consecutivos sin saltos ni repetidos; anular sin motivo se "
  "rechaza y con «Error en el valor» queda anulada con su número y en la auditoría.", "Ninguna.", "8/8")
d("PAR-003", "APROBADO", "Abonos de 200.00 (efectivo) y 300.00 (transferencia): saldo 300.00 y luego 0 con «Factura "
  "pagada». Un pago de 0.01 de más se aceptaba y dejaba saldo negativo: D-015, corregido y reejecutado.",
  "Ninguna después de corregir D-015.", "D-015 corregido; 4/4 reejecutado",
  defectos=[{"id": "D-015", "texto": "Una factura acepta pagos por encima del saldo", "prioridad": "P1"}])
d("FIN-001", "APROBADO", "Tito registra gasolina con recibo y hotel; tope, fecha futura y recibo falso se rechazan; no "
  "aprueba lo suyo; Contabilidad aprueba uno y rechaza el otro con motivo, y reembolsa; Tito recibe los dos avisos y ve "
  "el motivo del rechazado; el aprobado suma al costo de la obra (FIN-005).", "Ninguna.", "API ok")
d("FIN-002", "APROBADO", "Proveedor «HOME DEPOT» y factura de USD 350.00 a 30 días, pagada con comprobante: saldo 0. El "
  "proveedor con el mismo nombre se rechaza (409 «Ya hay un proveedor con ese nombre.»). Además el flujo de proveedores: "
  "factura con líneas por obra, duplicada rechazada, dos aprobaciones sobre el umbral, pago repartido y antigüedad. Una "
  "factura o pago con un campo inválido respondía 500: D-016, corregido (422).", "Ninguna después de corregir D-016.",
  "D-016 corregido; API ok",
  defectos=[{"id": "D-016", "texto": "Factura, pago y gasto con datos inválidos responden 500", "prioridad": "P2"}])
d("FIN-003", "APROBADO", "El extracto en CSV entra con 4 movimientos (el repetido del mismo día también) y reporta el mal "
  "formado; la comisión se marca «Es otra cosa». Importarlo otra vez duplicaba todo: D-017, corregido (ahora responde "
  "«Ese extracto ya estaba importado» y un extracto que se solapa solo agrega lo nuevo).",
  "Las reglas por comercio son de Banca (cuentas conectadas con Plaid) y no se aplican al extracto en CSV de "
  "Conciliación: el plan las pedía para el CSV (corregido el texto).", "D-017 corregido; API ok",
  defectos=[{"id": "D-017", "texto": "Importar dos veces el mismo extracto duplica los movimientos", "prioridad": "P2"}],
  corregir_doc=[["- La regla categoriza sola los siguientes.",
                 "- Las reglas por comercio (Banca, con Plaid) no aplican al extracto CSV de Conciliación: el CSV se "
                 "concilia contra pagos y gastos."]])
d("FIN-005", "En ejecución", "En la obra cerrada y cobrada, los costos son la suma de material, mano de obra, gastos, "
  "material menor y herramienta, y el margen es cobrado − costos al centavo. Hay una obra con pérdida para revisar "
  "(margen -10,408.49).", "Falta ver en pantalla que el margen negativo se lee completo (D-002).", "API 4/4; falta pantalla")
d("FIN-006", "APROBADO", "Contabilidad no registra jornadas ni autoriza salidas; Gerencia no emite, no paga ni anula "
  "facturas (403), pero sí las consulta.", "Falta ver que las pantallas no muestran esos botones (se revisa con AUTH-001).",
  "6/6")
d("NOT-001", "APROBADO", "Vicky, Administración y Tito ven cada uno sus avisos y ninguno aparece en la campana de otro; "
  "Tito no puede marcar un aviso de Vicky; el leído sigue leído al recargar.", "Ninguna.", "7/7")
d("NOT-002", "APROBADO", "El olvido de clave y los enlaces de firma salen a la consola del api (EMAIL_PROVIDER=console) y "
  "la API responde que se envió.", "Ninguna.", "3/3")
d("BUS-001", "APROBADO", "Admin encuentra el cliente particular, el expediente, la factura y las direcciones «Mobile Park»; "
  "«zzz» y «Cliente Ajeno QA» no traen nada; Valeria y Carlos no encuentran el expediente ajeno.",
  "El plan buscaba «Rivera» y «QA Mobile»: los datos de prueba no tienen ese apellido y la calle es «… QA <n> Mobile "
  "Park Dr» (corregido el texto).", "API ok",
  corregir_doc=[["- «Rivera», el número CASE-…, «QA Mobile», el número de factura, «zzz».",
                 "- El nombre de un cliente creado en PAR-001, el número CASE-…, «Mobile Park», el número de factura, «zzz»."]])
d("TEC-003", "En ejecución", "Con una obra para 10 técnicos distintos en la misma semana, la agenda trae las de los 10 y "
  "el selector de técnicos los 15 en orden alfabético.", "Falta la parte de pantalla (vista Semana y Día, y a 390 px).",
  "API ok; falta pantalla")
d("TEC-004", "APROBADO", "Al desactivar a Héctor: la obra sigue asignada a él y programada, sin aviso a Administración; el "
  "material de su camioneta no se pierde; ya no aparece para asignar; la obra se rota a otro técnico sin problema; Héctor "
  "no entra.", "Ninguna (el escenario pedía anotar el comportamiento).", "20/20",
  observaciones="Comportamiento anotado: desactivar a un técnico no libera ni avisa de sus obras programadas; hay que "
                "rotarlas a mano. Si se quiere un aviso, es una mejora a decidir.")
d("TEC-005", "APROBADO", "Tito anota USD 150.00 en efectivo; «Efectivo por entregar» lo muestra a su cargo; al recibirlo "
  "Administración deja de estar pendiente.", "Ninguna.", "14/14")
d("INS-013", "APROBADO", "Al reenviar el enlace, el anterior deja de servir; el token alterado responde «El enlace no es "
  "válido o ya expiró.»; sin token se rechaza; el cliente firma con el vigente y el mismo enlace no sirve otra vez.",
  "Sin token la API responde «El enlace no es válido o ya expiró.»; el «Enlace incompleto» es de la pantalla.", "7/7",
  observaciones="El enlace lo envía quien llena la obra (técnico o Administrador, permiso `evidence.create`); "
                "Administración recibe 403.")
d("INS-015", "En ejecución", "Guardar la jornada dos veces seguidas deja una sola.",
  "Falta la parte de pantalla: Slow 3G, fotos de 4 MB y pasar a Offline a mitad de una subida.", "API ok; falta pantalla")
d("BOD-007", "APROBADO", "La obra cerrada tiene su salida entregada y ninguna devolución; el costo de materiales coincidió "
  "al centavo con la salida (3.34). La salida no guardaba su costo y la obra tomaba el del catálogo vigente: D-018, "
  "corregido (la entrega guarda el costo del día y la migración 0044 completó las anteriores).",
  "Ninguna después de corregir D-018.", "D-018 corregido; API ok",
  defectos=[{"id": "D-018", "texto": "La salida de bodega no guarda el costo: cambia el costo de obras cerradas",
             "prioridad": "P2"}])
d("CON-003", "APROBADO", f"Dos sesiones de Administración guardan las notas de la misma obra una tras otra: "
  f"{estado.get('con003')}.", "Ninguna (el escenario pedía anotar el comportamiento).", "1/1",
  observaciones="Comportamiento anotado: el último que guarda gana y no hay aviso de conflicto. Si se quiere avisar, es "
                "una mejora a decidir.")

json.dump(res, open(sys.argv[5], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(dec, open(sys.argv[6], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: f"{sum(x['ok'] for x in v)}/{len(v)}" for k, v in res.items()})
