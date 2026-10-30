# [INS-010] El técnico llega y el cliente no estaba (visita fallida)

## 1. Información general

- **ID:** INS-010
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 16 de 16 comprobaciones bien.
- Diferencias con lo esperado: Falta la pantalla: botón «No se pudo hacer la visita», formulario y sección «Visitas fallidas».
- Comprobaciones por API (16 de 16):
  - ✔ Liberar orden
  - ✔ Material entregado a la obra (4 × PVC 3496) — `4.0`
  - ✔ Sin motivo no guarda
  - ✔ Con nota de 2 letras no guarda
  - ✔ Registrar visita fallida
  - ✔ 1 de 2 visitas fallidas — `{'failed_visits': 1, 'limit': 2, 'limit_reached': False, 'extra_visits_authorized': 0}`
  - ✔ La obra queda sin fecha, «Sin agendar», con el mismo técnico — `None planning`
  - ✔ Expediente «Listo para instalar · Visita fallida» — `('ready_to_install', 'visit_failed')`
  - ✔ project_visit_attempts con motivo, fecha y GPS — `customer_absent|2026-10-26|33.45|-112.07`
  - ✔ Auditoría projects.visit_failed
  - ✔ El material sigue cargado a la obra — `4.0`
  - ✔ Administración recibe el aviso de visita fallida — `['installation.visit_failed', 'warehouse.release_pending', 'case.submitted', 'claim.paid', 'claim.rejected']`
  - ✔ El técnico que la registró no se avisa a sí mismo
  - ✔ Sin fecha agendada no hay visita fallida
  - ✔ Reagendar con «Liberar orden»
  - ✔ Vuelve a «Instalación agendada» — `install_scheduled`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- El técnico ve «No se pudo hacer la visita» en su obra agendada; el formulario pide el motivo (6 opciones) y la nota, y la obra queda con la sección «Visitas fallidas», el contador y lo escrito (D-001).
- Comprobaciones (3 de 3):
  - ✔ El técnico ve «No se pudo hacer la visita» en la obra agendada
  - ✔ El formulario pide el motivo (6 opciones) y la nota — `['Elige el motivo', 'El cliente no estaba', 'No dejaron entrar o el cliente no quiso', 'Condiciones inseguras en la casa', 'Faltó material o`
  - ✔ Queda la sección «Visitas fallidas» con el contador y lo que escribió — `2
Orden liberada
Sin técnico ni fecha
En curso

Solo Administración asigna el técnico y la fecha.

Visitas fallidas

1 de 2 permitidas.

El `
- Capturas:
  - [formulario.jpg](../evidencias/pantalla/INS-010/formulario.jpg)
  - [visitas-fallidas.jpg](../evidencias/pantalla/INS-010/visitas-fallidas.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `project_visit_attempts`: una fila con motivo, nota, fecha agendada, técnico, latitud y longitud.
- [ ] Auditoría: `projects.visit_failed`.
- [ ] Una visita fallida sin fecha agendada se rechaza (`no_scheduled_visit`).

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
