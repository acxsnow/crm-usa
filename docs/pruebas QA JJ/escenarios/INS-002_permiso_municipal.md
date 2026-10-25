# [INS-002] Permiso municipal: sin permiso no se instala

## 1. Información general

- **ID:** INS-002
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

La guarda del permiso impide pasar a «Listo para instalar» sin el permiso aprobado.

## 3. Precondiciones

- INS-001 hecho.
- `PERMIT_FILED_ALLOWS_INSTALL` sin definir en `backend/.env` (valor por defecto).

## 4. Datos de prueba

- Ciudad o condado: «Phoenix»; número de radicado `PHX-QA-001`; un PDF cualquiera como permiso firmado.

## 5. Procedimiento paso a paso

1. [ ] En la obra, sección **Permiso**: **Registrar permiso** solo como radicado.
2. [ ] Intentar mover el expediente a «Listo para instalar» desde la revisión: anotar el mensaje.
3. [ ] Registrar el permiso como aprobado y **Subir permiso firmado por el inspector**.
4. [ ] Volver a intentar el paso a «Listo para instalar».

## 6. Resultado esperado

- Con solo el radicado lo rechaza con un mensaje que explica que falta el permiso aprobado.
- Con el aprobado sí avanza.

## 7. Resultado obtenido

- Qué pasó: Por API, 6 de 6 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (6 de 6):
  - ✔ Registrar el permiso solo radicado
  - ✔ Con solo el radicado, el paso manual a «Listo para instalar» se rechaza — `400 {"detail":"Todos los permisos deben estar aprobados y vigentes, o marcados como no requeridos, antes de pasar a «Listo para instalar».","code":"permits_not_`
  - ✔ Con solo el radicado, «Liberar orden» también se rechaza (permits_not_cleared) — `400 {"detail":"Todos los permisos deben estar aprobados y vigentes, o marcados como no requeridos, antes de pasar a «Listo para instalar».","code":"permits_not_`
  - ✔ Registrar el permiso como aprobado
  - ✔ Con el permiso aprobado el expediente pasa a «Listo para instalar» — `ready_to_install`
  - ✔ Permiso municipal aprobado con vencimiento

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial de etapas: un solo paso a «Listo para instalar», hecho por `advance_case`.
- [ ] Repetir con `PERMIT_FILED_ALLOWS_INSTALL=true` (reiniciar la API) y confirmar que el radicado basta para instalar pero no para el cobro.

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
- Observaciones: Sin ningún permiso registrado se puede liberar la orden (spec D6.4: se instala antes del permiso); con un permiso solo radicado, no.
