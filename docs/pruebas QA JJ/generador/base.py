"""Plantilla común de los escenarios de `docs/pruebas QA JJ/`."""
from pathlib import Path

COMMIT = "main 23260ae"
ESTADO = "Pendiente"

PLANTILLA = """# [{id}] {nombre}

## 1. Información general

- **ID:** {id}
- **Módulo:** {modulo}
- **Prioridad:** {prioridad}
- **Tipo de prueba:** {tipo}
- **Estado:** {estado}
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** {tiempo} min de ejecución{prep}
- **Tiempo real:**
- **Versión o commit probado:** {commit} (anotar el que se pruebe de verdad)

## 2. Objetivo

{objetivo}

## 3. Precondiciones

{precondiciones}

## 4. Datos de prueba

{datos}

## 5. Procedimiento paso a paso

{pasos}

## 6. Resultado esperado

{esperado}

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

{validaciones}

## 10. Resultado final

- [ ] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
"""


def lista(items, casillas=False, numerada=False):
    if isinstance(items, str):
        return items
    salida = []
    for n, x in enumerate(items, start=1):
        if casillas:
            salida.append(f"{n}. [ ] {x}")
        elif numerada:
            salida.append(f"{n}. {x}")
        else:
            salida.append(f"- {x}")
    return "\n".join(salida)


def archivo(e):
    return f"{e['id']}_{e['slug']}.md"


def render(e):
    prep = f" + {e['prep']} min de preparación" if e.get("prep") else ""
    return PLANTILLA.format(
        id=e["id"], nombre=e["nombre"], modulo=e["modulo"], prioridad=e["prioridad"], tipo=e["tipo"],
        estado=e.get("estado", ESTADO), tiempo=e["tiempo"], prep=prep, commit=COMMIT,
        objetivo=e["objetivo"], precondiciones=lista(e["pre"]), datos=lista(e["datos"]),
        pasos=lista(e["pasos"], casillas=True), esperado=lista(e["esperado"]),
        validaciones=lista([f"[ ] {v}" for v in e["validaciones"]]),
    )


def escribir(destino: Path, escenarios):
    nuevos = 0
    for e in escenarios:
        ruta = destino / archivo(e)
        if ruta.exists():
            continue
        ruta.write_text(render(e), encoding="utf-8")
        nuevos += 1
    return nuevos
