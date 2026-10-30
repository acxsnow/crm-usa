# [REV-001] Revisar documentos: aceptar, rechazar con nota y agregar uno

## 1. Información general

- **ID:** REV-001
- **Módulo:** Revisión administrativa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Administración revisa cada documento y no puede aprobar con uno rechazado.

## 3. Precondiciones

- VEN-004 enviado.
- Sesión de `administracion@demo-org.com` (Andrés).

## 4. Datos de prueba

- Expediente de VEN-004.

## 5. Procedimiento paso a paso

1. [ ] Menú **Por revisar** › pestaña **Documentos**: abrir el expediente.
2. [ ] Aceptar todos los documentos menos uno; rechazar ese con la nota «Foto borrosa».
3. [ ] Intentar **Aprobar**: anotar el mensaje.
4. [ ] Usar **+ Agregar documento** para subir el reemplazo y aceptarlo.

## 6. Resultado esperado

- Con un documento rechazado el botón Aprobar está bloqueado y dice cuántos hay.
- Al aceptar el reemplazo se habilita.

## 7. Resultado obtenido

- Qué pasó: Por API, 8 de 8 comprobaciones bien.
- Diferencias con lo esperado: Falta ver en pantalla que «Aprobar» queda bloqueado y dice cuántos documentos faltan.
- Comprobaciones por API (8 de 8):
  - ✔ Administración ve los documentos
  - ✔ Todos los documentos por revisar — `10`
  - ✔ El expediente aparece en la cola de documentos
  - ✔ Extra: Administración agrega una factura de luz
  - ✔ Rechazar sin nota se bloquea
  - ✔ Rechazar con nota
  - ✔ Aprobar con documento rechazado se bloquea
  - ✔ Todos los documentos aceptados — `11`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- Con documentos sin revisar, «Aprobar» queda bloqueado y la pantalla dice cuántos faltan («Faltan N documento(s) por revisar.»).
- Comprobaciones (2 de 2):
  - ✔ Con documentos sin revisar «Aprobar» queda bloqueado
  - ✔ Y dice cuántos faltan («Faltan N documento(s) por revisar.»)
- Capturas:
  - [aprobar-bloqueado.jpg](../evidencias/pantalla/REV-001/aprobar-bloqueado.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El contador de días hábiles sigue contando desde el envío.

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
