# [COB-001] Crear el cobro al programa y radicarlo

## 1. Información general

- **ID:** COB-001
- **Módulo:** Cobro al programa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Con el acta confirmada y la inspección aprobada, el cobro nace, se radica y mueve el expediente a «En proceso de cobro».

## 3. Precondiciones

- INS-006 hecho.
- Programa con su cobro configurado (procedimiento P-03).
- Sesión de `contabilidad@demo-org.com`.

## 4. Datos de prueba

- Referencia de radicado `AZ-RAD-0001`.

## 5. Procedimiento paso a paso

1. [ ] Menú **Facturación y cobros** › **Cobros de programas**: ubicar la obra en «Listo para crear el cobro».
2. [ ] **Crear cobro**; revisar el **Checklist para radicar** (lo que comprueba el sistema y lo que confirma una persona).
3. [ ] Intentar radicar con un punto manual sin marcar.
4. [ ] Marcarlo y radicar con la referencia.

## 6. Resultado esperado

- Sin el checklist completo no radica.
- Radicado: «En cobro: radicado, esperando pago» y el expediente en cobro.

## 7. Resultado obtenido

- Qué pasó: Por API, 5 de 5 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (5 de 5):
  - ✔ Elegibilidad del proyecto
  - ✔ Crear cobro AZ_EFFICIENCY
  - ✔ Cobro duplicado del mismo programa se bloquea
  - ✔ Radicar el cobro
  - ✔ El expediente pasó a «En cobro» — `billing_in_progress`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial de etapas: la entrada a cobro la hace `_sync_case` (no un cambio manual).
- [ ] Montos en Decimal: el valor del cobro coincide con la tarifa del programa al centavo.

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
- Observaciones: Antes hubo que cargar la tarifa vigente y la zona de cobro del programa (P-03); sin ellas el cobro dice «sin tarifa» o «fuera de zona».
