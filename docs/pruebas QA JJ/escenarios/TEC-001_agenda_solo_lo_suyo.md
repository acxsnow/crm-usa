# [TEC-001] Cada técnico ve solo su agenda y sus obras

## 1. Información general

- **ID:** TEC-001
- **Módulo:** Técnicos
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Aislamiento entre técnicos en lista, agenda, buscador y URL.

## 3. Precondiciones

- Obras asignadas a Carlos (INS-001) y a Luis (INS-007).

## 4. Datos de prueba

- Id de la obra de Carlos (URL `/projects/<id>`).

## 5. Procedimiento paso a paso

1. [ ] Como Luis abrir **Mi agenda**, **Proyectos** y el buscador con el nombre del cliente de Carlos.
2. [ ] Pegar la URL de la obra de Carlos.

## 6. Resultado esperado

- Luis no ve nada de Carlos; la URL responde 404.

## 7. Resultado obtenido

- Qué pasó: Por API, 3 de 3 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (3 de 3):
  - ✔ Luis no ve la obra de Tito en Proyectos
  - ✔ Luis: GET de la obra de Tito → 404
  - ✔ El buscador de Luis no la encuentra

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `GET /api/v1/projects/<id>` como Luis: 404.

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
