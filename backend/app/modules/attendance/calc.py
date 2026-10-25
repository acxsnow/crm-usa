"""Cálculos de horas, sin base de datos: lo que el panel y la nómina dicen
sale de aquí, y por eso se prueba aparte (`tests/test_attendance_calc.py`).

Fórmulas del spec (sección «Panel de Don Aldo y nómina»):

- Horas transcurridas = salida − entrada.
- Pausas = suma de cada pausa recortada a la jornada (una pausa sin cerrar
  cuenta hasta la salida).
- Horas efectivas = transcurridas − pausas, salvo que las pausas se paguen.
- Tarde = entrada > inicio programado + tolerancia. Los minutos de tardanza se
  cuentan desde el inicio, no desde la tolerancia.
- Salida anticipada = salida < fin programado − tolerancia.
- Programadas = fin − inicio − descanso programado.
- Extras: lo que pasa del umbral diario por día; de lo que queda, lo que pasa
  del umbral semanal (lunes a domingo). Así una hora no cuenta dos veces.

Una desconexión no aparece en ninguna fórmula: no resta ni suma.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.shared.datetime_utils import as_utc


def minutes_between(start: datetime, end: datetime) -> int:
    return max(0, int((as_utc(end) - as_utc(start)).total_seconds() // 60))


def pause_minutes(pauses, *, entry_start: datetime, entry_end: datetime) -> int:
    """`pauses`: objetos con `started_at` y `ended_at` (None = sigue abierta)."""
    total = 0
    inicio, fin = as_utc(entry_start), as_utc(entry_end)
    for p in pauses:
        desde = max(as_utc(p.started_at), inicio)
        hasta = min(as_utc(p.ended_at) if p.ended_at else fin, fin)
        if hasta > desde:
            total += minutes_between(desde, hasta)
    return total


@dataclass(frozen=True)
class EntryHours:
    elapsed: int
    pauses: int
    effective: int


def entry_hours(entry, *, now: datetime, paid_pauses: bool = False) -> EntryHours:
    """Horas de una marcación. Si sigue abierta, hasta `now`."""
    fin = entry.clock_out_at or now
    transcurridas = minutes_between(entry.clock_in_at, fin)
    pausas = pause_minutes(entry.pauses, entry_start=entry.clock_in_at, entry_end=fin)
    efectivas = transcurridas if paid_pauses else max(0, transcurridas - pausas)
    return EntryHours(transcurridas, pausas, efectivas)


def scheduled_minutes(shift) -> int:
    return max(0, minutes_between(shift.starts_at, shift.ends_at) - (shift.break_minutes or 0))


def late_minutes(shift, clock_in_at: datetime, tolerance: int) -> int:
    """Minutos de tardanza, o 0 si entró dentro de la tolerancia."""
    tarde = minutes_between(shift.starts_at, clock_in_at)
    return tarde if tarde > tolerance else 0


def early_leave_minutes(shift, clock_out_at: datetime | None, tolerance: int) -> int:
    if clock_out_at is None:
        return 0
    antes = minutes_between(clock_out_at, shift.ends_at)
    return antes if antes > tolerance else 0


# Estado de un turno de la malla frente a lo que pasó.
UPCOMING = "upcoming"          # todavía no empieza
PENDING = "pending"            # empezó (más la tolerancia) y no ha marcado
IN_PROGRESS = "in_progress"    # marcó y no ha salido, dentro de su horario
COMPLETED = "completed"        # entró y salió dentro de las tolerancias
LATE = "late"                  # completo, pero entró tarde
EARLY = "early_departure"      # completo, pero salió antes
LATE_EARLY = "late_and_early"
INCOMPLETE = "incomplete"      # marcó entrada, el turno ya terminó y no hay salida
MISSED = "missed"              # el turno terminó y nunca marcó (no es ausencia confirmada)
CANCELLED = "cancelled"

# Lo que cuenta como «cumplido» para el indicador de cumplimiento de malla.
COMPLIANT = {COMPLETED}
# Turnos ya vencidos: el denominador del cumplimiento.
DUE = {COMPLETED, LATE, EARLY, LATE_EARLY, INCOMPLETE, MISSED}


def shift_status(shift, entry, *, now: datetime, late_tolerance: int, early_tolerance: int) -> str:
    if shift.status == "cancelled":
        return CANCELLED
    now = as_utc(now)
    if entry is None:
        if now < as_utc(shift.starts_at) + timedelta(minutes=late_tolerance):
            return UPCOMING
        return MISSED if now >= as_utc(shift.ends_at) else PENDING
    if entry.clock_out_at is None:
        return INCOMPLETE if now >= as_utc(shift.ends_at) + timedelta(minutes=early_tolerance) else IN_PROGRESS
    tarde = late_minutes(shift, entry.clock_in_at, late_tolerance) > 0
    antes = early_leave_minutes(shift, entry.clock_out_at, early_tolerance) > 0
    if tarde and antes:
        return LATE_EARLY
    if tarde:
        return LATE
    if antes:
        return EARLY
    return COMPLETED


def overtime(minutes_by_day: dict[date, int], *, daily_after: int, weekly_after: int) -> tuple[int, int]:
    """(extras diarias, extras semanales) de un conjunto de días de una persona.
    Un umbral en 0 está apagado."""
    diarias = 0
    regulares_por_semana: dict[tuple[int, int], int] = defaultdict(int)
    for dia, minutos in minutes_by_day.items():
        extra = max(0, minutos - daily_after) if daily_after else 0
        diarias += extra
        regulares_por_semana[dia.isocalendar()[:2]] += minutos - extra
    semanales = 0
    if weekly_after:
        semanales = sum(max(0, m - weekly_after) for m in regulares_por_semana.values())
    return diarias, semanales


def compliance_pct(statuses: list[str]) -> float | None:
    """Turnos cumplidos ÷ turnos vencidos, en porcentaje. None si no venció ninguno."""
    vencidos = [s for s in statuses if s in DUE]
    if not vencidos:
        return None
    return round(100 * sum(1 for s in vencidos if s in COMPLIANT) / len(vencidos), 1)
