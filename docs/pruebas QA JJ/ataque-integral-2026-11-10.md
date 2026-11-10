# Ataque integral a la app · 9 y 10 nov 2026

Corrido por Claude contra la app local real: Postgres, los 6 roles y una segunda organización, con los usuarios demo. Los scripts están en `ejecucion/` y se pueden repetir; cada corrida crea datos nuevos con el prefijo «QA».

## Qué se hizo

| Parte | Script | Resultado |
|---|---|---|
| Barrido de toda la API: cada ruta con cada rol, sin sesión y con datos basura | `barrido_api.py` | 476 rutas, 11.829 llamadas |
| Acceso, usuarios y roles | `qa_acceso.py` | 43 / 43 |
| Venta: visita, formulario, documentos, revisión y cliente | `qa_venta.py` | 66 / 67 (1 decisión pendiente) |
| Campo: permiso, orden, acta, inspección, visita fallida y cancelación | `qa_campo.py` | 87 / 88 (1 marca del propio script) |
| Bodega: existencias, salidas, seriales y costos anotados | `qa_bodega.py` | 47 / 47 |
| Turnos, extras, nómina y mapa | `qa_turnos.py` | 37 / 37 en la primera corrida |
| Gastos, proveedores, conciliación, reportes y contabilidad | `qa_finanzas_conta.py` | 42 / 42 |
| Avisos, campañas, webhooks y bajas | `qa_avisos.py` | 20 / 22 (2 que no son defectos) |
| Cobro y rentabilidad (9 nov) | `qa_cobro_rentabilidad.py`, `cobro_rentabilidad_pantalla.py` | 182 / 182 y 14 / 14 |
| Recorrido completo de punta a punta, de regresión | `backend/scripts/qa_e2e.py` | 445 / 445 |

## Barrido de toda la API

- **Errores 500:** ninguna caída del servidor por datos malos. Las únicas respuestas 5xx son de «La banca conectada no está configurada»: en local no hay llaves de Plaid, y es un aviso de configuración, no una caída.
- **Rutas abiertas:** todas las rutas privadas piden sesión. Las que no la piden son públicas a propósito: ingreso, restablecer clave, invitación, enlaces del cliente y webhooks.
- **Fugas entre organizaciones:** ninguna. Se probaron 59 rutas de lectura con ids reales de 19 tipos de registro, pedidas desde la otra organización.

## Defectos encontrados y corregidos

Cada uno quedó con su prueba automática.

| # | Defecto | Arreglo | Prueba |
|---|---|---|---|
| 1 | La devolución de material a bodega no se restaba del costo de la obra; la rentabilidad no coincidía con la contabilidad. | `warehouse/costing.warehouse_costs` resta la devolución con la misma regla del asiento. | `test_field_visits.py::test_lo_que_vuelve_a_bodega_sale_del_costo_de_la_obra` |
| 2 | El Administrador se podía desactivar a sí mismo, y también al único Administrador activo; la empresa quedaba sin quien la administre. | `users/service.set_user_active_state` (`cannot_deactivate_self` y `last_admin`). | `test_users_roles.py::test_nobody_deactivates_themselves_nor_the_last_admin` y `test_the_last_active_admin_is_not_deactivated` |
| 3 | En una obra cancelada se seguían subiendo fotos. | `field_ops/service.upload_evidence` (`project_cancelled`). | `test_field_visits.py::test_en_una_obra_cancelada_no_se_suben_evidencias` |
| 4 | El traslado de bodega no tenía tope: dejaba la bodega en negativo y aceptaba la misma ubicación como origen y destino. | `warehouse/service.record_movement` (`transfer_exceeds_stock` y `transfer_same_location`). | `test_warehouse_security.py::test_no_se_traslada_mas_de_lo_que_hay_ni_a_la_misma_ubicacion` |
| 5 | Borrar las ubicaciones con el id de alguien de otra organización respondía 200 y dejaba ese id en la auditoría. No borraba nada ajeno. | `attendance/mapdata.purge_user_locations` responde 404. | `test_attendance_security.py::test_la_retencion_borra_coordenadas_y_deja_el_evento` |
| 6 | Un reporte con las fechas al revés salía vacío, como si no hubiera nada. | `finance/router._check_range` (`report_range_inverted`). | `test_finance.py` |

## Para decidir con el cliente

1. **El vendedor ve todos los clientes de la empresa.** Cualquier vendedor ve el directorio completo de clientes, con nombre, teléfono y dirección (`customers.read` sin recorte). No está decidido en ningún documento. Restringirlo a los clientes de sus expedientes reduce la exposición de datos personales (CCPA), pero cambia lo que hoy ve en el menú «Clientes».
2. **Administración cambia los datos bancarios de los proveedores.** Es consecuencia del pedido del 4 de noviembre, porque Administración recibió los permisos de Contabilidad. Cambiar la cuenta de un proveedor es un riesgo de fraude conocido. Lo mitiga que cada cambio avisa a quien aprueba los pagos y queda en la auditoría.

## Lo que no es un defecto, aunque saliera marcado

- **«El técnico ve la obra»:** la obra se la asignó el mismo script.
- **El técnico en el mapa:** solo se ve a sí mismo, como se acordó.
- **El enlace de baja:** muestra la confirmación sin revisar el enlace, para que los antivirus del correo no den de baja a nadie. Al confirmar con un enlace inventado responde «Enlace no válido».
- **Otra organización lanzando nuestra campaña:** la frena la validación (422) y no se lanza.

## Lo que no cubre

- **Stripe y Plaid:** las cuentas reales no se probaron; no hay llaves en local.
- **Render:** el ataque corrió en local.
- **Revisión visual:** no se miró pantalla por pantalla. La parte de pantalla se probó en cobro y rentabilidad (9 nov) y en los pedidos del cliente (5 nov).
- **Prueba de intrusión profesional:** esto no lo es.
