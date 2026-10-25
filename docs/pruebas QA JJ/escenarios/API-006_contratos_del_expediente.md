# [API-006] Las transiciones del expediente respetan su contrato

## 1. Información general

- **ID:** API-006
- **Módulo:** API y paginación
- **Prioridad:** P1
- **Tipo de prueba:** API · contrato
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Solo se permiten las transiciones de `stages.py` y cada una con su permiso.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).
- Un expediente en «Nuevo prospecto».

## 4. Datos de prueba

- Transiciones inválidas: `new_lead → paid`, `new_lead → approved`, `closed → submitted`.

## 5. Procedimiento paso a paso

1. [ ] Intentarlas por la API como admin.

## 6. Resultado esperado

- 409/422 con el motivo; la etapa no cambia.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `docs/contratos/case.md` coincide con lo observado.

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
