# [SEC-008] Autorización de datos en los cuatro puntos de captura

## 1. Información general

- **ID:** SEC-008
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Privacidad · cumplimiento
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
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

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
