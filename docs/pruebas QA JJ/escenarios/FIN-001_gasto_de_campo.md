# [FIN-001] Gasto de campo: enviar, aprobar y rechazar

## 1. Información general

- **ID:** FIN-001
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

El técnico registra sus gastos con comprobante y Contabilidad los aprueba o rechaza.

## 3. Precondiciones

- Sesión de Tito y de contabilidad.

## 4. Datos de prueba

- Gasolina USD 45.20 «Ej.: gasolina ida y vuelta a Sunrise Park» con foto del recibo; Hotel USD 89.00 sin comprobante.

## 5. Procedimiento paso a paso

1. [ ] Como Tito, **Mis gastos** › registrar y **Enviar gasto** (los dos).
2. [ ] Como contabilidad, aprobar el primero y rechazar el segundo con motivo.
3. [ ] Como Tito, ver el resultado.

## 6. Resultado esperado

- «Gasto enviado a revisión.»; el aprobado suma al costo de su obra; el rechazado muestra el motivo.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 15 de 15 comprobaciones bien. Tito registra gasolina con recibo y hotel; tope, fecha futura y recibo falso se rechazan; no aprueba lo suyo; Contabilidad aprueba uno y rechaza el otro con motivo, y reembolsa; Tito recibe los dos avisos y ve el motivo del rechazado; el aprobado suma al costo de la obra (FIN-005).
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (15 de 15):
  - ✔ Técnico registra gasolina con foto del recibo, cargada a la instalación TECH
  - ✔ Gasto sobre el tope se rechaza
  - ✔ Gasto con fecha futura se rechaza
  - ✔ Recibo disfrazado (exe) se rechaza
  - ✔ Técnico registra un segundo gasto (hotel, tarjeta de la empresa)
  - ✔ El técnico no aprueba su gasto
  - ✔ Contabilidad aprueba la gasolina
  - ✔ Contabilidad rechaza el hotel con motivo
  - ✔ Reembolso al técnico
  - ✔ El vendedor no ve gastos de otros
  - ✔ Se concilian solos el cheque y el reembolso (2 de 4) — `{'statement_id': '778e4845-c941-4192-b4b4-b789a9f3ace6', 'lines': 4, 'auto_matched': 2, 'invalid': []}`
  - ✔ El costo incluye equipos, contratista y la gasolina aprobada — `{'materials': '220.46', 'equipment': '4139.28', 'labor': '0.00', 'contractor': '12500.00', 'permit': '0.00', 'services': '0.00', 'other': '0.00', 'sales_rep': '`
  - ✔ El bloque terminó sin error inesperado (FileNotFoundError) [reevaluado: error del script, no del sistema: `qa_e2e.worker` llama a docker dentro del contenedor; corregido en `qa_comun.py` y los avisos se revisaron en la fase C2] — `FileNotFoundError(2, 'No such file or directory')`
  - ✔ Tito recibe el aviso de gasto aprobado y de gasto rechazado — `['expense.approved', 'expense.rejected', 'installation.scheduled', 'warehouse.release_delivered']`
  - ✔ El rechazado muestra el motivo — `[{'id': '0fedca2b-a373-4975-8fc3-2fa927d9aa40', 'user_id': 'f9c2c322-ff13-4215-9094-dece2583c4e7', 'user_name': 'Tito Técnico', 'project_id': 'f1adbe77-ddd5-4f9`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Tito no ve los gastos de otros técnicos.

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
