# [REV-005] Cerrar un expediente desde cualquier etapa

## 1. Información general

- **ID:** REV-005
- **Módulo:** Revisión administrativa
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Cierre administrativo con motivo obligatorio.

## 3. Precondiciones

- Un expediente en «Nuevo prospecto» (puerta 205, «QA Cierre Paz»).

## 4. Datos de prueba

- Puerta: dirección «205 QA Mobile Park Dr», espacio «Spc 25», Phoenix, AZ, 85006; motivo «Cliente se mudó».

## 5. Procedimiento paso a paso

1. [ ] Como Andrés, en la revisión tocar **Cerrar expediente…**, primero sin motivo y luego con él.
2. [ ] Como Vicky, buscar el expediente.

## 6. Resultado esperado

- Sin motivo no cierra; con motivo queda «Cerrado» y ya no se edita.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] No se creó obra ni cobro.

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
