# [BUS-001] Buscador global por nombre, número y dirección

## 1. Información general

- **ID:** BUS-001
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El buscador de arriba encuentra clientes, expedientes, obras y facturas del usuario.

## 3. Precondiciones

- Datos creados en VEN y PAR.

## 4. Datos de prueba

- «Rivera», el número CASE-…, «QA Mobile», el número de factura, «zzz».

## 5. Procedimiento paso a paso

1. [ ] Buscar cada término como admin.
2. [ ] Buscar «Rivera» como Valeria y como Carlos.
3. [ ] Buscar «Cliente Ajeno QA».

## 6. Resultado esperado

- Admin encuentra todo; cada rol solo lo suyo; «zzz» dice que no hay resultados.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Nunca aparece nada de la organización ajena.
- [ ] Responde en menos de 500 ms.

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
