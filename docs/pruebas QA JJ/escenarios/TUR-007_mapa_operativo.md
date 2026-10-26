# [TUR-007] Mapa operativo: técnicos y obras

## 1. Información general

- **ID:** TUR-007
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

El mapa muestra dónde están los técnicos y las obras, y ubica las que no tienen coordenadas.

## 3. Precondiciones

- Obras creadas en P-01 con direcciones reales de Phoenix.

## 4. Datos de prueba

- Una obra con dirección inventada (sin coordenadas posibles).

## 5. Procedimiento paso a paso

1. [ ] **Mapa operativo**: revisar técnicos y obras.
2. [ ] Usar la geocodificación de obras sin coordenadas.
3. [ ] Abrir la obra inventada.

## 6. Resultado esperado

- Las reales quedan ubicadas; la inventada sigue avisando que no tiene coordenadas (máximo 25 por intento).

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 31 de 31 comprobaciones bien. Una obra sin coordenadas aparece «sin ubicar»; «Ubicar por dirección» no encuentra la dirección inventada y la sigue mostrando sin ubicar; más de 25 por intento se rechaza; se puede ubicar a mano. El mapa muestra al personal y las obras, y el orden sugerido del día.
- Diferencias con lo esperado: La obra del plan con «dirección inventada» igual tenía coordenadas: las toma del GPS de la visita del vendedor. Para la prueba se le quitaron.
- Comprobaciones por API (31 de 31):
  - ✔ Gerencia ve el mapa del personal
  - ✔ El técnico aparece en el mapa
  - ✔ Administración ve las obras en el mapa
  - ✔ El mapa separa obras ubicadas y sin ubicar
  - ✔ Orden sugerido del día
  - ✔ Visita «opened» en 471 QA 1025215010 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ El vendedor no puede aprobar su expediente
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ Se puede ubicar a mano — `200 {"id":"f16fe14e-491f-46ff-b302-ba932440fdfa","latitude":33.4484,"longitude":-112.074}`
  - ✔ Visita «opened» en 472 QA 1025215402 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ El vendedor no puede aprobar su expediente
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ La obra sin coordenadas aparece «sin ubicar» — `1`
  - ✔ «Ubicar por dirección» responde (200) — `{"located":[],"not_found":[{"id":"7eb7ea5a-7994-465a-b655-aa149dd9fca2","title":"Instalación · CASE-2026-0016","address":"472 QA 1025215402 Mobile Park Dr, Spc `
  - ✔ La dirección inventada sigue sin coordenadas y avisando — `{"located":[],"not_found":[{"id":"7eb7ea5a-7994-465a-b655-aa149dd9fca2","title":"Instalación · CASE-2026-0016","address":"472 QA 1025215402 Mobile Par`
  - ✔ Más de 25 obras por intento se rechaza (422) — `422`
  - ✔ Se ubica a mano — `200 {"id":"7eb7ea5a-7994-465a-b655-aa149dd9fca2","latitude":33.4484,"longitude":-112.074}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo Administrador y Administración ven el mapa.

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
