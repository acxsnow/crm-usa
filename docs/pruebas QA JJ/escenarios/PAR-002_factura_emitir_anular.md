# [PAR-002] Emitir y anular una factura

## 1. Información general

- **ID:** PAR-002
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La numeración la da `billing/numbering.py` (dos emisiones a la vez no repiten: ver CON-002).

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
