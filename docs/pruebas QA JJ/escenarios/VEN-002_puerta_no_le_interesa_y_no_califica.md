# [VEN-002] No le interesa y no califica

## 1. Información general

- **ID:** VEN-002
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las dos salidas tempranas quedan registradas con su etapa propia.

## 3. Precondiciones

- Sesión de Vicky.

## 4. Datos de prueba

- Puerta A: dirección «102 QA Mobile Park Dr», espacio «Spc 2», Phoenix, AZ, 85006. Puerta B: dirección «103 QA Mobile Park Dr», espacio «Spc 3», Phoenix, AZ, 85006.

## 5. Procedimiento paso a paso

1. [ ] Tocar una puerta en A con resultado **No le interesa**.
2. [ ] Tocar una puerta en B con resultado **No califica**.
3. [ ] Revisar ambas en Expedientes con «Mostrar puertas cerradas».

## 6. Resultado esperado

- A queda en «No interesado» y B en «No califica», sin datos de cliente.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna de las dos crea obra, cobro ni cliente.

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
