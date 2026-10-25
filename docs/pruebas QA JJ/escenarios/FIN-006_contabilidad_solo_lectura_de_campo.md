# [FIN-006] Contabilidad no opera campo ni gerencia escribe

## 1. Información general

- **ID:** FIN-006
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Contabilidad no cierra instalaciones y Gerencia solo consulta.

## 3. Precondiciones

- Sesiones de contabilidad y gerencia.

## 4. Datos de prueba

- Una obra en curso; una factura emitida.

## 5. Procedimiento paso a paso

1. [ ] Como contabilidad, intentar registrar una jornada y autorizar una salida.
2. [ ] Como gerencia, intentar emitir, anular y pagar facturas.

## 6. Resultado esperado

- 403 en cada intento; las pantallas no muestran esos botones.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Comparar con `05_MATRIZ_PERMISOS.md`.

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
