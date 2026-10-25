import json
import sys

res = json.load(open(sys.argv[1], encoding="utf-8"))
UI = {
    "VEN-001": "Falta ver en pantalla que no aparece en el tablero hasta «Mostrar puertas cerradas».",
    "VEN-004": "Falta la parte del celular (390 px), ver la marca de agua en las fotos y el aviso de la campana en pantalla.",
    "REV-001": "Falta ver en pantalla que «Aprobar» queda bloqueado y dice cuántos documentos faltan.",
    "REV-002": "Falta ver en pantalla la tarjeta «Devuelto al vendedor» con el motivo.",
    "INS-004": "Falta la parte del celular: fotos con «Tomar foto», firma con el dedo y el PDF abierto.",
    "INS-010": "Falta la pantalla: botón «No se pudo hacer la visita», formulario y sección «Visitas fallidas».",
    "INS-011": "Falta la pantalla: aviso del límite, «Autorizar otro intento» y «Límite de visitas fallidas».",
    "INS-012": "Falta la pantalla: «Cancelar la obra…» con salidas abiertas, material afuera y el aviso «Obra cancelada».",
}
FALLA = {
    "BOD-002": ([{"id": "D-009", "texto": "Un artículo acepta costo unitario negativo", "prioridad": "P2"},
                 {"id": "D-010", "texto": "Crear un artículo con un SKU repetido responde 500", "prioridad": "P1"}],
                "Costo -1 se guarda (201) y un SKU repetido revienta con 500 (uq_warehouse_item_sku sin capturar)."),
    "BOD-006": ([{"id": "D-008", "texto": "La devolución a bodega no tiene tope: se devuelve más de lo que salió para la obra",
                  "prioridad": "P1"}],
                "Con 1 unidad afuera se registró una devolución de 50 a la obra (201) y la existencia subió 50."),
    "BOD-011": ([{"id": "D-007", "texto": "«Con serial» no tiene efecto: la bodega no registra seriales al entregar",
                  "prioridad": "P2"}],
                "La entrega no pide ni guarda seriales; el serial solo se captura después en «Equipos instalados»."),
    "INS-008": ([{"id": "D-011", "texto": "Rotar antes de la fecha agendada deja el historial de responsables incoherente",
                  "prioridad": "P2"}],
                "Al rotar hoy una obra agendada para dentro de 2 días, el anterior queda «del 27 al 27» y el nuevo «desde el 25»: "
                "el anterior termina después de que empieza el nuevo y la lista sale en desorden."),
    "CON-001": ([{"id": "D-012", "texto": "Dos autorizaciones simultáneas de la misma salida pasan las dos", "prioridad": "P2"}],
                "En el lote pasó una sola, pero al repetirlo 10 veces (script `carrera.py`) en 6 casos las dos respondieron 200 "
                "y quedaron dos `warehouse.release_authorized` en la auditoría. La entrega doble sí está protegida (BOD-016)."),
}
dec = {"_fecha": "2026-10-25", "_version": "devjj 07e97c7 (base QA reiniciada con seed_qa)"}
for eid, cs in sorted(res.items()):
    ok = sum(c["ok"] for c in cs)
    d = {"tiempo": "lote 2 por API (≈1 min)", "lote": 2}
    if eid in FALLA:
        defs, motivo = FALLA[eid]
        d.update(estado="FALLIDO", marca="FALLIDO", defectos=defs, que_paso=f"{ok} de {len(cs)} comprobaciones bien.",
                 diferencias=motivo, indice=", ".join(x["id"] for x in defs))
    elif ok < len(cs):
        d.update(estado="En ejecución", que_paso=f"{ok} de {len(cs)} comprobaciones bien.",
                 diferencias="Revisar las comprobaciones marcadas ✘.", indice=f"API {ok}/{len(cs)}")
    elif eid in UI:
        d.update(estado="En ejecución", que_paso=f"Por API, {ok} de {len(cs)} comprobaciones bien.",
                 diferencias=UI[eid], indice=f"API {ok}/{len(cs)}; falta pantalla")
    else:
        d.update(estado="APROBADO", marca="APROBADO", que_paso=f"Por API, {ok} de {len(cs)} comprobaciones bien.",
                 diferencias="Ninguna.", indice=f"{ok}/{len(cs)}")
    dec[eid] = d
dec["BOD-005"]["observaciones"] = ("No avisa al pedir ni al autorizar: la entrega sale parcial y deja el faltante escrito "
                                   "(decisión D-BOD-4 del cliente). Ninguna existencia negativa.")
dec["BOD-015"]["observaciones"] = ("0.0001 se rechaza con «La cantidad debe ser mayor que cero» (las cantidades van con 2 "
                                   "decimales); el mensaje podría decir «mínimo 0.01». 1,000,000,000 se rechaza por grande.")
dec["VEN-003"]["observaciones"] = "La variante «101 qa … dr.» reconoce la misma puerta (no crea otro expediente)."
dec["INS-002"]["observaciones"] = ("Sin ningún permiso registrado se puede liberar la orden (spec D6.4: se instala antes "
                                   "del permiso); con un permiso solo radicado, no.")
dec["INS-014"]["observaciones"] = ("El técnico no puede anotarlo en «Materiales de la orden» (pide `projects.update`): "
                                   "lo anota en el diario de obra (INS-016). La oficina sí lo anota en la orden.")
dec["COB-001"]["observaciones"] = ("Antes hubo que cargar la tarifa vigente y la zona de cobro del programa (P-03); "
                                   "sin ellas el cobro dice «sin tarifa» o «fuera de zona».")
json.dump(dec, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: v["estado"] for k, v in dec.items() if not k.startswith("_")})
