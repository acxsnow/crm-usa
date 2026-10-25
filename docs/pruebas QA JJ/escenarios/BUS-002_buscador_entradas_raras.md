# [BUS-002] Buscador con entradas raras

## 1. Información general

- **ID:** BUS-002
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P2
- **Tipo de prueba:** Seguridad · validación
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El buscador no se rompe ni expone datos con caracteres especiales.

## 3. Precondiciones

- Sesión de admin.

## 4. Datos de prueba

- `%`, `_`, `' OR 1=1 --`, `<script>alert(1)</script>`, 300 caracteres, emojis, «Ñandú».

## 5. Procedimiento paso a paso

1. [ ] Buscar cada uno.

## 6. Resultado esperado

- Sin errores; `%` y `_` no devuelven todo; el script se muestra como texto.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.

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
