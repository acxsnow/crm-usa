# [REV-003] Aprobar con el código del programa: nace la obra

## 1. Información general

- **ID:** REV-003
- **Módulo:** Revisión administrativa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Aprobar mueve el expediente y crea la obra de instalación una sola vez.

## 3. Precondiciones

- Expediente de VEN-004 con todos los documentos aceptados (REV-001).

## 4. Datos de prueba

- Código de aprobación del programa: `AZ-QA-0001`.

## 5. Procedimiento paso a paso

1. [ ] Avanzar el estado con el programa: «Listo para el programa» › «Sometido» › «En revisión del programa».
2. [ ] Tocar **Aprobar** y escribir el código.
3. [ ] Abrir **Proyectos**: buscar «Instalación · CASE-…».

## 6. Resultado esperado

- El expediente pasa a «Aprobado» y nace la obra con su checklist del programa.
- Aprobar dos veces (doble clic) no crea dos obras.

## 7. Resultado obtenido

- Qué pasó: Por API, 8 de 8 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (8 de 8):
  - ✔ Avance con el programa: ready_to_submit
  - ✔ Avance con el programa: submitted_to_program
  - ✔ Avance con el programa: program_review
  - ✔ Aprobar con código
  - ✔ Aprobado con código y solicitud guardados
  - ✔ Aprobar dos veces no se permite — `400`
  - ✔ Una sola obra para el expediente — `1`
  - ✔ La obra copia la dirección y las coordenadas de la visita — `True|True`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Una sola fila en `projects` con ese `case_id`.
- [ ] La obra copia la dirección y las coordenadas de la visita.

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
