# [TEC-001] Cada técnico ve solo su agenda y sus obras

## 1. Información general

- **ID:** TEC-001
- **Módulo:** Técnicos
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `GET /api/v1/projects/<id>` como Luis: 404.

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
