# [INS-005] Administración devuelve el acta al técnico y luego la confirma

## 1. Información general

- **ID:** INS-005
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La instalación devuelta vuelve al técnico con el motivo y el cobro sigue bloqueado hasta confirmar.

## 3. Precondiciones

- INS-004 hecho.

## 4. Datos de prueba

- Motivo: «La foto de la etiqueta exterior no se lee».

## 5. Procedimiento paso a paso

1. [ ] Como administración, en la obra: **Confirmación de Administración** › devolver con el motivo.
2. [ ] Como Carlos: ver la obra «Devuelta al técnico» y el motivo; **Corregir** subiendo la foto nueva.
3. [ ] Como administración, **Confirmar información técnica**.
4. [ ] Revisar la sección **Cobro al programa**.

## 6. Resultado esperado

- Mientras está devuelta, «Crear cobro» dice «Se habilita al confirmar el acta».
- Tras confirmar queda «Confirmada por Administración» y el cobro se habilita.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial: devolución y confirmación con usuario, fecha y motivo.
- [ ] Carlos recibe el aviso de la devolución.

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
