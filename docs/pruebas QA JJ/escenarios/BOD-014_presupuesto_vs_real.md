# [BOD-014] Presupuesto de la obra contra lo real

## 1. Información general

- **ID:** BOD-014
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

La desviación entre lo presupuestado y lo consumido es correcta.

## 3. Precondiciones

- Una obra sin presupuesto.

## 4. Datos de prueba

- Presupuesto con la lista 3 ton; luego entregar el 80 %.

## 5. Procedimiento paso a paso

1. [ ] **Armar presupuesto** con la lista y **Aprobar presupuesto**.
2. [ ] Entregar parte del material.
3. [ ] Ver presupuesto vs. real.

## 6. Resultado esperado

- La desviación por renglón y total es exacta.

## 7. Resultado obtenido

- Qué pasó: Por API, 6 de 6 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (6 de 6):
  - ✔ Administración arma el presupuesto de la obra
  - ✔ Le agrega la lista «Mini split 12k»
  - ✔ Gerencia solo lee: no aprueba presupuestos
  - ✔ El Administrador aprueba el presupuesto
  - ✔ Presupuesto contra costo real de la obra
  - ✔ El material entregado ya cuenta como costo real de la obra — `{"category": "materials", "label": "Material", "estimated": "280.25", "actual": "169.25", "deviation": "-111.00", "deviation_pct": -39.6}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un presupuesto aprobado no se edita sin volver a borrador (anotar el comportamiento).

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
