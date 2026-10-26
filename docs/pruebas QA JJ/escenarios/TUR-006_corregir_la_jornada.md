# [TUR-006] Corregir una jornada mal marcada

## 1. Información general

- **ID:** TUR-006
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P2
- **Tipo de prueba:** Funcional · auditoría
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

La corrección queda trazada y no borra la marca original.

## 3. Precondiciones

- Una jornada marcada (TUR-002).

## 4. Datos de prueba

- Nueva salida: 30 minutos después.

## 5. Procedimiento paso a paso

1. [ ] **Corregir la jornada** con motivo.
2. [ ] Ver el historial.

## 6. Resultado esperado

- Se ven la marca original, la corrección, quién y por qué.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 6 de 6 comprobaciones bien. El técnico pide corregir la salida, Administración la aprueba, la corrección queda auditada con el valor original y las horas se aprueban; nómina en Excel y PDF.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (6 de 6):
  - ✔ El técnico pide corregir la salida
  - ✔ La corrección queda auditada con el valor original — `1`
  - ✔ Administración aprueba las horas
  - ✔ Quedan aprobadas — `{"approved": ["e9c9182c-c498-45cc-8946-553af1697a0f"], "errors": []}`
  - ✔ Nómina en Excel — `200`
  - ✔ Nómina en PDF — `200`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El técnico no puede corregir su propia jornada.

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
