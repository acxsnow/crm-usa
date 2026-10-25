# [TEC-004] Desactivar un técnico que tiene obras y camioneta con material

## 1. Información general

- **ID:** TEC-004
- **Módulo:** Técnicos
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Desactivar no deja obras huérfanas sin aviso ni pierde el material de la camioneta.

## 3. Precondiciones

- Héctor Ruiz (`tecnico15@demo-org.com`) con una obra programada y material en su camioneta.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Como admin, desactivar a Héctor en **Equipo**.
2. [ ] Revisar la obra, la agenda y la existencia de su camioneta.
3. [ ] Rotar la obra a otro técnico.

## 6. Resultado esperado

- Anotar qué hace el sistema con la obra (aviso, la deja asignada, la libera) y con la camioneta.
- Héctor ya no entra.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si la obra queda asignada a alguien inactivo sin aviso, registrar defecto.

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
