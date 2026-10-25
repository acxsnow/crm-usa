# [INS-008] Cambiar el técnico de una obra en curso (rotación)

## 1. Información general

- **ID:** INS-008
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** FALLIDO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Al rotar, el técnico nuevo continúa y el anterior queda en solo lectura, sin perder lo que registró.

## 3. Precondiciones

- Una obra «En curso» de Tito con una jornada registrada y material entregado.

## 4. Datos de prueba

- Técnico nuevo: Toño Segundo (`tecnico02@demo-org.com`).

## 5. Procedimiento paso a paso

1. [ ] Como administración, en la obra: **Cambiar técnico** a Toño.
2. [ ] Como Tito: abrir la obra desde su agenda o por la URL.
3. [ ] Como Toño: registrar una jornada y cerrar la instalación.
4. [ ] Revisar el Diario de obra.

## 6. Resultado esperado

- Tito ve la obra en solo lectura (no puede registrar ni cerrar).
- El diario muestra las jornadas de los dos, cada una con su autor.

## 7. Resultado obtenido

- Qué pasó: 8 de 9 comprobaciones bien.
- Diferencias con lo esperado: Al rotar hoy una obra agendada para dentro de 2 días, el anterior queda «del 27 al 27» y el nuevo «desde el 25»: el anterior termina después de que empieza el nuevo y la lista sale en desorden.
- Comprobaciones por API (8 de 9):
  - ✔ Hay una obra abierta del técnico para rotar — `ninguna abierta`
  - ✔ Hay otro técnico a quien pasarla
  - ✔ La oficina pasa la obra a otro técnico
  - ✔ El técnico anterior la sigue viendo, en solo lectura — `read_only`
  - ✔ Ya no registra jornadas → 403 — `403`
  - ✘ El historial muestra al anterior y al de hoy — `[{"technician_user_id": "a7426653-fc1a-4369-9718-d18d2e318b62", "technician_name": "Andr\u00e9s Morales", "started_on": "2026-10-25", "ended_on": null, "current`
  - ✔ El calendario muestra el cambio de responsable — `[{"project_id": "fa6117a2-a3dd-4f5c-9c1a-628e954d7a83", "project_title": "Instalaci\u00f3n \u00b7 CASE-2026-0009", "project_status": "scheduled", "technician_us`
  - ✔ La obra vuelve a su técnico
  - ✔ Y él vuelve a llenarla

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El material entregado sigue cargado a la obra (no a Tito).
- [ ] Por API, Tito recibe 403 al intentar registrar una jornada en esa obra.

## 10. Resultado final

- [ ] APROBADO
- [x] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-011 | Rotar antes de la fecha agendada deja el historial de responsables incoherente | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
