# [FIN-002] Proveedor, factura de compra y pago

## 1. Información general

- **ID:** FIN-002
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las cuentas por pagar se registran y pagan con su soporte.

## 3. Precondiciones

- Sesión de `contabilidad@demo-org.com`.

## 4. Datos de prueba

- Proveedor «HOME DEPOT»; factura de USD 350.00 a 30 días.

## 5. Procedimiento paso a paso

1. [ ] **Proveedores y pagos**: crear el proveedor y la factura.
2. [ ] Pagarla con **Adjuntar comprobante**.
3. [ ] Crear otro proveedor con el mismo nombre.

## 6. Resultado esperado

- Saldo en cero tras el pago.
- Anotar si permite el proveedor duplicado.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo quien tiene «Autoriza pagos» puede pagar.

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
