# [TEC-002] El técnico no autoriza salidas ni confirma su propia acta

## 1. Información general

- **ID:** TEC-002
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

Separación de funciones en campo, también por la API.

## 3. Precondiciones

- Una salida «Por autorizar» y un acta cerrada del mismo técnico.

## 4. Datos de prueba

- Token del técnico.

## 5. Procedimiento paso a paso

1. [ ] Como técnico, buscar los botones Autorizar, Entregar y Confirmar información técnica.
2. [ ] Llamar por la API a autorizar la salida y a confirmar el acta con su token.

## 6. Resultado esperado

- La pantalla no los ofrece; la API responde 403 y nada cambia.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún movimiento de bodega creado.

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
