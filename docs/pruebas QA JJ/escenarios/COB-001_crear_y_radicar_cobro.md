# [COB-001] Crear el cobro al programa y radicarlo

## 1. Información general

- **ID:** COB-001
- **Módulo:** Cobro al programa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial de etapas: la entrada a cobro la hace `_sync_case` (no un cambio manual).
- [ ] Montos en Decimal: el valor del cobro coincide con la tarifa del programa al centavo.

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
