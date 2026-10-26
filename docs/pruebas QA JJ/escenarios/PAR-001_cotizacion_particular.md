# [PAR-001] Cotización particular: armar, enviar y aceptar

## 1. Información general

- **ID:** PAR-001
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

El trabajo particular se cotiza desde el price book sin tocar ningún expediente.

## 3. Precondiciones

- Sesión de `contabilidad@demo-org.com`.
- Un cliente particular creado en **Clientes** (con su autorización de datos).

## 4. Datos de prueba

- Cliente «QA Particular Gómez»; 2 renglones del price book y 1 libre (USD 120.00).

## 5. Procedimiento paso a paso

1. [ ] **Cotizaciones** › **Armar la cotización** con los renglones.
2. [ ] Enviarla al cliente.
3. [ ] Marcarla aceptada.
4. [ ] Crear otra y marcarla «No aceptada».

## 6. Resultado esperado

- Totales correctos con el impuesto que aplique.
- Los estados cambian a Aceptadas / No aceptada.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 9 de 9 comprobaciones bien. Cotización con 2 renglones del price book y 1 libre de USD 120.00: el total es la suma; no toca ningún expediente; enviada, aceptada (crea la factura en borrador) y otra marcada «No aceptada».
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (9 de 9):
  - ✔ Armar la cotización con 2 renglones del price book y 1 libre
  - ✔ Total = suma de los renglones (260.81) — `260.81 None`
  - ✔ No toca ningún expediente
  - ✔ Enviarla al cliente
  - ✔ Marcarla aceptada
  - ✔ Queda «Aceptada» y crea la factura en borrador — `accepted draft`
  - ✔ Otra, marcada «No aceptada»
  - ✔ Estado «No aceptada» — `rejected`
  - ✔ El resumen cuenta aceptadas y no aceptadas — `{'rejected': {'count': 1, 'total': 120.0}, 'accepted': {'count': 1, 'total': 260.81}}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún expediente cambió de etapa (`case_stage_events` sin filas nuevas).

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Las cotizaciones particulares no llevan impuesto (no existe ese concepto en la cotización): el total es la suma de los renglones.
