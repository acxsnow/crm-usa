# [VEN-002] No le interesa y no califica

## 1. Información general

- **ID:** VEN-002
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Las dos salidas tempranas quedan registradas con su etapa propia.

## 3. Precondiciones

- Sesión de Vicky.

## 4. Datos de prueba

- Puerta A: dirección «102 QA Mobile Park Dr», espacio «Spc 2», Phoenix, AZ, 85006. Puerta B: dirección «103 QA Mobile Park Dr», espacio «Spc 3», Phoenix, AZ, 85006.

## 5. Procedimiento paso a paso

1. [ ] Tocar una puerta en A con resultado **No le interesa**.
2. [ ] Tocar una puerta en B con resultado **No califica**.
3. [ ] Revisar ambas en Expedientes con «Mostrar puertas cerradas».

## 6. Resultado esperado

- A queda en «No interesado» y B en «No califica», sin datos de cliente.

## 7. Resultado obtenido

- Qué pasó: Por API, 5 de 5 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (5 de 5):
  - ✔ Visita «not_interested» en 202 QA 1025164900 Mobile Park Dr
  - ✔ Queda en «not_interested» sin cliente — `not_interested`
  - ✔ Visita «not_eligible» en 203 QA 1025164900 Mobile Park Dr
  - ✔ Queda en «not_eligible» sin cliente — `not_eligible`
  - ✔ Las salidas tempranas no crean obra ni cliente (obras/clientes) — `0/1`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna de las dos crea obra, cobro ni cliente.

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
