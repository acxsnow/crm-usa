# [API-005] Límite de peticiones (rate limit)

## 1. Información general

- **ID:** API-005
- **Módulo:** API y paginación
- **Prioridad:** P2
- **Tipo de prueba:** Seguridad · disponibilidad
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

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

- A partir del tope responde 429 o deja de actuar sin decirlo (olvido de clave: responde 200 y no crea más de 3 enlaces por hora).

## 7. Resultado obtenido

- Qué pasó: 30 pedidos seguidos de olvido de clave responden 200, pero solo se crean 3 enlaces en la hora: el límite es silencioso para no revelar si el correo existe. La API sigue respondiendo a los demás.
- Diferencias con lo esperado: El escenario esperaba 429; el comportamiento real es correcto y más seguro (corregido el texto). Falta la ráfaga contra la firma pública del cliente (se hace después de INS-004).
- Comprobaciones por API (2 de 2):
  - ✔ 30 pedidos de olvido de clave: no hay 429, pero solo se crean 3 enlaces en la hora (límite silencioso, no revela si el correo existe) — `códigos=30×200; password_reset_tokens en la última hora=3`
  - ✔ la API sigue respondiendo a otros usuarios — `200`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] La API sigue respondiendo a los demás usuarios.

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
