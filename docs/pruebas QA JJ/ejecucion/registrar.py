"""Escribe en los escenarios de `docs/pruebas QA JJ/` lo ejecutado por API.
Uso: python registrar.py <carpeta QA> <resultados.json> <decisiones.json>"""
import json
import re
import sys
from pathlib import Path

QA = Path(sys.argv[1])
RES = json.load(open(sys.argv[2], encoding="utf-8"))
DEC = json.load(open(sys.argv[3], encoding="utf-8"))
FECHA = DEC["_fecha"]
VERSION = DEC["_version"]
MARCAS = {"APROBADO": "APROBADO", "FALLIDO": "FALLIDO", "BLOQUEADO": "BLOQUEADO",
          "PENDIENTE DE CORRECCIÓN": "PENDIENTE DE CORRECCIÓN", "PENDIENTE DE REEJECUCIÓN": "PENDIENTE DE REEJECUCIÓN"}


def archivo(esc):
    return next((QA / "escenarios").glob(f"{esc}_*.md"))


for esc, d in DEC.items():
    if esc.startswith("_"):
        continue
    p = archivo(esc)
    s = p.read_text(encoding="utf-8")
    checks = RES.get(esc, []) + d.get("extra", [])
    lineas = "\n".join(f"  - {'✔' if c['ok'] else '✘'} {c['check']}" + (f" — `{c['dato'][:160]}`" if c.get("dato") else "")
                       for c in checks)
    s = re.sub(r"- \*\*Estado:\*\* .*", f"- **Estado:** {d['estado']}", s, count=1)
    s = re.sub(r"- \*\*Fecha de ejecución:\*\*.*", f"- **Fecha de ejecución:** {FECHA} (parte por API)", s, count=1)
    s = re.sub(r"- \*\*Tiempo real:\*\*.*", f"- **Tiempo real:** {d['tiempo']}", s, count=1)
    s = re.sub(r"- \*\*Versión o commit probado:\*\*.*", f"- **Versión o commit probado:** {VERSION}", s, count=1)
    s = s.replace("- Qué pasó:\n- Diferencias con lo esperado:",
                  f"- Qué pasó: {d['que_paso']}\n- Diferencias con lo esperado: {d['diferencias']}\n"
                  f"- Comprobaciones por API ({sum(c['ok'] for c in checks)} de {len(checks)}):\n{lineas}", 1)
    s = s.replace("- Respuestas HTTP (F12 › Network, filtrar `api/v1`):",
                  f"- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 "
                  f"(script `lote{d.get('lote', 1)}` por API).", 1)
    if d.get("consultas"):
        s = s.replace("- Consultas de verificación:", f"- Consultas de verificación: {d['consultas']}", 1)
    for v in d.get("validaciones_ok", []):
        s = s.replace(f"- [ ] {v}", f"- [x] {v}", 1)
    for paso in d.get("pasos_ok", []):
        s = re.sub(rf"^{paso}\. \[ \]", f"{paso}. [x]", s, count=1, flags=re.M)
    if d.get("marca"):
        s = s.replace(f"- [ ] {d['marca']}", f"- [x] {d['marca']}", 1)
    if d.get("defectos"):
        filas = "\n".join(f"| {x['id']} | {x['texto']} | {x['prioridad']} | `01_REGISTRO_DEFECTOS.md` |" for x in d["defectos"])
        s = s.replace("| | | | `01_REGISTRO_DEFECTOS.md` |", filas, 1)
    s = s.replace("- Tiempo de ejecución:", f"- Tiempo de ejecución: {d['tiempo']}", 1)
    if d.get("observaciones"):
        s = s.replace("- Observaciones:", f"- Observaciones: {d['observaciones']}", 1)
    for viejo, nuevo in d.get("corregir_doc", []):
        assert viejo in s, (esc, viejo)
        s = s.replace(viejo, nuevo)
    p.write_text(s, encoding="utf-8")

# Índice: estado, tiempo real, defectos y observaciones de cada fila.
ind = QA / "00_INDICE_GENERAL.md"
s = ind.read_text(encoding="utf-8")
for esc, d in DEC.items():
    if esc.startswith("_"):
        continue
    patron = re.compile(rf"^\| {esc} \|(.*)$", re.M)
    m = patron.search(s)
    celdas = [c.strip() for c in m.group(0).strip("|").split("|")]
    celdas[6] = d["estado"]
    celdas[8] = d["tiempo"]
    celdas[9] = ", ".join(x["id"] for x in d.get("defectos", []))
    celdas[11] = d.get("indice", "")
    s = s[:m.start()] + "| " + " | ".join(celdas) + " |" + s[m.end():]
ind.write_text(s, encoding="utf-8")
print("ok", len(DEC) - 2)
