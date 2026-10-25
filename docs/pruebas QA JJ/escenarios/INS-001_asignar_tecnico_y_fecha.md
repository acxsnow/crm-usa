# [INS-001] Asignar técnico y fecha a la obra

## 1. Información general

- **ID:** INS-001
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución + 25 min de preparación
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

La obra pasa de «Sin técnico ni fecha» a programada y le aparece al técnico en su agenda.

## 3. Precondiciones

- Una obra nacida de un expediente aprobado (procedimiento P-01 de `04_DATOS_DE_PRUEBA.md`).
- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Técnico: Carlos Ramírez (`tecnico03@demo-org.com`); fecha: el próximo día hábil.

## 5. Procedimiento paso a paso

1. [ ] Menú **Proyectos**: abrir la obra «Instalación · CASE-…».
2. [ ] Asignar a Carlos Ramírez y la fecha de instalación.
3. [ ] Abrir **Agenda de instalaciones** (vista Semana) y ubicar la obra.
4. [ ] Como Carlos (incógnito), abrir **Mi agenda**.

## 6. Resultado esperado

- La obra queda «Programado» con técnico y fecha.
- Carlos la ve en su agenda; Tito no.

## 7. Resultado obtenido

- Qué pasó: Por API, 8 de 8 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (8 de 8):
  - ✔ Asignar técnico y fecha (Liberar orden)
  - ✔ La obra queda programada con técnico y fecha — `scheduled 2026-10-26`
  - ✔ El técnico la ve en su agenda — `1`
  - ✔ Otro técnico (Luis) no la ve en su agenda — `0`
  - ✔ La auditoría registra quién asignó — `1`
  - ✔ Al aprobar se creó el proyecto de instalación
  - ✔ Agendar instalación con técnico
  - ✔ El técnico ve su orden

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Carlos recibe el aviso en la campana.
- [ ] La auditoría registra quién asignó.

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
