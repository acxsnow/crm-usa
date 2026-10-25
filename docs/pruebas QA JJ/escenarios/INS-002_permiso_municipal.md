# [INS-002] Permiso municipal: sin permiso no se instala

## 1. Información general

- **ID:** INS-002
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial de etapas: un solo paso a «Listo para instalar», hecho por `advance_case`.
- [ ] Repetir con `PERMIT_FILED_ALLOWS_INSTALL=true` (reiniciar la API) y confirmar que el radicado basta para instalar pero no para el cobro.

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

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
