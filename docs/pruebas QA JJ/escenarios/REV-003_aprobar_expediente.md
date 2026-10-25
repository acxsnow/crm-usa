# [REV-003] Aprobar con el código del programa: nace la obra

## 1. Información general

- **ID:** REV-003
- **Módulo:** Revisión administrativa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Una sola fila en `projects` con ese `case_id`.
- [ ] La obra copia la dirección y las coordenadas de la visita.

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
