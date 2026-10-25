# [BOD-006] Reintegro: el material vuelve de la camioneta a bodega

## 1. Información general

- **ID:** BOD-006
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Lo que sobra en la obra vuelve a bodega y sale del costo de la obra.

## 3. Precondiciones

- Una salida entregada (INS-003).

## 4. Datos de prueba

- Devolver 1 unidad de un renglón entregado.

## 5. Procedimiento paso a paso

1. [ ] En la salida, **Devolver** la unidad a bodega.
2. [ ] Intentar devolver más de lo entregado.
3. [ ] Revisar la existencia, la camioneta y el costo de la obra en Rentabilidad.

## 6. Resultado esperado

- Bodega sube 1, la camioneta baja 1 y el costo de la obra baja en ese valor.
- No permite devolver más de lo entregado.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Movimiento `devolucion` con referencia a la salida.
- [ ] Lo entregado no se edita: se corrige con la devolución.

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
