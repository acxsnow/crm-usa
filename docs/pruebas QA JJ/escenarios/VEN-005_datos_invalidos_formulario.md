# [VEN-005] Datos inválidos en el formulario

## 1. Información general

- **ID:** VEN-005
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P2
- **Tipo de prueba:** Funcional · validación
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Los campos rechazan formatos imposibles en la pantalla y en la API.

## 3. Precondiciones

- Un expediente de Vicky en «Nuevo prospecto» (iniciar uno nuevo como en VEN-004 sin enviarlo).

## 4. Datos de prueba

- Puerta: dirección «202 QA Mobile Park Dr», espacio «Spc 22», Phoenix, AZ, 85006. Valores: correo «sin-arroba», teléfono «abc», número por encima del máximo del catálogo, archivo .exe renombrado a .jpg.

## 5. Procedimiento paso a paso

1. [ ] Escribir cada valor inválido en su campo y tocar **Guardar y seguir**.
2. [ ] Subir el .exe renombrado como foto.
3. [ ] Con F12 › Network, anotar la respuesta de la API en cada intento.

## 6. Resultado esperado

- Cada valor inválido se rechaza con un mensaje claro en español.
- El archivo falso se rechaza por su contenido real (400), no por la extensión.

## 7. Resultado obtenido

- Qué pasó: Por API, 6 de 6 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (6 de 6):
  - ✔ Archivo disfrazado (exe como jpg) se rechaza
  - ✔ Visita «opened» en 302 QA 1025164900 Mobile Park Dr
  - ✔ email inválido «sin-arroba»: rechazado o marcado con error — `400 error=None {"detail":"Revisa: Correo electrónico: No es un correo válido.","code":"invalid_answers","request_id":"f0ab3688-7609-419`
  - ✔ phone inválido «abc»: rechazado o marcado con error — `400 error=None {"detail":"Revisa: Teléfono: No es un teléfono válido.","code":"invalid_answers","request_id":"b8296595-cbeb-41b7-98f2-4`
  - ✔ Número por encima del máximo (home.household_members > 30.0) — `400 error=None`
  - ✔ Ningún 500 en las validaciones

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.
- [ ] Lo rechazado no queda guardado a medias.

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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
