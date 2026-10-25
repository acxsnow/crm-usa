# [REV-006] El vendedor no puede aprobar su propio expediente (SEG-07)

## 1. Información general

- **ID:** REV-006
- **Módulo:** Revisión administrativa
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Separación de funciones: vender y aprobar son permisos distintos, también por la API.

## 3. Precondiciones

- Expediente de Vicky en «Pendiente de aprobación».

## 4. Datos de prueba

- Token de Vicky (F12 › Network › cualquier petición › cabecera Authorization).

## 5. Procedimiento paso a paso

1. [ ] Como Vicky, abrir `/cases/<id>/review`.
2. [ ] Desde la consola del navegador o Postman: `POST /api/v1/cases/<id>/transition` con `{"to_stage":"approved"}` y el token de Vicky.

## 6. Resultado esperado

- La pantalla no ofrece aprobar.
- La API responde 403 y el expediente no cambia.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna obra creada.

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
