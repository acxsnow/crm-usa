# [API-005] Límite de peticiones (rate limit)

## 1. Información general

- **ID:** API-005
- **Módulo:** API y paginación
- **Prioridad:** P2
- **Tipo de prueba:** Seguridad · disponibilidad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las rutas públicas sensibles no aceptan ráfagas.

## 3. Precondiciones

- Redis activo.

## 4. Datos de prueba

- 30 peticiones seguidas a olvido de clave y a la firma pública.

## 5. Procedimiento paso a paso

1. [ ] Lanzarlas con un bucle de `fetch`.
2. [ ] Limpiar los contadores (ver AUTH-002).

## 6. Resultado esperado

- A partir del tope responde 429.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La API sigue respondiendo a los demás usuarios.

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
