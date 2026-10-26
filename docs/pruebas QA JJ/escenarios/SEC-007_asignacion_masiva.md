# [SEC-007] Campos que el cliente no debe poder fijar

## 1. Información general

- **ID:** SEC-007
- **Módulo:** Seguridad
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

No se puede cambiar el estado, el dueño ni el rol mandando campos extra.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).

## 4. Datos de prueba

- Cuerpos con `stage_code`, `organization_id`, `created_by`, `status`, `role`, `is_system`.

## 5. Procedimiento paso a paso

1. [ ] Como vendedor, `PATCH` de su expediente con `stage_code: "paid"`.
2. [ ] Como técnico, `PATCH` de su perfil con un rol de admin.
3. [ ] Como contabilidad, emitir una factura con `number` fijado a mano.

## 6. Resultado esperado

- Los campos se ignoran o se rechazan (422); nada cambia de etapa fuera de `transition()`.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 10 de 10 comprobaciones bien. No hay PATCH del expediente (405) y la transición a «paid» del vendedor se rechaza; el técnico no se cambia el rol (403); la factura emitida con número a mano recibe el de la numeración; un rol creado con `is_system` queda normal; crear cliente con dueño y organización ajenos los ignora.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (10 de 10):
  - ✔ Visita «opened» en 432 QA 1025205435 Mobile Park Dr
  - ✔ Vendedor: PATCH del expediente con stage_code=paid no existe (405) — `405`
  - ✔ Vendedor: pasar su expediente a «paid» se rechaza — `403 {"detail":"No tienes permiso para pasar un expediente a «Pagado».","code":"stage_not_allowed_for_role","request_id":"234ea55e-feb2-4ff6-ba88-8e9600e65`
  - ✔ La etapa no cambió — `new_prospect`
  - ✔ Técnico: editarse con un rol de admin → 403 — `403`
  - ✔ Técnico: cambiarse el rol → 403 — `403`
  - ✔ Sigue siendo técnico, con los mismos permisos — `['field_technician']`
  - ✔ Contabilidad: emitir con el número fijado a mano lo ignora (lo pone la numeración) — `200 número=FAC-2026-0001`
  - ✔ Admin: crear un rol con is_system=true lo deja como rol normal — `201 {"code":"qa_sistema","name":"QA sistema","is_system":false,"is_locked":false,"permissions":[],"user_count":0}`
  - ✔ Vendedor: crear cliente con dueño y organización ajenos los ignora — `201 {"id":"ece30942-9f9a-49aa-9254-e50c7465551b","legal_name":"QA 1025205435 creado_por","customer_type":"individual","main_phone":null,"email":null,"webs`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `case_stage_events` sin filas nuevas.

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
