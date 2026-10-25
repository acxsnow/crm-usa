# [REV-004] Poner en espera, rechazar con motivo y reenviar un rechazado

## 1. Información general

- **ID:** REV-004
- **Módulo:** Revisión administrativa
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las salidas no felices del programa quedan registradas y un rechazado se puede corregir.

## 3. Precondiciones

- Un expediente enviado (VEN-004 con la puerta 204, «QA Espera León»).

## 4. Datos de prueba

- Puerta: dirección «204 QA Mobile Park Dr», espacio «Spc 24», Phoenix, AZ, 85006; motivos «Programa sin cupo» y «No cumple requisito de ingresos».

## 5. Procedimiento paso a paso

1. [ ] Como Andrés, **Poner en espera del programa** con el primer motivo.
2. [ ] Sacarlo de la espera (volver a revisión).
3. [ ] **Rechazar** con el segundo motivo; intentar rechazar sin motivo.
4. [ ] Como Vicky, abrir el rechazado, corregir y reenviar.

## 6. Resultado esperado

- Rechazar sin motivo no se permite.
- El rechazado se puede editar y reenviar.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Todos los cambios en el historial con su motivo.

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
