# [INS-009] Cambiar las fechas de una obra programada

## 1. Información general

- **ID:** INS-009
- **Módulo:** Instalación en campo
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Reprogramar mueve la obra en la agenda sin perder nada.

## 3. Precondiciones

- Una obra programada (INS-001).

## 4. Datos de prueba

- Nueva fecha: dos días hábiles después.

## 5. Procedimiento paso a paso

1. [ ] En la obra: **Cambiar fechas**.
2. [ ] Revisar la Agenda de instalaciones y la agenda del técnico.

## 6. Resultado esperado

- La obra aparece en la nueva fecha en las dos agendas.

## 7. Resultado obtenido

- Qué pasó: Por API, 3 de 3 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (3 de 3):
  - ✔ Cambiar fechas
  - ✔ La obra aparece en la nueva fecha en la agenda del técnico
  - ✔ La auditoría registra la fecha anterior y la nueva — `{"technician": "6f7ea603-b361-484a-b02b-dea603ae0a88", "scheduled_date": "2026-10-25"}|{"technician": "6f7ea603-b361-484a-b02b-dea603ae0a88", "scheduled_date": `

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El técnico recibe el aviso del cambio.
- [ ] La auditoría registra la fecha anterior y la nueva.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
