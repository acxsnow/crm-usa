# [COB-002] El programa rechaza el cobro: corregir y volver a radicar

## 1. Información general

- **ID:** COB-002
- **Módulo:** Cobro al programa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Un rechazo del programa queda con su motivo y se puede corregir sin crear otro cobro.

## 3. Precondiciones

- COB-001 hecho.

## 4. Datos de prueba

- Motivo: «Falta el formulario de reducción de carbono».

## 5. Procedimiento paso a paso

1. [ ] Registrar el rechazo con el motivo (y sin él).
2. [ ] Corregir adjuntando el documento.
3. [ ] Radicar de nuevo.

## 6. Resultado esperado

- «En cobro: rechazado, en corrección» y luego radicado otra vez.
- Sin motivo no se guarda el rechazo.

## 7. Resultado obtenido

- Qué pasó: Por API, 3 de 3 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (3 de 3):
  - ✔ Rechazo sin motivo suficiente se bloquea
  - ✔ Programa rechaza el cobro
  - ✔ Se vuelve a radicar

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un solo cobro para la obra, con el historial de los dos radicados.

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
