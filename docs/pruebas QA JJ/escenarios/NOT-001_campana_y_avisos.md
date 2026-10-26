# [NOT-001] Campana de avisos en cada paso del flujo

## 1. Información general

- **ID:** NOT-001
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Cada persona recibe el aviso que le toca y solo ese.

## 3. Precondiciones

- Haber corrido VEN-004, REV-002, INS-001 e INS-005.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Entrar con Vicky, Andrés y Carlos y revisar la campana.
2. [ ] Marcar uno como leído y recargar.

## 6. Resultado esperado

- Cada uno ve sus avisos; el leído se mantiene leído.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 7 de 7 comprobaciones bien. Vicky, Administración y Tito ven cada uno sus avisos y ninguno aparece en la campana de otro; Tito no puede marcar un aviso de Vicky; el leído sigue leído al recargar.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ Vicky ve sus avisos (2) — `2`
  - ✔ Administración ve sus avisos (7) — `7`
  - ✔ Tito ve sus avisos (6) — `6`
  - ✔ Ningún aviso aparece en la campana de otro — `{'Vicky': 2, 'Administración': 7, 'Tito': 6}`
  - ✔ Tito no puede marcar como leído un aviso de Vicky — `404`
  - ✔ Vicky marca uno como leído
  - ✔ Al recargar sigue leído — `True`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Nadie ve avisos de otro usuario.

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
