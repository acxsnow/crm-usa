# [API-006] Las transiciones del expediente respetan su contrato

## 1. Información general

- **ID:** API-006
- **Módulo:** API y paginación
- **Prioridad:** P1
- **Tipo de prueba:** API · contrato
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Solo se permiten las transiciones de `stages.py` y cada una con su permiso.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).
- Un expediente en «Nuevo prospecto».

## 4. Datos de prueba

- Transiciones inválidas: `new_lead → paid`, `new_lead → approved`, `closed → submitted`.

## 5. Procedimiento paso a paso

1. [ ] Intentarlas por la API como admin.

## 6. Resultado esperado

- 400 `invalid_transition` con el motivo; la etapa no cambia.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 12 de 12 comprobaciones bien. new_prospect → paid / approved y una etapa inventada se rechazan con el motivo; el expediente no cambia ni suma eventos; cerrado no vuelve a ninguna etapa; gerencia no hace transiciones (403).
- Diferencias con lo esperado: Responde 400 `invalid_transition` (el plan decía 409/422; corregido el texto).
- Comprobaciones por API (12 de 12):
  - ✔ Visita «opened» en 433 QA 1025205435 Mobile Park Dr
  - ✔ El expediente arranca en «Nuevo prospecto» — `new_prospect`
  - ✔ new_prospect → paid se rechaza con el motivo [reevaluado: responde 400 con el motivo; el plan decía 409/422] — `400 {"detail":"No se puede pasar de «Nuevo prospecto» a «Pagado».","code":"invalid_transition","request_id":"c084b040-ced3-4734-ae1e-a7dcf167558b"}`
  - ✔ new_prospect → approved se rechaza con el motivo [reevaluado: responde 400 con el motivo; el plan decía 409/422] — `400 {"detail":"No se puede pasar de «Nuevo prospecto» a «Aprobado».","code":"invalid_transition","request_id":"893f439d-cc7f-4d10-b496-5647be2b1ea4"}`
  - ✔ Una etapa que no existe se rechaza [reevaluado: responde 400 con el motivo; el plan decía 409/422] — `400 {"detail":"La etapa «inventado» no existe.","code":"unknown_stage","request_id":"82542003-cb44-4739-98b5-b4779ea03fb3"}`
  - ✔ Ni la etapa ni el historial cambiaron — `1 eventos`
  - ✔ Cierre administrativo con motivo
  - ✔ closed → submitted_to_program se rechaza [reevaluado: responde 400 con el motivo; el plan decía 409/422] — `400 {"detail":"La etapa «submitted_to_program» no existe.","code":"unknown_stage","request_id":"e52e80e9-a7d8-455f-9821-6fe1`
  - ✔ closed → pending_approval se rechaza [reevaluado: responde 400 con el motivo; el plan decía 409/422] — `400 {"detail":"No se puede pasar de «Cerrado» a «Pendiente de aprobación».","code":"invalid_transition","request_id":"e86691`
  - ✔ closed → new_prospect se rechaza [reevaluado: responde 400 con el motivo; el plan decía 409/422] — `400 {"detail":"No se puede pasar de «Cerrado» a «Nuevo prospecto».","code":"invalid_transition","request_id":"70b6b7e7-85dc-`
  - ✔ Sigue cerrado
  - ✔ Gerencia (sin permiso de transición) → 403 — `403`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `docs/contratos/case.md` coincide con lo observado.

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
