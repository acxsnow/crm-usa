# [INS-003] Salida de material con la lista «3 ton desde cero»

## 1. Información general

- **ID:** INS-003
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

El técnico pide el material con la lista predefinida, bodega lo autoriza y lo entrega, y la existencia baja.

## 3. Precondiciones

- INS-001 hecho (obra de Carlos).
- Anotar la existencia de 3 artículos de la lista (por ejemplo los SKU 85980, 3496 y 1578).

## 4. Datos de prueba

- Lista «Instalación 3 ton desde cero» (46 renglones).

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, en la obra: **Agregar material** › **Cargar desde una lista predefinida** › la lista 3 ton.
2. [ ] Quitar un renglón no obligatorio y bajar la cantidad de otro.
3. [ ] **Guardar y enviar a autorizar**.
4. [ ] Como administración, menú **Bodega** › **Salidas de bodega** › **Por autorizar**: abrirla y **Autorizar**.
5. [ ] **Entregar** (la salida pasa a «Entregada»).
6. [ ] Volver a mirar la existencia de los 3 artículos.

## 6. Resultado esperado

- La salida recibe su número SAL-… al enviarse.
- Al entregar, la existencia de bodega baja exactamente en lo entregado y ese material queda cargado a la obra o a la camioneta de Carlos (anotar dónde lo muestra).

## 7. Resultado obtenido

- Qué pasó: Por API, 13 de 13 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (13 de 13):
  - ✔ Un borrador sin renglones se rechaza (422) — `422`
  - ✔ El técnico arma el borrador de salida para la obra
  - ✔ Cargar la lista «3 ton desde cero»
  - ✔ La lista agrega sus renglones (46, menos el que ya estaba) — `45`
  - ✔ Guardar y enviar a autorizar
  - ✔ Recibe su número SAL- — `SAL-2026-0001`
  - ✔ Bodega la autoriza
  - ✔ Bodega la entrega
  - ✔ Existencia baja exactamente en lo entregado (Z & Y-Series Smart Communicating WiFi Th) — `antes=1.0 entregado=1.0 ahora=0.0`
  - ✔ Existencia baja exactamente en lo entregado (B-Series Air Handler Multi Position 3 To) — `antes=1.0 entregado=1.0 ahora=0.0`
  - ✔ Existencia baja exactamente en lo entregado (B-Series Heat Pump Condenser 2-3 Ton 20 ) — `antes=1.0 entregado=1.0 ahora=0.0`
  - ✔ Movimientos `salida` con la obra — `46`
  - ✔ El material entregado quedó cargado a la obra — `46`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Movimientos de bodega: una `salida` por renglón con el usuario y la obra.
- [ ] El equipo con serial (85980) pide el serial al entregar.
- [ ] El costo de la obra en Rentabilidad incluye ese material.

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
