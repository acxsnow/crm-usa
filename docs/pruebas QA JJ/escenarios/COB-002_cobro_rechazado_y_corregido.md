# [COB-002] El programa rechaza el cobro: corregir y volver a radicar

## 1. Información general

- **ID:** COB-002
- **Módulo:** Cobro al programa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Un rechazo del programa queda con su motivo y se puede corregir sin crear otro cobro.

## 3. Precondiciones

- COB-001 hecho.

## 4. Datos de prueba

- Motivo: «Falta el formulario de reducción de carbono».

## 5. Procedimiento paso a paso

1. [ ] Registrar el rechazo con el motivo (y sin él).
2. [ ] Corregir adjuntando el documento.
3. [ ] Radicar de nuevo.

## 6. Resultado esperado

- «En cobro: rechazado, en corrección» y luego radicado otra vez.
- Sin motivo no se guarda el rechazo.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un solo cobro para la obra, con el historial de los dos radicados.

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
