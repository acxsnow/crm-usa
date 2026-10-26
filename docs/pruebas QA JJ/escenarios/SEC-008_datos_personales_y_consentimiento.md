# [SEC-008] Autorización de datos en los cuatro puntos de captura

## 1. Información general

- **ID:** SEC-008
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Privacidad · cumplimiento
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

La autorización es obligatoria al crear cliente, editarlo, en los T&C del expediente y en la firma pública.

## 3. Precondiciones

- Sesiones de admin y vendedor.

## 4. Datos de prueba

- Cliente «QA Privacidad Díaz».

## 5. Procedimiento paso a paso

1. [ ] Crear el cliente sin marcar la autorización (pantalla y API).
2. [ ] Editarlo sin volver a autorizar.
3. [ ] Firmar T&C sin autorización (VEN-004).
4. [ ] Firmar el acta pública sin autorización (INS-004).
5. [ ] Abrir `http://localhost:8000/api/v1/privacy/consent-notice` sin sesión.

## 6. Resultado esperado

- Ninguno de los cuatro se guarda sin la autorización.
- El aviso es público y trae su versión.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 11 de 11 comprobaciones bien. Crear y editar cliente sin autorización se rechaza (`consent_required`); el aviso es público, versionado (2026.1) y cita California, Nevada y Arizona; cada autorización deja su constancia; la firma de los T&C deja la suya.
- Diferencias con lo esperado: En los T&C y en la firma pública del acta la API no pide una casilla aparte: la firma misma queda como autorización y se guarda la constancia. Falta ver en pantalla que el aviso se muestra antes de firmar (VEN-004 e INS-004).
- Comprobaciones por API (11 de 11):
  - ✔ El aviso se ve sin sesión
  - ✔ El aviso viene versionado y en español — `2026.1`
  - ✔ El aviso dice lo que exige la ley de esas zonas — `Autorizo a la empresa que me presta este servicio a recolectar, usar, guardar y compartir mis datos personales para aten`
  - ✔ Sin autorización no se guarda el cliente — `HTTP 400: {"detail":"Falta la autorización de tratamiento de datos personales del cliente: márcala antes de guardar.","code":"cons`
  - ✔ Con autorización sí se guarda
  - ✔ Editar solo las notas no pide autorización
  - ✔ Corregir el teléfono sin autorización se rechaza — `HTTP 400: {"detail":"Falta la autorización de tratamiento de datos personales del cliente: márcala antes de guardar.","code":"cons`
  - ✔ Corregir el teléfono con autorización
  - ✔ Queda una constancia por cada autorización — `5`
  - ✔ La constancia guarda el texto completo con su versión y origen — `2026.1|2061|customer_update`
  - ✔ La firma de los T&C deja su constancia (fuente del expediente) — `case_intake|1; customer_create|3; customer_update|1`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `data_consents`: una fila por cada autorización con versión, fecha, IP y GPS.

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

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
