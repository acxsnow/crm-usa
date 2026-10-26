# [PAR-002] Emitir y anular una factura

## 1. Información general

- **ID:** PAR-002
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

La factura toma su número consecutivo y anularla exige motivo y deja rastro.

## 3. Precondiciones

- PAR-001 aceptada.

## 4. Datos de prueba

- Motivo de anulación: «Error en el valor».

## 5. Procedimiento paso a paso

1. [ ] Desde la cotización, **Emitir factura**: anotar el número.
2. [ ] Emitir una segunda factura y comparar números.
3. [ ] **Anular** la primera sin motivo y luego con él.
4. [ ] Emitir una tercera.

## 6. Resultado esperado

- Números consecutivos sin saltos ni repetidos; la anulada conserva su número.
- Sin motivo no anula.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 8 de 8 comprobaciones bien. Las tres facturas salen con números consecutivos sin saltos ni repetidos; anular sin motivo se rechaza y con «Error en el valor» queda anulada con su número y en la auditoría.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (8 de 8):
  - ✔ Emitir la factura de la cotización
  - ✔ Emitir una segunda factura
  - ✔ Anular sin motivo se rechaza — `422`
  - ✔ Anular con el motivo «Error en el valor»
  - ✔ La anulada conserva su número — `void FAC-2026-0001`
  - ✔ Emitir una tercera
  - ✔ Números consecutivos sin saltos ni repetidos ['FAC-2026-0001', 'FAC-2026-0002', 'FAC-2026-0003'] — `['FAC-2026-0001', 'FAC-2026-0002', 'FAC-2026-0003']`
  - ✔ La anulación deja rastro en la auditoría — `1`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La numeración la da `billing/numbering.py` (dos emisiones a la vez no repiten: ver CON-002).

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
