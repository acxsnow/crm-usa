# [REV-002] Devolver al vendedor con motivo y reenviar

## 1. Información general

- **ID:** REV-002
- **Módulo:** Revisión administrativa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La devolución llega al vendedor, que corrige y reenvía sin reiniciar los días.

## 3. Precondiciones

- Un expediente enviado (repetir VEN-004 con la puerta 203, «QA Devuelto Soto»).

## 4. Datos de prueba

- Puerta: dirección «203 QA Mobile Park Dr», espacio «Spc 23», Phoenix, AZ, 85006; motivo «Falta foto del panel».

## 5. Procedimiento paso a paso

1. [ ] Como Andrés, en la revisión tocar **Devolver al vendedor** con el motivo.
2. [ ] Como Vicky: ver el aviso en la campana y el expediente en **Mi día**.
3. [ ] Corregir y **Enviar a revisión** otra vez.
4. [ ] Como Andrés, mirar el contador de días hábiles.

## 6. Resultado esperado

- Devuelto: la tarjeta dice «Devuelto al vendedor» con el motivo.
- Tras reenviar vuelve a «Pendiente de aprobación» y el contador NO vuelve a 0.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial de etapas: envío, devolución y reenvío, cada uno con usuario y fecha.

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
