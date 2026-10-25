# [INS-003] Salida de material con la lista «3 ton desde cero»

## 1. Información general

- **ID:** INS-003
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El técnico pide el material con la lista predefinida, bodega lo autoriza y lo entrega, y la existencia baja.

## 3. Precondiciones

- INS-001 hecho (obra de Carlos).
- Anotar la existencia de 3 artículos de la lista (por ejemplo los SKU 85980, 3496 y 1578).

## 4. Datos de prueba

- Lista «Instalación 3 ton desde cero» (46 renglones).

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, en la obra: **Agregar material** › **Cargar desde una lista predefinida** › la lista 3 ton.
2. [ ] Quitar un renglón no obligatorio y bajar la cantidad de otro.
3. [ ] **Guardar y enviar a autorizar**.
4. [ ] Como administración, menú **Bodega** › **Salidas de bodega** › **Por autorizar**: abrirla y **Autorizar**.
5. [ ] **Entregar** (la salida pasa a «Entregada»).
6. [ ] Volver a mirar la existencia de los 3 artículos.

## 6. Resultado esperado

- La salida recibe su número SAL-… al enviarse.
- Al entregar, la existencia de bodega baja exactamente en lo entregado y ese material queda cargado a la obra o a la camioneta de Carlos (anotar dónde lo muestra).

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Movimientos de bodega: una `salida` por renglón con el usuario y la obra.
- [ ] El equipo con serial (85980) pide el serial al entregar.
- [ ] El costo de la obra en Rentabilidad incluye ese material.

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
