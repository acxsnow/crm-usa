# [SEC-003] Cada rol contra cada grupo de rutas

## 1. Información general

- **ID:** SEC-003
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 45 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Confirmar por la API la matriz de `05_MATRIZ_PERMISOS.md` (no solo el menú).

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).
- La matriz de permisos.

## 4. Datos de prueba

- Una ruta de lectura y una de escritura por módulo (la matriz trae la lista).

## 5. Procedimiento paso a paso

1. [ ] Con el token de cada uno de los 6 roles, llamar las rutas de la matriz.
2. [ ] Marcar en la matriz lo obtenido.

## 6. Resultado esperado

- Coincide con la matriz; cualquier diferencia es un defecto P0.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 21 de 21 comprobaciones bien. Las sesiones de los 6 roles traen los permisos de la matriz. 406 rutas con permiso declarado: cada rol recibe 403 en todas las que no le tocan y abre sin 401/403/5xx las lecturas que sí. De las 19 rutas sin `require_permission`, 15 son públicas o de sesión (`/auth`, `/public`, `/privacy`, `/health`, `/webhooks`) y 4 se revisaron a mano: `/me/programs` y `/me/program-options` devuelven solo lo del usuario, y `unsubscribe/{token}` es la baja pública de campañas por enlace.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (21 de 21):
  - ✔ organization_admin: los permisos que trae la sesión son los de la matriz (91) — `faltan [] · sobran []`
  - ✔ admin_staff: los permisos que trae la sesión son los de la matriz (58) — `faltan [] · sobran []`
  - ✔ salesperson: los permisos que trae la sesión son los de la matriz (14) — `faltan [] · sobran []`
  - ✔ field_technician: los permisos que trae la sesión son los de la matriz (15) — `faltan [] · sobran []`
  - ✔ accounting: los permisos que trae la sesión son los de la matriz (32) — `faltan [] · sobran []`
  - ✔ management: los permisos que trae la sesión son los de la matriz (21) — `faltan [] · sobran []`
  - ✔ Rutas con permiso declarado: 406 — `406`
  - ✔ Rutas sin `require_permission` (19): las públicas y de sesión, y estas otras para revisar a mano (4) — `GET /api/v1/me/programs; GET /api/v1/me/program-options; GET /api/v1/unsubscribe/{token}; POST /api/v1/unsubscribe/{token}`
  - ✔ organization_admin: 0 rutas sin su permiso responden 403 — `todas 403`
  - ✔ organization_admin: 177 lecturas con su permiso responden sin 401/403/5xx — `ninguna falla`
  - ✔ admin_staff: 104 rutas sin su permiso responden 403 — `todas 403`
  - ✔ admin_staff: 144 lecturas con su permiso responden sin 401/403/5xx — `ninguna falla`
  - ✔ salesperson: 341 rutas sin su permiso responden 403 — `todas 403`
  - ✔ salesperson: 40 lecturas con su permiso responden sin 401/403/5xx — `ninguna falla`
  - ✔ field_technician: 311 rutas sin su permiso responden 403 — `todas 403`
  - ✔ field_technician: 60 lecturas con su permiso responden sin 401/403/5xx — `ninguna falla`
  - ✔ accounting: 197 rutas sin su permiso responden 403 — `todas 403`
  - ✔ accounting: 139 lecturas con su permiso responden sin 401/403/5xx — `ninguna falla`
  - ✔ management: 269 rutas sin su permiso responden 403 — `todas 403`
  - ✔ management: 121 lecturas con su permiso responden sin 401/403/5xx — `ninguna falla`
  - ✔ Sin sesión → 401 — `401`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `tests/test_permissions*.py` pasa (la prueba automática que ya cubre rutas sin permiso).

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-014 | Siete permisos del catálogo no controlan nada | P3 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Las escrituras permitidas no se llamaron (crearían datos): se prueban en sus escenarios. La columna «Verificado en SEC-003» de `05_MATRIZ_PERMISOS.md` queda ✔ para los permisos que exige alguna ruta.
