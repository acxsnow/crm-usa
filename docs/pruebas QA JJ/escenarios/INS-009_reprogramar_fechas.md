# [INS-009] Cambiar las fechas de una obra programada

## 1. Información general

- **ID:** INS-009
- **Módulo:** Instalación en campo
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Reprogramar mueve la obra en la agenda sin perder nada.

## 3. Precondiciones

- Una obra programada (INS-001).

## 4. Datos de prueba

- Nueva fecha: dos días hábiles después.

## 5. Procedimiento paso a paso

1. [ ] En la obra: **Cambiar fechas**.
2. [ ] Revisar la Agenda de instalaciones y la agenda del técnico.

## 6. Resultado esperado

- La obra aparece en la nueva fecha en las dos agendas.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El técnico recibe el aviso del cambio.
- [ ] La auditoría registra la fecha anterior y la nueva.

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
