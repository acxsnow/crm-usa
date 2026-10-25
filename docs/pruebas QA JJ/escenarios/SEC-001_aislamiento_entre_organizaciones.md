# [SEC-001] Aislamiento entre organizaciones (IDOR)

## 1. Información general

- **ID:** SEC-001
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Repetir con las listas: ningún registro ajeno en ningún listado.

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
