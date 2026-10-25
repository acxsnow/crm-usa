# [REV-001] Revisar documentos: aceptar, rechazar con nota y agregar uno

## 1. Información general

- **ID:** REV-001
- **Módulo:** Revisión administrativa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El contador de días hábiles sigue contando desde el envío.

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
