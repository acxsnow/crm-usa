# [SEC-010] Bitácora de auditoría de acciones sensibles

## 1. Información general

- **ID:** SEC-010
- **Módulo:** Seguridad
- **Prioridad:** P1
- **Tipo de prueba:** Auditoría
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las acciones de dinero, permisos y datos personales quedan con quién, qué y cuándo.

## 3. Precondiciones

- Haber ejecutado AUTH-007, PAR-002, BOD-009 e INS-008.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Menú **Auditoría**: filtrar por cada acción.
2. [ ] Intentar abrirla como gerencia y como técnico.

## 6. Resultado esperado

- Cada acción aparece con usuario, fecha, antes y después.
- Solo el Administrador la ve.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La bitácora no se puede editar ni borrar desde la API.

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
