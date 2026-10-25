# [VEN-003] La misma puerta otra vez reabre su expediente

## 1. Información general

- **ID:** VEN-003
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Volver a la misma dirección no crea un expediente duplicado.

## 3. Precondiciones

- VEN-001 ejecutado (puerta 101 en «Sin contacto»).

## 4. Datos de prueba

- La misma puerta de VEN-001: dirección «101 QA Mobile Park Dr», espacio «Spc 1», Phoenix, AZ, 85006; y la variante «101 qa mobile park dr.» en minúsculas.

## 5. Procedimiento paso a paso

1. [ ] Tocar una puerta con la dirección exacta de VEN-001 y resultado **Abrió y sigue**, programa Arizona.
2. [ ] Leer el aviso que muestra la pantalla.
3. [ ] Tocar otra puerta con la variante en minúsculas y con punto final, resultado **No abrió**.

## 6. Resultado esperado

- El primer intento muestra «Esta puerta ya tenía expediente: lo reabrimos» y usa el mismo expediente.
- Anotar si la variante escrita distinta reconoce la misma puerta o crea otra (riesgo conocido de direcciones duplicadas).

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo un expediente para la dirección exacta.
- [ ] El historial de etapas muestra la reapertura.

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
