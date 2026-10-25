# [SEC-009] Secretos fuera del navegador y cabeceras de seguridad

## 1. Información general

- **ID:** SEC-009
- **Módulo:** Seguridad
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Ninguna llave del servidor llega al navegador.

## 3. Precondiciones

- El frontend cargado.

## 4. Datos de prueba

- Buscar en Sources y en las respuestas: `sk_`, `secret`, `PLAID`, `SMTP`, `password`.

## 5. Procedimiento paso a paso

1. [ ] F12 › Sources: buscar las palabras en los JS.
2. [ ] Revisar las cabeceras de una respuesta de la API.
3. [ ] Abrir `http://localhost:8000/api/v1/../docs` y `/openapi.json`.

## 6. Resultado esperado

- Ninguna llave en el JS ni en respuestas.
- Anotar si la documentación de la API está abierta (en producción debería cerrarse).

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] CORS solo permite el origen del frontend.

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
