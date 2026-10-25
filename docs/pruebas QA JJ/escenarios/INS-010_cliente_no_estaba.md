# [INS-010] El técnico llega y el cliente no estaba (visita fallida)

## 1. Información general

- **ID:** INS-010
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El técnico registra la visita fallida con motivo, nota y GPS; la obra queda sin fecha para agendarla otra vez, el expediente no cambia de etapa y Administración recibe el aviso.

## 3. Precondiciones

- Una obra programada de Carlos con material entregado (INS-001 e INS-003).
- Sesión de Carlos en el celular, ubicación concedida.

## 4. Datos de prueba

- Motivo «El cliente no estaba»; nota «Toqué tres veces y llamé, no contestó».

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, abrir la obra › paso **Orden liberada** › **No se pudo hacer la visita**.
2. [ ] Tocar **Registrar visita fallida** sin elegir motivo, y luego con una nota de 2 letras: anotar los mensajes.
3. [ ] Elegir «El cliente no estaba», escribir la nota y **Registrar visita fallida**.
4. [ ] Ver la sección **Visitas fallidas** (contador e historial con «con GPS»).
5. [ ] Como administración: ver el aviso en la campana (enlace a la obra) y la obra en **Proyectos** sin fecha.
6. [ ] Abrir el expediente: etapa «Listo para instalar · Visita fallida».
7. [ ] Revisar que el material sigue cargado a la obra (no volvió solo a bodega).
8. [ ] Como administración, **Liberar orden** con una fecha nueva.

## 6. Resultado esperado

- Sin motivo o con nota corta no guarda.
- La obra queda sin fecha, «Sin agendar», con 1 de 2 visitas fallidas y el mismo técnico.
- El expediente sigue en «Listo para instalar» con el sub-estado «Visita fallida»; al reagendar vuelve a «Instalación agendada».
- El aviso le llega a quien agenda y no al técnico que la registró.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `project_visit_attempts`: una fila con motivo, nota, fecha agendada, técnico, latitud y longitud.
- [ ] Auditoría: `projects.visit_failed`.
- [ ] Una visita fallida sin fecha agendada se rechaza (`no_scheduled_visit`).

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
