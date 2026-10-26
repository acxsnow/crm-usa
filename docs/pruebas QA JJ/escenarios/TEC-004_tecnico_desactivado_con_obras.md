# [TEC-004] Desactivar un técnico que tiene obras y camioneta con material

## 1. Información general

- **ID:** TEC-004
- **Módulo:** Técnicos
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Desactivar no deja obras huérfanas sin aviso ni pierde el material de la camioneta.

## 3. Precondiciones

- Héctor Ruiz (`tecnico15@demo-org.com`) con una obra programada y material en su camioneta.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Como admin, desactivar a Héctor en **Equipo**.
2. [ ] Revisar la obra, la agenda y la existencia de su camioneta.
3. [ ] Rotar la obra a otro técnico.

## 6. Resultado esperado

- Anotar qué hace el sistema con la obra (aviso, la deja asignada, la libera) y con la camioneta.
- Héctor ya no entra.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 20 de 20 comprobaciones bien. Al desactivar a Héctor: la obra sigue asignada a él y programada, sin aviso a Administración; el material de su camioneta no se pierde; ya no aparece para asignar; la obra se rota a otro técnico sin problema; Héctor no entra.
- Diferencias con lo esperado: Ninguna (el escenario pedía anotar el comportamiento).
- Comprobaciones por API (20 de 20):
  - ✔ Visita «opened» en 461 QA 1025212450 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ El vendedor no puede aprobar su expediente
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ Obra programada a Héctor
  - ✔ Camioneta de Héctor
  - ✔ Traslado de 2 unidades a su camioneta
  - ✔ Admin desactiva a Héctor
  - ✔ La obra queda (anotar): técnico=Héctor, estado=scheduled
  - ✔ ¿Avisa a Administración que la obra quedó con un técnico inactivo? (anotar: ['case.submitted', 'claim.paid', 'installation.closed', 'warehouse.release_pending'])
  - ✔ El material de su camioneta no se pierde (2.00) — `2.00`
  - ✔ Héctor ya no aparece para asignar — `15`
  - ✔ Rotar la obra a otro técnico — `200 {"address_street":"461 QA 1025212450 Mobile Park Dr","address_unit":"Spc 361","address_city":"San Fernando","address_sta`
  - ✔ Héctor ya no entra

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si la obra queda asignada a alguien inactivo sin aviso, registrar defecto.

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
- Observaciones: Comportamiento anotado: desactivar a un técnico no libera ni avisa de sus obras programadas; hay que rotarlas a mano. Si se quiere un aviso, es una mejora a decidir.
