# [REV-006] El vendedor no puede aprobar su propio expediente (SEG-07)

## 1. Información general

- **ID:** REV-006
- **Módulo:** Revisión administrativa
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 1 de 1 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (1 de 1):
  - ✔ El vendedor no puede aprobar su expediente

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna obra creada.

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
