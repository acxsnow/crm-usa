# [TUR-005] Horas extra y almuerzo según la forma de pago

## 1. Información general

- **ID:** TUR-005
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Regla de negocio · dinero
- **Estado:** FALLIDO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

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

- Qué pasó: Lote 3 por API (25 oct): 1 de 3 comprobaciones bien. Las reglas de nómina son de toda la organización: pausas pagadas sí/no, y extras calculadas solas desde 8 h al día y 40 a la semana.
- Diferencias con lo esperado: No hay dónde decir si a un técnico se le paga por día/hora o por trabajo, así que no se aplica la regla del almuerzo; y las extras no se declaran en horas con el valor que pone el jefe. Las dos son respuestas confirmadas por Don Aldo.
- Comprobaciones por API (1 de 3):
  - ✔ Reglas de nómina: pausas pagadas=False (para toda la organización), extras desde 480 min al día y 2400 a la semana — `{"late_tolerance_minutes": 10, "early_leave_tolerance_minutes": 10, "daily_overtime_after_minutes": 480, "weekly_overtime_after_minutes": 2400, "tracking_interv`
  - ✘ Se puede decir si a un técnico se le paga por hora/día o por trabajo (decisión de Don Aldo) — `campos del perfil: ['email', 'full_name', 'has_invitation', 'id', 'invited_at', 'invited_by', 'joined_at', 'last_login_at', 'role_names', 'roles', 'status', 'zo`
  - ✘ Las extras se declaran en horas y el jefe pone el valor — `{"date_from": "2026-10-25", "date_to": "2026-10-25", "period_status": "sin per\u00edodo", "rows": [{"user_id": "f1794000-8ca2-480f-bf1c-bfc1663e5d3f", "user_nam`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Valores en Decimal, sin centavos perdidos.

## 10. Resultado final

- [ ] APROBADO
- [x] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-019 | La nómina no aplica las reglas de Don Aldo: almuerzo según la forma de pago y extras declaradas con el valor del jefe | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
