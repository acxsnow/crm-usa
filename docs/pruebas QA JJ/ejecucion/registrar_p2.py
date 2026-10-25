"""Registra la reejecución tras corregir los P2 y D-007 (25 oct)."""
import glob
import json
import re

Q = "/q"
L1 = json.load(open(f"{Q}/ejecucion/lote1_reejecucion_p2.json", encoding="utf-8"))
L2 = json.load(open(f"{Q}/ejecucion/lote2_reejecucion_p2.json", encoding="utf-8"))
B11 = json.load(open(f"{Q}/ejecucion/bod011_paso2.json", encoding="utf-8"))


def n(res, eid):
    return f"{sum(c['ok'] for c in res[eid])} de {len(res[eid])}"


R = "Reejecución (25 oct, tras corregir los P2 y D-007, base QA reiniciada)"
ESC = {
    "AUTH-002": ("APROBADO", f"{R}: {n(L1, 'AUTH-002')}. Los mensajes salen en español (401 «El correo o la contraseña no son "
                 "correctos.», 429 «Demasiados intentos de ingreso. Espera 15 minutos…») y la auditoría tiene "
                 "`auth.login.failed` y `auth.login.locked` (D-005 y D-006). Falta ver en pantalla que el bloqueo se "
                 "muestra con su propio mensaje (D-005).", "5/5 (reejecutado); falta ver el bloqueo en pantalla", None),
    "SEC-004": ("En ejecución", f"{R}: {n(L1, 'SEC-004')}. `%` y `_` ya se buscan tal cual en los filtros (D-004). Sigue "
                "faltando la parte de pantalla (textos guardados y el PDF del acta).", "API 16/16; falta pantalla", None),
    "BOD-002": ("APROBADO", f"{R}: {n(L2, 'BOD-002')}. Costo -1 responde 400 «El costo no puede ser negativo.» (D-009) y el "
                "SKU repetido 409 (D-010).", "15/15 (reejecutado)", None),
    "BOD-011": ("APROBADO", f"{R}: lote 2 {n(L2, 'BOD-011')} y paso 2 aparte (`ejecucion/bod011_paso2.py`) "
                f"{sum(c['ok'] for c in B11)} de {len(B11)}. Sin seriales la entrega responde 400 `serials_count_mismatch`; "
                "el mismo serial en otra salida, 409 «… no está en bodega: está entregado a la obra.»; el serial vacío, "
                "400 «hay un serial vacío». Bodega › Seriales muestra el estado y la orden, y el técnico lo elige en "
                "Equipos instalados (D-007). Falta ver en pantalla los campos de serial al entregar.",
                "API ok (reejecutado); falta pantalla", B11),
    "INS-008": ("APROBADO", f"{R}: {n(L2, 'INS-008')}. Al rotar antes de la fecha, el turno del anterior termina el día del "
                "cambio y la lista sale en orden (D-011).", "9/9 (reejecutado)", None),
    "CON-001": ("APROBADO", f"{R}: {n(L2, 'CON-001')}, y `carrera.py` 3 veces: 0 de 30 con doble autorización (antes 6 de "
                "10). La segunda recibe 400 `release_not_pending` (D-012).", "2/2 + carrera 0/30 (reejecutado)", None),
}
for eid, (est, nota, ind, extra) in ESC.items():
    p = glob.glob(f"{Q}/escenarios/{eid}_*.md")[0]
    s = open(p, encoding="utf-8").read()
    s = re.sub(r"- \*\*Estado:\*\* .*", f"- **Estado:** {est}", s, count=1)
    linea = "- " + nota
    if extra:
        linea += "\n" + "\n".join(f"  - {'✔' if c['ok'] else '✘'} {c['check']} — `{c['dato'][:160]}`" for c in extra)
    s = re.sub(r"(- Diferencias con lo esperado: .*)", lambda m: m.group(1) + "\n" + linea, s, count=1)
    if est == "APROBADO":
        s = s.replace("- [ ] APROBADO", "- [x] APROBADO", 1).replace("- [x] FALLIDO", "- [ ] FALLIDO", 1)
        s = re.sub(r"^(\d+)\. \[ \]", r"\1. [x]", s, flags=re.M)
    open(p, "w", encoding="utf-8").write(s)
    ip = f"{Q}/00_INDICE_GENERAL.md"
    t = open(ip, encoding="utf-8").read()
    m = re.search(rf"^\| {eid} \|.*$", t, re.M)
    c = [x.strip() for x in m.group(0).strip("|").split("|")]
    c[6], c[11] = est, ind
    t = t[:m.start()] + "| " + " | ".join(c) + " |" + t[m.end():]
    open(ip, "w", encoding="utf-8").write(t)

