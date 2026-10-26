# [INS-015] Señal débil: subir fotos y guardar con red lenta

## 1. Información general

- **ID:** INS-015
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Rendimiento · celular
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

En un parque sin buena señal no se pierden fotos ni se duplican registros.

## 3. Precondiciones

- Una obra en curso; F12 › Network con perfil **Slow 3G**.

## 4. Datos de prueba

- 3 fotos de ~4 MB del celular.

## 5. Procedimiento paso a paso

1. [ ] Subir las 3 fotos del checklist con Slow 3G.
2. [ ] Registrar la jornada y tocar Guardar dos veces seguidas.
3. [ ] Pasar a Offline a mitad de una subida y volver a Online.

## 6. Resultado esperado

- Cada foto muestra «Subiendo…» y termina, o falla con «No se pudo subir la foto.» y se puede reintentar.
- El doble toque no crea dos jornadas.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 11 de 11 comprobaciones bien. Guardar la jornada dos veces seguidas deja una sola.
- Diferencias con lo esperado: Falta la parte de pantalla: Slow 3G, fotos de 4 MB y pasar a Offline a mitad de una subida.
- Comprobaciones por API (11 de 11):
  - ✔ Visita «opened» en 463 QA 1025212450 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ El vendedor no puede aprobar su expediente
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ Guardar la jornada dos veces seguidas no crea dos (201, 400) — `jornadas=1 {"detail":"Esa obra ya tiene una jornada de ese día.","code":"day_log_date_taken","request_id":"75ba34a2-38d4-4638-976b-8f8b1f625e3d"}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Anotar el tiempo de cada subida.
- [ ] Ninguna foto a medias queda guardada.

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
