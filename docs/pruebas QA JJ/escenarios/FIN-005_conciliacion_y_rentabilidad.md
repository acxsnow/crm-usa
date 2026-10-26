# [FIN-005] Conciliación y rentabilidad por obra

## 1. Información general

- **ID:** FIN-005
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

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

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 4 de 4 comprobaciones bien. En la obra cerrada y cobrada, los costos son la suma de material, mano de obra, gastos, material menor y herramienta, y el margen es cobrado − costos al centavo. Hay una obra con pérdida para revisar (margen -10,408.49).
- Diferencias con lo esperado: Falta ver en pantalla que el margen negativo se lee completo (D-002).
- Comprobaciones por API (4 de 4):
  - ✔ Rentabilidad de la instalación TECH
  - ✔ Cobrado 6500.00 · costos 16908.49 · margen -10408.49 — `{'project_id': 'f1adbe77-ddd5-4f96-8204-46d2e6bb5b6d', 'title': 'Instalación · CASE-2026-0001', 'status': 'completed', 'completed_date': '2026-10-25', 'case_num`
  - ✔ Costos = suma de material, mano de obra, gastos, material menor y herramienta (3.34) — `{'materials': '3.34', 'equipment': '0.00', 'labor': '0.00', 'contractor': '0.00', 'permit': '0.00', 'services': '0.00', 'other': '0.00', 'sales_rep': '0.00', 'c`
  - ✔ Margen = cobrado − costos (6500.00 − 3.34 = 6496.66) — `{'project_id': 'f1adbe77-ddd5-4f96-8204-46d2e6bb5b6d', 'title': 'Instalación · CASE-2026-0001', 'status': 'completed', 'completed_date': '2026-10-25', 'case_num`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