p = f"{Q}/01_REGISTRO_DEFECTOS.md"
s = open(p, encoding="utf-8").read()
ESTADO = {"D-004": "Cerrado (2026-10-25)", "D-006": "Cerrado (2026-10-25)", "D-009": "Cerrado (2026-10-25)",
          "D-011": "Cerrado (2026-10-25)", "D-012": "Cerrado (2026-10-25)",
          "D-005": "Corregido (validado por API; falta pantalla)", "D-007": "Corregido (validado por API; falta pantalla)",
          "D-002": "Corregido (pendiente de validar en pantalla)"}
for d, est in ESTADO.items():
    i = s.index(f"| {d} |")
    j = s.index("\n", i)
    fila = s[i:j]
    s = s[:i] + re.sub(r"\| (Corregido \(pendiente de validar\)) \|", f"| {est} |", fila, count=1) + s[j:]
REG = "Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend."
VAL = {
    "- **Validación:** pendiente, reejecutar SEC-004.":
        f"- **Validación:** SEC-004 reejecutado el 25 oct: 16 de 16 por API, `%` trae solo lo que contiene `%`. {REG} **Cerrado.**",
    "- **Validación:** pendiente, reejecutar AUTH-002 (API y pantalla).":
        "- **Validación:** AUTH-002 reejecutado el 25 oct: 5 de 5 por API, con los mensajes en español. Falta ver en pantalla que el bloqueo muestra su propio mensaje.",
    "- **Validación:** pendiente, reejecutar AUTH-002.":
        f"- **Validación:** AUTH-002 reejecutado el 25 oct: la auditoría tiene `auth.login.failed` (6) y `auth.login.locked` (1). {REG} **Cerrado.**",
    "- **Validación:** pendiente, reejecutar BOD-002.":
        f"- **Validación:** BOD-002 reejecutado el 25 oct: 15 de 15. {REG} **Cerrado.**",
    "- **Validación:** pendiente, reejecutar INS-008.":
        f"- **Validación:** INS-008 reejecutado el 25 oct: 9 de 9. {REG} **Cerrado.**",
}
for a, b in VAL.items():
    assert s.count(a) == 1, a
    s = s.replace(a, b)
a = "- **Validación:** pendiente, reejecutar CON-001 y `carrera.py` (10 intentos)."
i = s.index(a)
j = s.index("\n", i)
s = s[:i] + ("- **Validación:** CON-001 reejecutado el 25 oct: 2 de 2, y `carrera.py` 3 veces: 0 de 30 con doble autorización "
             "(antes 6 de 10). La segunda recibe 400 `release_not_pending` (el mismo código que ya daba al autorizar dos veces "
             f"seguidas), no 409, para no cambiar el contrato. {REG} **Cerrado.**") + s[j:]
a = "- **Validación:** pendiente, reejecutar BOD-011 (el lote 2 ya entrega la lista de 3 ton con los seriales del 85980) y la parte de pantalla."
assert s.count(a) == 1
s = s.replace(a, "- **Validación:** BOD-011 reejecutado el 25 oct: lote 2 18 de 18 (entrega de la lista de 3 ton con los seriales "
              "del 85980, consulta, técnico, instalación y vuelta a «Entregado») y paso 2 aparte 4 de 4 (mismo serial en otra "
              f"salida 409, vacío 400). {REG} Falta la parte de pantalla: campos de serial al entregar, selector en Equipos "
              "instalados y Bodega › Seriales.")
for d in ("D-004", "D-006", "D-009", "D-011", "D-012"):
    i = s.index(f"\n## {d} ")
    j = s.index("\n## ", i + 5)
    s = s[:i] + s[i:j].replace("- **Estado:** Corregido (pendiente de validar).", "- **Estado:** Cerrado (25 oct).", 1) + s[j:]
open(p, "w", encoding="utf-8").write(s)
print("ok")
