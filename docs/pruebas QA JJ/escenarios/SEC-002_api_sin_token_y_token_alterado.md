# [SEC-002] API sin token, con token vencido o alterado

## 1. Información general

- **ID:** SEC-002
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Ninguna ruta privada responde sin una sesión válida.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).

## 4. Datos de prueba

- `http://localhost:8000/api/v1/cases`, `/customers`, `/warehouse/stock`, `/invoices`.

## 5. Procedimiento paso a paso

1. [ ] Llamar cada una sin cabecera.
2. [ ] Con un token con un carácter cambiado.
3. [ ] Con un token de hace más de 15 minutos.
4. [ ] Con el token de refresco en lugar del de acceso.

## 6. Resultado esperado

- 401 en todos los casos, sin datos.

## 7. Resultado obtenido

- Qué pasó: Sin token, con token alterado, con un token basura y con el token de refresco: 401 en las 4 rutas, sin trazas internas.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (25 de 25):
  - ✔ /cases sin token → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"586bbcdb-d824-4`
  - ✔ /cases sin token sin trazas internas
  - ✔ /cases token alterado → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"dd8622c4-c162-4`
  - ✔ /cases token alterado sin trazas internas
  - ✔ /cases basura → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"44ddb368-c475-4`
  - ✔ /cases basura sin trazas internas
  - ✔ /customers sin token → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"73a069dd-8d50-4`
  - ✔ /customers sin token sin trazas internas
  - ✔ /customers token alterado → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"456e3f3d-1e3d-4`
  - ✔ /customers token alterado sin trazas internas
  - ✔ /customers basura → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"cd93dcbb-c834-4`
  - ✔ /customers basura sin trazas internas
  - ✔ /warehouse/stock sin token → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"9baa3f49-2933-4`
  - ✔ /warehouse/stock sin token sin trazas internas
  - ✔ /warehouse/stock token alterado → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"97e09326-329a-4`
  - ✔ /warehouse/stock token alterado sin trazas internas
  - ✔ /warehouse/stock basura → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"9e591231-e96d-4`
  - ✔ /warehouse/stock basura sin trazas internas
  - ✔ /invoices sin token → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"2c14b5c1-93d9-4`
  - ✔ /invoices sin token sin trazas internas
  - ✔ /invoices token alterado → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"675ac394-5dad-4`
  - ✔ /invoices token alterado sin trazas internas
  - ✔ /invoices basura → 401 — `401 {"detail":"Tu sesión no es válida o ya venció. Vuelve a iniciar sesión.","code":"http_401","request_id":"50d81c20-f37e-4`
  - ✔ /invoices basura sin trazas internas
  - ✔ el token de refresco no sirve como token de acceso — `401`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] El mensaje de error no revela detalles internos (sin trazas).

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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
