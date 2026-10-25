# [REV-005] Cerrar un expediente desde cualquier etapa

## 1. Información general

- **ID:** REV-005
- **Módulo:** Revisión administrativa
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Cierre administrativo con motivo obligatorio.

## 3. Precondiciones

- Un expediente en «Nuevo prospecto» (puerta 205, «QA Cierre Paz»).

## 4. Datos de prueba

- Puerta: dirección «205 QA Mobile Park Dr», espacio «Spc 25», Phoenix, AZ, 85006; motivo «Cliente se mudó».

## 5. Procedimiento paso a paso

1. [ ] Como Andrés, en la revisión tocar **Cerrar expediente…**, primero sin motivo y luego con él.
2. [ ] Como Vicky, buscar el expediente.

## 6. Resultado esperado

- Sin motivo no cierra; con motivo queda «Cerrado» y ya no se edita.

## 7. Resultado obtenido

- Qué pasó: Por API, 7 de 7 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ Vendedor NO puede cerrar
  - ✔ Cierre administrativo desde «En espera»
  - ✔ Visita «opened» en 305 QA 1025164900 Mobile Park Dr
  - ✔ Cerrar un «Nuevo prospecto» sin motivo se bloquea
  - ✔ Cerrar con motivo
  - ✔ Cerrado ya no se edita
  - ✔ No se creó obra — `0`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] No se creó obra ni cobro.

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
