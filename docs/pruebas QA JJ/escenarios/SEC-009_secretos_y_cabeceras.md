# [SEC-009] Secretos fuera del navegador y cabeceras de seguridad

## 1. Información general

- **ID:** SEC-009
- **Módulo:** Seguridad
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

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

- Qué pasó: CORS no autoriza un origen ajeno; `/auth/me` no devuelve hashes ni secretos. `/api/docs` está abierta en desarrollo y el código la apaga en producción (`main.py`, `docs_url=None` con ENVIRONMENT=production).
- Diferencias con lo esperado: Falta buscar llaves en los JS del navegador (F12 › Sources).
- Comprobaciones por API (3 de 3):
  - ✔ documentación de la API (/api/docs) — anotar si está abierta — `200 (abierta=True)`
  - ✔ CORS no permite un origen ajeno — `None`
  - ✔ /auth/me no devuelve hash de clave ni secretos

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] CORS solo permite el origen del frontend.

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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
