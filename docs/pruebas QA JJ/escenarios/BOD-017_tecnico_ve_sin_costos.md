# [BOD-017] El técnico ve su camioneta sin costos

## 1. Información general

- **ID:** BOD-017
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Los costos de bodega son información de la empresa, no del técnico.

## 3. Precondiciones

- Material en la camioneta de Carlos.

## 4. Datos de prueba

- Token de Carlos.

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, abrir lo que puede ver de bodega y su camioneta.
2. [ ] Llamar `GET /api/v1/warehouse/stock` con su token.

## 6. Resultado esperado

- No ve costos ni valor en pantalla ni en la respuesta JSON.
- No ve la bodega de otras camionetas.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Revisar el JSON completo: ni `unit_cost` ni totales en dinero.

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
