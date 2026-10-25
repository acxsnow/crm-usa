# [FIN-005] Conciliación y rentabilidad por obra

## 1. Información general

- **ID:** FIN-005
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La ganancia de cada obra suma bien ingresos y costos (material, mano de obra, gastos, material menor y herramienta).

## 3. Precondiciones

- Una obra cerrada y cobrada (COB-003) con material, jornadas y un gasto.

## 4. Datos de prueba

- Cálculo a mano en una hoja: ingreso − (material + mano de obra + gastos).

## 5. Procedimiento paso a paso

1. [ ] **Conciliación y rentabilidad**: abrir la obra.
2. [ ] Comparar con el cálculo a mano.
3. [ ] Mirar el margen de una obra con pérdida.

## 6. Resultado esperado

- Coincide al centavo.
- Los márgenes negativos se leen completos (ver D-002).

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Material menor y herramienta entran en el costo según su configuración.

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
