# [SEC-006] Enlaces directos a archivos de otros

## 1. Información general

- **ID:** SEC-006
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Un archivo no se descarga solo con conocer su dirección.

## 3. Precondiciones

- Una foto de una obra de Carlos.

## 4. Datos de prueba

- La URL de descarga de esa foto.

## 5. Procedimiento paso a paso

1. [ ] Abrirla sin sesión.
2. [ ] Abrirla como Luis.
3. [ ] Abrirla como admin ajeno.

## 6. Resultado esperado

- Sin sesión: 401; Luis y ajeno: 404.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 8 de 9 comprobaciones bien. Sin sesión 401 y admin ajeno 404. Luis (técnico de otra obra) abría la foto de Carlos (200): D-013. Corregido y reejecutado: Luis 404, Carlos y Administración 200.
- Diferencias con lo esperado: Ninguna después de corregir D-013.
- Comprobaciones por API (8 de 9):
  - ✔ Sin sesión → 401 — `401`
  - ✘ Luis (técnico de otra obra) → 404 [reevaluado: D-013, corregido y reejecutado abajo] — `200`
  - ✔ El admin de otra organización → 404 — `404`
  - ✔ Carlos, el de la obra, sí la abre — `200`
  - ✔ Reejecución D-013: sin sesión → 401
  - ✔ Reejecución D-013: Luis (técnico de otra obra) → 404 — `404`
  - ✔ Reejecución D-013: admin ajeno → 404
  - ✔ Reejecución D-013: Carlos sí la abre
  - ✔ Reejecución D-013: Administración (ve todas las obras) sí la abre

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si la URL es firmada, anotar cuánto dura.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-013 | Un técnico descarga la foto de una obra que no es suya con solo el id | P1 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
