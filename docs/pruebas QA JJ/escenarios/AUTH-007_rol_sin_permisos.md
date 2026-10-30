# [AUTH-007] Rol nuevo sin permisos marcados

## 1. Información general

- **ID:** AUTH-007
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Un rol recién creado no abre nada hasta que se le den permisos.

## 3. Precondiciones

- Sesión de admin.

## 4. Datos de prueba

- Rol «QA sin permisos»; usuario invitado `sinrol@demo-org.com`.

## 5. Procedimiento paso a paso

1. [ ] Menú **Roles y permisos**: crear el rol «QA sin permisos» sin marcar nada.
2. [ ] Invitar a `sinrol@demo-org.com` con ese rol y aceptar la invitación (como en AUTH-004).
3. [ ] Entrar como `sinrol@demo-org.com` y recorrer el menú.
4. [ ] Escribir a mano /cases, /projects y /invoices.
5. [ ] Como admin, darle al rol solo «Ver clientes» y volver a entrar.

## 6. Resultado esperado

- Sin permisos solo ve el Inicio vacío; todo lo demás responde 403.
- Con «Ver clientes» aparece solo Clientes.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 9 de 9 comprobaciones bien. El rol sin permisos no trae permisos ni módulos y recibe 403 en expedientes, obras, facturas, clientes, bodega y proveedores; con «Ver clientes» trae solo `customers.read`, el módulo de clientes, y solo Clientes abre.
- Diferencias con lo esperado: Falta ver el menú en pantalla (Inicio vacío y luego solo Clientes).
- Comprobaciones por API (9 de 9):
  - ✔ Crear el rol «QA sin permisos» sin marcar nada — `201 {"code":"qa_sin_permisos","name":"QA sin permisos","is_system":false,"is_locked":false,"permissions":[],"user_count":0}`
  - ✔ Invitar a sinrol@demo-org.com con ese rol — `201 {"id":"f462a157-ee05-472b-a2b0-750212be8707","email":"sinrol@demo-org.com","full_name":"QA Sin Rol","status":"invited","roles":["qa_sin_permisos"],"la`
  - ✔ Aceptar la invitación de sinrol — `200 {"id":"f462a157-ee05-472b-a2b0-750212be8707","email":"sinrol@demo-org.com","full_name":"QA Sin Rol","organization_id":"a86681e1-01d1-48b8-a9c0-47fec95`
  - ✔ Sin permisos: la sesión no trae permisos ni módulos — `[] []`
  - ✔ Expedientes, obras, facturas, clientes, bodega y proveedores → 403 — `{'/cases': 403, '/projects': 403, '/invoices': 403, '/customers': 403, '/warehouse/items': 403, '/payables/suppliers': 403}`
  - ✔ Admin le da al rol solo «Ver clientes»
  - ✔ Ahora la sesión trae solo customers.read — `['customers.read']`
  - ✔ Y el menú solo el módulo de clientes — `['customers']`
  - ✔ Clientes abre (200) y lo demás sigue en 403 — `{'/cases': 403, '/projects': 403, '/invoices': 403, '/customers': 200, '/warehouse/items': 403, '/payables/suppliers': 403}`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- Un rol sin permisos solo ve Inicio y escribir /cases, /projects, /invoices o /customers lo devuelve al inicio; al darle «Ver clientes» aparece solo Clientes.
- Comprobaciones (3 de 3):
  - ✔ Sin permisos el menú solo trae Inicio (['Inicio']) — `['Inicio']`
  - ✔ Escribir /cases, /projects, /invoices y /customers lo devuelve al inicio — `[]`
  - ✔ Con «Ver clientes» aparece solo Clientes (['Inicio', 'Clientes']) — `['Inicio', 'Clientes']`
- Capturas:
  - [sin-permisos.jpg](../evidencias/pantalla/AUTH-007/sin-permisos.jpg)
  - [solo-clientes.jpg](../evidencias/pantalla/AUTH-007/solo-clientes.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El cambio de permisos se refleja al volver a entrar, sin reiniciar nada.
- [ ] Auditoría registra la creación del rol y el cambio de permisos.

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
