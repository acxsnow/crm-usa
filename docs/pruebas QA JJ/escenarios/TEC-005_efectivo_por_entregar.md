# [TEC-005] Cobro en efectivo en campo y efectivo por entregar

## 1. Información general

- **ID:** TEC-005
- **Módulo:** Técnicos
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

El efectivo que recibe el técnico queda a su cargo hasta que lo entrega.

## 3. Precondiciones

- Una obra con **Cobro adicional del cliente** anotado.

## 4. Datos de prueba

- Efectivo USD 150.00.

## 5. Procedimiento paso a paso

1. [ ] Como técnico, **Anotar cobro** en efectivo.
2. [ ] Ver «Efectivo por entregar».
3. [ ] Como administración, recibir la entrega.

## 6. Resultado esperado

- El efectivo aparece a cargo del técnico hasta la entrega y luego en cero.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 14 de 14 comprobaciones bien. Tito anota USD 150.00 en efectivo; «Efectivo por entregar» lo muestra a su cargo; al recibirlo Administración deja de estar pendiente.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (14 de 14):
  - ✔ Visita «opened» en 462 QA 1025212450 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ El vendedor no puede aprobar su expediente
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ Tito anota un cobro en efectivo de USD 150.00 — `201 {"id":"00ec5217-96b2-475b-8db4-863824126651","project_id":"d458d36c-c156-434c-a1c2-5e832f28651f","charge_date":"2026-10-25","description":"QA cobro ad`
  - ✔ «Efectivo por entregar» lo muestra a cargo de Tito — `[{'id': '00ec5217-96b2-475b-8db4-863824126651', 'project_id': 'd458d36c-c156-434c-a1c2-5e832f28651f', 'charge_date': '2026-10-25', 'description': 'QA cobro adic`
  - ✔ Administración recibe la entrega
  - ✔ Después de entregarlo ya no está pendiente

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El valor es exacto (Decimal), sin centavos perdidos.

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
- Observaciones:
