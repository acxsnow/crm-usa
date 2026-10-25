# Plan de regresión

Qué volver a correr después de cada corrección, para confirmar que lo corregido no rompió otra cosa.

## 1. Siempre, antes de pasar una corrección a QA (automático)

Desde la raíz del repo, con Docker arriba:

| Qué | Comando | Debe dar |
|---|---|---|
| Pruebas del backend | `docker compose exec -T api python -m pytest -q -p no:cacheprovider` | 0 fallos (CI además exige cobertura ≥ 70 %) |
| Tipos y build del frontend | `docker compose exec -T frontend npm run build` | sin errores |
| Reglas de hooks de React | `python frontend/scripts/check_hooks.py` | sin hallazgos |
| Lint del backend (CI) | `docker compose exec -T api python -m ruff check app/api app/db app/modules/crm app/modules/field_ops app/modules/users` (lo mismo que corre CI) | sin hallazgos |

La integración continua de GitHub Actions corre lo mismo en `main`, `CadenaB` y `cadenaA`.

## 2. Humo: después de cada corrección (4 h 15 min)

El recorrido mínimo del negocio, de la puerta al pago:

- AUTH-001
- VEN-004
- REV-003
- INS-003
- INS-004
- INS-005
- COB-001
- COB-003
- BOD-006
- SEC-001
- API-001

## 3. Por módulo tocado

| Si la corrección tocó… | Reejecutar además |
|---|---|
| `auth`, `users`, `roles`, `shared/permissions.py` | AUTH-*, SEC-003, SEC-007, FIN-006, TEC-002 |
| `cases`, `crm`, `programs` | VEN-*, REV-*, API-006, SEC-008 |
| `field_ops`, `projects` | INS-*, TEC-*, COB-004 |
| `warehouse` | BOD-*, INS-003, INS-014, FIN-005 |
| `billing`, `payments` | COB-*, PAR-*, CON-002 |
| `finance`, `banking` | FIN-* |
| `attendance`, `map` | TUR-* |
| `notifications`, `search` | NOT-*, BUS-* |
| `shared/files` | SEC-005, SEC-006, INS-004, INS-015 |
| `shared/pagination.py` o cualquier listado | API-001 a API-003 |

## 4. Antes de salir a producción: todos los P0 (35 escenarios, 12 h 00 min)

| ID | Escenario | Min |
|---|---|---|
| AUTH-001 | Ingreso válido con cada uno de los 6 roles | 15 |
| VEN-004 | Venta completa: abrió, formulario, autorización, firma y envío | 35 |
| VEN-006 | Un vendedor no ve los expedientes del otro | 15 |
| REV-003 | Aprobar con el código del programa: nace la obra | 15 |
| REV-006 | El vendedor no puede aprobar su propio expediente (SEG-07) | 10 |
| INS-001 | Asignar técnico y fecha a la obra | 15 |
| INS-002 | Permiso municipal: sin permiso no se instala | 20 |
| INS-003 | Salida de material con la lista «3 ton desde cero» | 25 |
| INS-004 | Instalación completa: jornada, checklist, equipos y acta firmada | 40 |
| INS-005 | Administración devuelve el acta al técnico y luego la confirma | 20 |
| INS-008 | Cambiar el técnico de una obra en curso (rotación) | 20 |
| INS-010 | El técnico llega y el cliente no estaba (visita fallida) | 25 |
| INS-012 | Cancelar una obra y reintegrar el material | 30 |
| TEC-001 | Cada técnico ve solo su agenda y sus obras | 15 |
| TEC-002 | El técnico no autoriza salidas ni confirma su propia acta | 15 |
| BOD-001 | La carga inicial cuadra con los PDF de AC Pro | 20 |
| BOD-004 | Entrega parcial y rechazo de una salida | 20 |
| BOD-005 | Pedir más de lo que hay en bodega | 15 |
| BOD-006 | Reintegro: el material vuelve de la camioneta a bodega | 20 |
| BOD-016 | Dos entregas a la vez sobre la misma existencia | 20 |
| COB-001 | Crear el cobro al programa y radicarlo | 20 |
| COB-003 | El programa paga: expediente pagado y cerrado | 15 |
| COB-004 | No se puede cobrar sin acta confirmada ni permiso aprobado | 15 |
| PAR-002 | Emitir y anular una factura | 20 |
| TUR-002 | Marcar entrada y salida con GPS | 15 |
| TUR-010 | El técnico no ve la asistencia ni la ubicación de otros | 10 |
| SEC-001 | Aislamiento entre organizaciones (IDOR) | 30 |
| SEC-002 | API sin token, con token vencido o alterado | 15 |
| SEC-003 | Cada rol contra cada grupo de rutas | 45 |
| SEC-004 | Inyección SQL y XSS en formularios y filtros | 25 |
| SEC-005 | Subida de archivos: tipo, tamaño y nombre | 20 |
| SEC-006 | Enlaces directos a archivos de otros | 15 |
| SEC-008 | Autorización de datos en los cuatro puntos de captura | 25 |
| API-001 | Paginación: límite por defecto, máximo y total | 20 |
| CON-001 | Doble clic y reintentos en acciones que crean cosas | 20 |

Más PAR-004 y FIN-004 cuando estén las llaves de prueba de Stripe/Plaid.

## 5. Reglas

- Cada reejecución se anota en la sección 12 del escenario y en la columna «Reejecución» del índice.
- Si la regresión encuentra un fallo nuevo, es un defecto nuevo (`D-###`), no se reabre el anterior.
- La base se reinicia (`04_DATOS_DE_PRUEBA.md`) antes de la regresión completa de P0.
