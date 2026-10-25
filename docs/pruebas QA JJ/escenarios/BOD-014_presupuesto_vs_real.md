# [BOD-014] Presupuesto de la obra contra lo real

## 1. Información general

- **ID:** BOD-014
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La desviación entre lo presupuestado y lo consumido es correcta.

## 3. Precondiciones

- Una obra sin presupuesto.

## 4. Datos de prueba

- Presupuesto con la lista 3 ton; luego entregar el 80 %.

## 5. Procedimiento paso a paso

1. [ ] **Armar presupuesto** con la lista y **Aprobar presupuesto**.
2. [ ] Entregar parte del material.
3. [ ] Ver presupuesto vs. real.

## 6. Resultado esperado

- La desviación por renglón y total es exacta.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un presupuesto aprobado no se edita sin volver a borrador (anotar el comportamiento).

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
