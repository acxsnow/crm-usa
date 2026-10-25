# [INS-010] El técnico llega y el cliente no estaba

## 1. Información general

- **ID:** INS-010
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Bloqueado (D-001)
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El técnico registra la visita fallida con su motivo y evidencia, la obra vuelve a por agendar y el material queda decidido (se queda en la camioneta o se reintegra).

## 3. Precondiciones

- D-001 implementado.
- Una obra programada con material entregado (INS-003).

## 4. Datos de prueba

- Motivo: «Cliente no estaba»; foto de la puerta.

## 5. Procedimiento paso a paso

1. [ ] Como técnico, en la obra registrar **visita fallida** con el motivo y la foto.
2. [ ] Ver el estado de la obra y el contador de reagendamientos.
3. [ ] Como administración, ver el aviso y la obra en «por agendar».
4. [ ] Decidir el material: dejarlo en la camioneta o reintegrarlo a bodega (BOD-006).

## 6. Resultado esperado

- Sin motivo no se guarda.
- La obra queda sin fecha, con el contador en 1 y el motivo visible.
- El expediente no cambia de etapa (sigue en el tramo de campo).

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Evento registrado con GPS, fecha y técnico.
- [ ] Los pasos exactos se ajustan cuando D-001 esté hecho.

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
