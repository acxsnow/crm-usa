# [REV-002] Devolver al vendedor con motivo y reenviar

## 1. Información general

- **ID:** REV-002
- **Módulo:** Revisión administrativa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integración
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 8 de 8 comprobaciones bien.
- Diferencias con lo esperado: Falta ver en pantalla la tarjeta «Devuelto al vendedor» con el motivo.
- Comprobaciones por API (8 de 8):
  - ✔ Devolver al vendedor
  - ✔ El vendedor puede editar el devuelto
  - ✔ Reenviar con el rechazado vigente se bloquea
  - ✔ Vendedor sube la foto de nuevo
  - ✔ Guarda el paso con la foto nueva
  - ✔ Reenviar a revisión
  - ✔ Vuelve a «en revisión» — `pending_review`
  - ✔ El contador de días no se reinicia al reenviar (submitted_at igual) — `2026-10-25T16:49:16.679272Z → 2026-10-25T16:49:16.679272Z`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
