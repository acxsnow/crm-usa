# [INS-014] Material comprado en la obra (no sale de bodega)

## 1. Información general

- **ID:** INS-014
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

Lo que el técnico compra en el camino entra al costo sin mover la bodega.

## 3. Precondiciones

- Una obra en curso.

## 4. Datos de prueba

- «Breaker 30A y 10 ft de cable», USD 48.75.

## 5. Procedimiento paso a paso

1. [ ] En la obra: **Agregar material que no sale de bodega** con el dato.
2. [ ] Revisar el costo de la obra y la existencia de bodega.

## 6. Resultado esperado

- Aparece como «Comprado en la obra» en el costo; la bodega no cambia.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Valores con dos decimales exactos (sin redondeos raros).

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
