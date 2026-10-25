# [BOD-015] Cantidades y costos extremos

## 1. Información general

- **ID:** BOD-015
- **Módulo:** Bodega
- **Prioridad:** P2
- **Tipo de prueba:** Validación
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La bodega no acepta cantidades imposibles.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Cantidades: 0, -1, 0.0001, 1e9, «1,5»; costo 9999999.99.

## 5. Procedimiento paso a paso

1. [ ] Probar cada valor en entrada, salida y ajuste.
2. [ ] Mirar la respuesta de la API.

## 6. Resultado esperado

- Rechaza 0 y negativos donde no aplican; decimales según la unidad; nunca un 500.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Los totales con montos grandes no se desbordan ni redondean mal.

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
