# [SEC-003] Cada rol contra cada grupo de rutas

## 1. Información general

- **ID:** SEC-003
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 45 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Confirmar por la API la matriz de `05_MATRIZ_PERMISOS.md` (no solo el menú).

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).
- La matriz de permisos.

## 4. Datos de prueba

- Una ruta de lectura y una de escritura por módulo (la matriz trae la lista).

## 5. Procedimiento paso a paso

1. [ ] Con el token de cada uno de los 6 roles, llamar las rutas de la matriz.
2. [ ] Marcar en la matriz lo obtenido.

## 6. Resultado esperado

- Coincide con la matriz; cualquier diferencia es un defecto P0.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `tests/test_permissions*.py` pasa (la prueba automática que ya cubre rutas sin permiso).

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
