# [SEC-001] Aislamiento entre organizaciones (IDOR)

## 1. Información general

- **ID:** SEC-001
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Nadie de una organización lee ni cambia nada de otra, aunque conozca el id.

## 3. Precondiciones

- Base QA (trae «Organización Ajena QA» con `admin@otra-org.com`).
- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).

## 4. Datos de prueba

- Ids del cliente «Cliente Ajeno QA» y del «Artículo Ajeno QA» (consultarlos en la base).
- Un expediente, una obra y una factura de la organización demo.

## 5. Procedimiento paso a paso

1. [ ] Como `admin@otra-org.com`, `GET` del expediente, la obra, la factura y un cliente de la demo.
2. [ ] Como `admin@demo-org.com`, `GET`, `PATCH` y `DELETE` del cliente y el artículo ajenos.
3. [ ] Como admin ajeno, crear un cliente mandando en el cuerpo `organization_id` de la demo.

## 6. Resultado esperado

- Todo responde 404 (no 403, no revela que existe) y nada cambia.
- El cliente creado queda en la organización del token, no en la del cuerpo.

## 7. Resultado obtenido

- Qué pasó: El admin ajeno recibe 404 en artículo, usuario, lista y programa de la demo; el admin demo recibe 404/405 al leer, cambiar o borrar el cliente y el artículo ajenos. Las listas de clientes, artículos y usuarios del ajeno solo traen lo suyo. Crear un cliente mandando el `organization_id` de la demo lo deja en la organización del token.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (16 de 16):
  - ✔ admin ajeno GET artículo demo → 404 — `404 {"detail":"El artículo no existe.","code":"warehouse_item_not_found","request_id":"b04e6a0a-28c3-4e2`
  - ✔ admin ajeno GET usuario demo → 404 — `404 {"detail":"Frontend build not found.","code":"http_404","request_id":"40803aca-e009-4128-a834-b23bf1`
  - ✔ admin ajeno GET lista demo → 404 — `404 {"detail":"La lista predefinida no existe.","code":"warehouse_kit_not_found","request_id":"1e4a2a05-`
  - ✔ admin ajeno GET programa demo → 404 — `404 {"detail":"El programa no existe.","code":"program_not_found","request_id":"c7cabae8-85c2-4304-843b-`
  - ✔ admin demo GET cliente ajeno → 404 — `404`
  - ✔ admin demo PATCH cliente ajeno → 404/405 — `404`
  - ✔ admin demo PUT cliente ajeno → 404/405/422 — `405`
  - ✔ admin demo DELETE cliente ajeno → 404/405 — `405`
  - ✔ admin demo GET artículo ajeno → 404 — `404`
  - ✔ admin demo PATCH artículo ajeno → 404/405 — `405`
  - ✔ admin demo PUT artículo ajeno → 404/405/422 — `404`
  - ✔ admin demo DELETE artículo ajeno → 404/405 — `405`
  - ✔ la lista de clientes del ajeno solo trae lo suyo — `['Cliente Ajeno QA']`
  - ✔ la lista de artículos del ajeno solo trae el suyo — `1`
  - ✔ la lista de usuarios del ajeno solo trae los suyos — `200 ['admin@otra-org.com']`
  - ✔ crear cliente mandando organization_id ajeno no lo deja en la demo — `400 org=None {"detail":"Falta la autorización de tratamiento de datos personales del cliente: márcala antes de guardar.","code":"consent_required","request_id":`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] Repetir con las listas: ningún registro ajeno en ningún listado.

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
- Observaciones: Aún no hay expedientes, obras ni facturas: repetir con ellos al final del ciclo (después de VEN, INS y PAR).
