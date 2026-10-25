# [TEC-002] El técnico no autoriza salidas ni confirma su propia acta

## 1. Información general

- **ID:** TEC-002
- **Módulo:** Técnicos
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Separación de funciones en campo, también por la API.

## 3. Precondiciones

- Una salida «Por autorizar» y un acta cerrada del mismo técnico.

## 4. Datos de prueba

- Token del técnico.

## 5. Procedimiento paso a paso

1. [ ] Como técnico, buscar los botones Autorizar, Entregar y Confirmar información técnica.
2. [ ] Llamar por la API a autorizar la salida y a confirmar el acta con su token.

## 6. Resultado esperado

- La pantalla no los ofrece; la API responde 403 y nada cambia.

## 7. Resultado obtenido

- Qué pasó: Por API, 5 de 5 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (5 de 5):
  - ✔ El técnico no puede confirmar su propia acta
  - ✔ El técnico no puede autorizar
  - ✔ Nadie autoriza la salida que pidió → 403 — `403 {"detail":"Otra persona debe autorizar esta salida: tú la pediste.","code":"release_self_authorization","request_id":"7d`
  - ✔ El técnico no autoriza su salida
  - ✔ El técnico no entrega

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún movimiento de bodega creado.

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
