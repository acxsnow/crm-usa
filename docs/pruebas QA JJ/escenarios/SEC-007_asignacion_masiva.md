# [SEC-007] Campos que el cliente no debe poder fijar

## 1. Información general

- **ID:** SEC-007
- **Módulo:** Seguridad
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `case_stage_events` sin filas nuevas.

## 10. Resultado final

- [ ] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
