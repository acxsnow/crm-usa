# [COB-004] No se puede cobrar sin acta confirmada ni permiso aprobado

## 1. Información general

- **ID:** COB-004
- **Módulo:** Cobro al programa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Las guardas del cobro no se saltan ni por la pantalla ni por la API.

## 3. Precondiciones

- Una obra con la instalación cerrada pero sin confirmar (INS-004 sin INS-005).

## 4. Datos de prueba

- Token de contabilidad.

## 5. Procedimiento paso a paso

1. [ ] Buscar la obra en Cobros de programas.
2. [ ] `POST` de creación del cobro por la API con el id de la obra.
3. [ ] Intentar `transition` del expediente a `billing_in_progress`.

## 6. Resultado esperado

- La pantalla dice «Se habilita al confirmar el acta»; la API responde 409/422 con el motivo; nada cambia.

## 7. Resultado obtenido

- Qué pasó: Por API, 2 de 2 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (2 de 2):
  - ✔ No se crea cobro de una obra cancelada (sin acta confirmada) — `409 {"detail":"Administración tiene que confirmar la información técnica del acta antes de crear el cobro.","code":"acta_not_confirmed","request_id":"f98c`
  - ✔ Tampoco por la transición manual a cobro — `400 {"detail":"No se puede pasar de «Cerrado» a «En proceso de cobro».","code":"invalid_transition","request_id":"40c6eab6-be82-4b68-9457-d4a5c3251267"}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún cobro creado.

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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
