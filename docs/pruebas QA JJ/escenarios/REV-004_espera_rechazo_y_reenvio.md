# [REV-004] Poner en espera, rechazar con motivo y reenviar un rechazado

## 1. Información general

- **ID:** REV-004
- **Módulo:** Revisión administrativa
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Las salidas no felices del programa quedan registradas y un rechazado se puede corregir.

## 3. Precondiciones

- Un expediente enviado (VEN-004 con la puerta 204, «QA Espera León»).

## 4. Datos de prueba

- Puerta: dirección «204 QA Mobile Park Dr», espacio «Spc 24», Phoenix, AZ, 85006; motivos «Programa sin cupo» y «No cumple requisito de ingresos».

## 5. Procedimiento paso a paso

1. [ ] Como Andrés, **Poner en espera del programa** con el primer motivo.
2. [ ] Sacarlo de la espera (volver a revisión).
3. [ ] **Rechazar** con el segundo motivo; intentar rechazar sin motivo.
4. [ ] Como Vicky, abrir el rechazado, corregir y reenviar.

## 6. Resultado esperado

- Rechazar sin motivo no se permite.
- El rechazado se puede editar y reenviar.

## 7. Resultado obtenido

- Qué pasó: Por API, 17 de 17 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (17 de 17):
  - ✔ Visita «opened» en 304 QA 1025164900 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ El vendedor no puede aprobar su expediente
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ Rechazar sin motivo se bloquea
  - ✔ Rechazar con motivo
  - ✔ El vendedor puede corregir el rechazado
  - ✔ Corrige un dato
  - ✔ Reenvía a revisión
  - ✔ Vuelve a pendiente de aprobación — `pending_approval`
  - ✔ Poner en espera del programa

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Todos los cambios en el historial con su motivo.

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
