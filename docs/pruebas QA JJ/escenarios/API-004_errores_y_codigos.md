# [API-004] Códigos HTTP y formato de error uniformes

## 1. Información general

- **ID:** API-004
- **Módulo:** API y paginación
- **Prioridad:** P1
- **Tipo de prueba:** API · contrato
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Los errores siguen `docs/ERRORES.md`: mismo formato, código correcto, mensaje en español.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).

## 4. Datos de prueba

- Un id inexistente, un id mal formado (`abc`), un cuerpo vacío, un JSON roto.

## 5. Procedimiento paso a paso

1. [ ] Provocar cada error en 3 módulos distintos.

## 6. Resultado esperado

- 404, 422, 422 y 400/422 respectivamente, con el mismo formato de `docs/ERRORES.md`.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Nunca 500 por una entrada del usuario.

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
