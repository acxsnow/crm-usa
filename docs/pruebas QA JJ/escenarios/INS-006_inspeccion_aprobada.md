# [INS-006] Inspección municipal aprobada

## 1. Información general

- **ID:** INS-006
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Registrar la inspección aprobada deja la obra lista para el cobro.

## 3. Precondiciones

- INS-005 hecho.

## 4. Datos de prueba

- Inspector o entidad: «City of Phoenix»; fecha y hora: hoy 10:00.

## 5. Procedimiento paso a paso

1. [ ] En la obra: **Agendar inspección** con los datos.
2. [ ] Registrar el resultado **Inspección aprobada** con su evidencia.
3. [ ] Abrir el expediente: mirar la etapa.

## 6. Resultado esperado

- El expediente sale de inspección pendiente y queda listo para el cobro.

## 7. Resultado obtenido

- Qué pasó: Por API, 5 de 5 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (5 de 5):
  - ✔ Segunda inspección
  - ✔ Aprobar sin permiso firmado se bloquea
  - ✔ Sube el permiso firmado por el inspector
  - ✔ Inspección aprobada
  - ✔ Etapa tras la inspección aprobada — `inspection_pending`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un solo evento de etapa por el resultado de la inspección.

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
