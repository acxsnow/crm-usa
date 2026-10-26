# [AUTH-008] Quitar un permiso a un rol con usuarios conectados

## 1. Información general

- **ID:** AUTH-008
- **Módulo:** Acceso y sesión
- **Prioridad:** P2
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Revocar un permiso corta el acceso en la siguiente operación, no días después.

## 3. Precondiciones

- Contabilidad con sesión abierta en Banca o Proveedores.

## 4. Datos de prueba

- Rol Contabilidad, permisos «Gestionar proveedores» (`suppliers.manage`) y «Aprobar pagos» (`payables.approve`): cualquiera de los dos deja crear proveedores.

## 5. Procedimiento paso a paso

1. [ ] Entrar como `contabilidad@demo-org.com` y abrir **Proveedores y pagos**.
2. [ ] En otra ventana, como admin, quitar `suppliers.manage` y `payables.approve` al rol Contabilidad.
3. [ ] Como contabilidad, recargar la pantalla y tratar de crear un proveedor.
4. [ ] Como admin, devolver el permiso.

## 6. Resultado esperado

- Tras quitar el permiso, la siguiente acción responde 403 (como máximo al renovar el token de 15 min).
- Al devolverlo vuelve a funcionar.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 6 de 6 comprobaciones bien. Con la sesión abierta de Contabilidad, quitar `suppliers.manage` y `payables.approve` al rol hace que crear un proveedor responda 403 en la siguiente acción; al devolverlos funciona sin volver a entrar.
- Diferencias con lo esperado: El plan nombraba `payables.manage`, pero crear proveedores exige `suppliers.manage` o `payables.approve` (corregido el texto).
- Comprobaciones por API (6 de 6):
  - ✔ Contabilidad abre Proveedores y pagos — `200`
  - ✔ Contabilidad crea proveedores con ['suppliers.manage'] — `['accounting.export', 'attendance.clock', 'attendance.dashboard', 'audit.read', 'bankfeeds.manage', 'billing.configure', 'billing.submit', 'cases.read_all', 'cu`
  - ✔ Admin quita esos permisos a Contabilidad
  - ✔ Con la misma sesión, crear un proveedor → 403 en la siguiente acción — `403`
  - ✔ Admin devuelve los permisos
  - ✔ Vuelve a funcionar sin volver a entrar — `201 {"id":"86e300a4-6594-434b-92b9-e31433064cb7","name":"QA 1025210655 Con permiso","legal_name":null,"tax_id":null,"kinds":`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Anotar cuánto tardó en aplicarse el cambio (inmediato o al renovar).

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

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
