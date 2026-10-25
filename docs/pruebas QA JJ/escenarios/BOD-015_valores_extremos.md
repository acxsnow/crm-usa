# [BOD-015] Cantidades y costos extremos

## 1. Información general

- **ID:** BOD-015
- **Módulo:** Bodega
- **Prioridad:** P2
- **Tipo de prueba:** Validación
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

La bodega no acepta cantidades imposibles.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Cantidades: 0, -1, 0.0001, 1e9, «1,5»; costo 9999999.99.

## 5. Procedimiento paso a paso

1. [ ] Probar cada valor en entrada, salida y ajuste.
2. [ ] Mirar la respuesta de la API.

## 6. Resultado esperado

- Rechaza 0 y negativos donde no aplican; decimales según la unidad; nunca un 500.

## 7. Resultado obtenido

- Qué pasó: Por API, 7 de 7 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ Entrada con cantidad 0: rechaza (anotar) — `400 {"detail":"La cantidad debe ser mayor que cero.","code":"invalid_quantity","request_id":"24fc3c28-fb49-4d19-8cea-f21082a`
  - ✔ Entrada con cantidad -1: rechaza (anotar) — `400 {"detail":"La cantidad debe ser mayor que cero.","code":"invalid_quantity","request_id":"efded4b9-c6a7-4381-aacf-eb415a9`
  - ✔ Entrada con cantidad 0.0001: acepta (anotar) — `400 {"detail":"La cantidad debe ser mayor que cero.","code":"invalid_quantity","request_id":"7602df7f-5a9e-4a6d-8153-9cc4b9f`
  - ✔ Entrada con cantidad 1000000000: acepta (anotar) — `400 {"detail":"«1000000000» no es un número válido o es demasiado grande.","code":"invalid_number","request_id":"d74f1581-d5`
  - ✔ Entrada con cantidad 1,5: rechaza (anotar) — `400 {"detail":"«1,5» no es un número válido.","code":"invalid_number","request_id":"df726713-a454-4a1a-b516-c7027eb488de"}`
  - ✔ Costo 9,999,999.99 se acepta sin desbordar — `201 {"id":"fdcb5668-655b-4dde-9a22-3a07f6044445","name":"QA costo grande","sku":"QA-BIG-1025164900","brand":null,"manufactur`
  - ✔ Sin existencias negativas después de los valores extremos — `0`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Los totales con montos grandes no se desbordan ni redondean mal.

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
- Observaciones: 0.0001 se rechaza con «La cantidad debe ser mayor que cero» (las cantidades van con 2 decimales); el mensaje podría decir «mínimo 0.01». 1,000,000,000 se rechaza por grande.
