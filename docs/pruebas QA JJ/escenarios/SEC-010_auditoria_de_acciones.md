# [SEC-010] Bitácora de auditoría de acciones sensibles

## 1. Información general

- **ID:** SEC-010
- **Módulo:** Seguridad
- **Prioridad:** P1
- **Tipo de prueba:** Auditoría
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj + D-020 (base QA del lote 3)

## 2. Objetivo

Las acciones de dinero, permisos y datos personales quedan con quién, qué y cuándo.

## 3. Precondiciones

- Haber ejecutado AUTH-007, PAR-002, BOD-009 e INS-008.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Menú **Auditoría**: filtrar por cada acción.
2. [ ] Intentar abrirla como gerencia y como técnico.

## 6. Resultado esperado

- Cada acción aparece con usuario, fecha, antes y después.
- La ven quienes tienen «Ver la auditoría» (Administrador, Administración, Contabilidad y Gerencia); el técnico y el vendedor no.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 16 de 16 comprobaciones bien. Permisos de un rol, desactivar y activar una persona, autorización, corrección y borrado de un cliente, anulación y pago de factura, pago a proveedor, autorización de salida, asignación de técnico e ingreso fallido: cada uno con quién, cuándo, el antes (cuando aplica) y el después. La auditoría no mostraba el antes y el después aunque la base los guardaba: D-020, corregido (API y columna «Cambios»).
- Diferencias con lo esperado: El plan decía que solo el Administrador la ve: la ven quienes tienen `audit.read` (Administrador, Administración, Contabilidad y Gerencia, según la matriz); el técnico y el vendedor reciben 403 (corregido el texto). Falta ver la columna «Cambios» en pantalla.
- Comprobaciones por API (16 de 16):
  - ✔ Permisos de un rol (roles.updated): con usuario, fecha, antes y detalle — `2 eventos; antes={'name': 'Gerencia', 'permissions': ['attendance.clock', 'attendance.dashboard', 'audit.read', 'cases.read_all', 'custom después={'name': 'Gere`
  - ✔ Desactivar a una persona (users.deactivated): con usuario, fecha y detalle — `2 eventos; antes={'status': 'active'} después={'status': 'inactive'}`
  - ✔ Activarla otra vez (users.activated): con usuario, fecha y detalle — `1 eventos; antes={'status': 'inactive'} después={'status': 'active'}`
  - ✔ Autorización de datos del cliente (customer.consent_recorded): con usuario, fecha y detalle — `4 eventos; antes=None después={'source': 'customer_create', 'version': '2026.1'}`
  - ✔ Corrección de un dato personal (customer.updated): con usuario, fecha y detalle — `1 eventos; antes=None después={'main_phone': '(602) 555-0202'}`
  - ✔ Borrado de un cliente (customer.deleted): con usuario, fecha, antes y detalle — `1 eventos; antes={'legal_name': 'QA 1026005936 Auditoría', 'email': None, 'main_phone': '(602) 555-0202'} después=None`
  - ✔ Anulación de factura (invoices.voided): con usuario, fecha y detalle — `1 eventos; antes=None después={'reason': 'Error en el valor'}`
  - ✔ Pago de factura (invoices.payment_recorded): con usuario, fecha y detalle — `5 eventos; antes=None después={'amount': '300.00', 'balance': '0.00'}`
  - ✔ Pago a proveedor (payables.payment_recorded): con usuario, fecha y detalle — `2 eventos; antes=None después={'supplier': 'QA HOME DEPOT C2 1025214209', 'amount': '350.00', 'invoices': 1}`
  - ✔ Autorización de salida de bodega (warehouse.release_authorized): con usuario, fecha y detalle — `1 eventos; antes=None después={'number': 'SAL-2026-0001'}`
  - ✔ Asignación y cambio de técnico (projects.installation_scheduled): con usuario, fecha, antes y detalle — `16 eventos; antes={'technician': None, 'scheduled_date': None} después={'technician': '917b4cfb-2bc8-45c1-bd64-c199948a5132', 'scheduled_date': '2026-10-30'}`
  - ✔ Ingreso fallido (auth.login.failed): con usuario, fecha y detalle — `2 eventos; antes=None después={'reason': 'invalid_credentials'}`
  - ✔ gerencia → 200 — `200`
  - ✔ conta → 200 — `200`
  - ✔ tecnico → 403 — `403`
  - ✔ vendedor → 403 — `403`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La bitácora no se puede editar ni borrar desde la API.

## 10. Resultado final

- [ ] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-020 | La auditoría no muestra el antes y el después | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
