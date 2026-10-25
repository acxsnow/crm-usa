# [TUR-005] Horas extra y almuerzo según la forma de pago

## 1. Información general

- **ID:** TUR-005
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Regla de negocio · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Por día u hora el almuerzo va incluido; por trabajo no. Las extras se declaran en horas y el jefe pone el valor.

## 3. Precondiciones

- Un técnico pagado por hora y otro por trabajo, con turnos de 10 horas.

## 4. Datos de prueba

- 2 horas extra declaradas para el de por hora.

## 5. Procedimiento paso a paso

1. [ ] Registrar las jornadas y las extras.
2. [ ] Ver **Nómina** del periodo.

## 6. Resultado esperado

- El de por hora cobra con almuerzo incluido; el de por trabajo no cuenta almuerzo.
- Las extras salen en horas con el valor del jefe.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Valores en Decimal, sin centavos perdidos.

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
