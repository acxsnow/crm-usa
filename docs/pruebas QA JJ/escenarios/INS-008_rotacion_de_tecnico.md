# [INS-008] Cambiar el técnico de una obra en curso (rotación)

## 1. Información general

- **ID:** INS-008
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Al rotar, el técnico nuevo continúa y el anterior queda en solo lectura, sin perder lo que registró.

## 3. Precondiciones

- Una obra «En curso» de Tito con una jornada registrada y material entregado.

## 4. Datos de prueba

- Técnico nuevo: Toño Segundo (`tecnico02@demo-org.com`).

## 5. Procedimiento paso a paso

1. [ ] Como administración, en la obra: **Cambiar técnico** a Toño.
2. [ ] Como Tito: abrir la obra desde su agenda o por la URL.
3. [ ] Como Toño: registrar una jornada y cerrar la instalación.
4. [ ] Revisar el Diario de obra.

## 6. Resultado esperado

- Tito ve la obra en solo lectura (no puede registrar ni cerrar).
- El diario muestra las jornadas de los dos, cada una con su autor.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El material entregado sigue cargado a la obra (no a Tito).
- [ ] Por API, Tito recibe 403 al intentar registrar una jornada en esa obra.

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
