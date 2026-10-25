"""Fórmulas de horas del panel y la nómina (`attendance/calc.py`)."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS

from app.modules.attendance import calc, geo

T0 = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)  # lunes


def _shift(start=T0, hours=8, break_minutes=30, status="scheduled"):
    return NS(starts_at=start, ends_at=start + timedelta(hours=hours), break_minutes=break_minutes, status=status)


def _entry(cin, cout=None, pauses=()):
    return NS(clock_in_at=cin, clock_out_at=cout, pauses=list(pauses))


def test_horas_efectivas_restan_pausas_recortadas_a_la_jornada():
    e = _entry(T0, T0 + timedelta(hours=9), [
        NS(started_at=T0 + timedelta(hours=4), ended_at=T0 + timedelta(hours=4, minutes=30)),
        # Una pausa que quedó abierta cuenta hasta la salida.
        NS(started_at=T0 + timedelta(hours=8, minutes=45), ended_at=None),
    ])
    h = calc.entry_hours(e, now=T0 + timedelta(hours=12))
    assert (h.elapsed, h.pauses, h.effective) == (540, 45, 495)
    assert calc.entry_hours(e, now=T0, paid_pauses=True).effective == 540


def test_marcacion_abierta_cuenta_hasta_ahora():
    assert calc.entry_hours(_entry(T0), now=T0 + timedelta(minutes=95)).effective == 95


def test_programadas_restan_el_descanso():
    assert calc.scheduled_minutes(_shift()) == 450


def test_tardanza_solo_pasada_la_tolerancia_y_contada_desde_el_inicio():
    s = _shift()
    assert calc.late_minutes(s, T0 + timedelta(minutes=10), 10) == 0
    assert calc.late_minutes(s, T0 + timedelta(minutes=11), 10) == 11
    assert calc.late_minutes(s, T0 - timedelta(minutes=30), 10) == 0


def test_salida_anticipada():
    s = _shift()
    assert calc.early_leave_minutes(s, s.ends_at - timedelta(minutes=10), 10) == 0
    assert calc.early_leave_minutes(s, s.ends_at - timedelta(minutes=40), 10) == 40
    assert calc.early_leave_minutes(s, None, 10) == 0


def test_estados_del_turno():
    s = _shift()
    kw = dict(late_tolerance=10, early_tolerance=10)
    assert calc.shift_status(s, None, now=T0 + timedelta(minutes=5), **kw) == calc.UPCOMING
    assert calc.shift_status(s, None, now=T0 + timedelta(minutes=20), **kw) == calc.PENDING
    assert calc.shift_status(s, None, now=s.ends_at, **kw) == calc.MISSED
    assert calc.shift_status(s, _entry(T0), now=T0 + timedelta(hours=2), **kw) == calc.IN_PROGRESS
    assert calc.shift_status(s, _entry(T0), now=s.ends_at + timedelta(minutes=30), **kw) == calc.INCOMPLETE
    assert calc.shift_status(s, _entry(T0, s.ends_at), now=s.ends_at, **kw) == calc.COMPLETED
    assert calc.shift_status(s, _entry(T0 + timedelta(minutes=30), s.ends_at), now=s.ends_at, **kw) == calc.LATE
    assert calc.shift_status(s, _entry(T0, s.ends_at - timedelta(hours=1)), now=s.ends_at, **kw) == calc.EARLY
    assert calc.shift_status(_shift(status="cancelled"), None, now=T0, **kw) == calc.CANCELLED


def test_turno_nocturno_que_cruza_la_medianoche():
    noche = _shift(start=datetime(2026, 10, 26, 5, 0, tzinfo=timezone.utc), hours=10, break_minutes=0)
    e = _entry(noche.starts_at, noche.ends_at)
    assert calc.entry_hours(e, now=noche.ends_at).effective == 600
    assert calc.shift_status(noche, e, now=noche.ends_at, late_tolerance=10, early_tolerance=10) == calc.COMPLETED


def test_extras_diarias_y_semanales_no_se_cuentan_dos_veces():
    lunes = date(2026, 10, 26)
    # 5 días de 10 h: 2 h extra diarias cada día = 600; regulares 8 × 5 = 40 h → 0 semanales.
    dias = {lunes + timedelta(days=i): 600 for i in range(5)}
    assert calc.overtime(dias, daily_after=480, weekly_after=2400) == (600, 0)
    # 6 días de 8 h: sin extra diaria; 48 h regulares → 8 h semanales.
    dias = {lunes + timedelta(days=i): 480 for i in range(6)}
    assert calc.overtime(dias, daily_after=480, weekly_after=2400) == (0, 480)
    # Umbrales apagados.
    assert calc.overtime(dias, daily_after=0, weekly_after=0) == (0, 0)


def test_cumplimiento_cuenta_solo_turnos_vencidos():
    assert calc.compliance_pct([calc.UPCOMING, calc.PENDING]) is None
    assert calc.compliance_pct([calc.COMPLETED, calc.LATE, calc.MISSED, calc.IN_PROGRESS, calc.INCOMPLETE]) == 25.0


def test_distancias_y_orden_por_cercania():
    # Phoenix → Tempe ~ 14 km en línea recta.
    km = geo.haversine_km(33.4484, -112.0740, 33.4255, -111.9400)
    assert 12 < km < 15
    paradas = [{"id": "lejos", "latitude": 33.6, "longitude": -112.3},
               {"id": "cerca", "latitude": 33.45, "longitude": -112.08},
               {"id": "sin", "latitude": None, "longitude": None}]
    orden = geo.nearest_neighbor_order((33.4484, -112.0740), paradas)
    assert [p["id"] for p in orden] == ["cerca", "lejos", "sin"]
    url = geo.google_maps_directions_url((33.4484, -112.0740), orden)
    assert url.startswith("https://www.google.com/maps/dir/?api=1") and "waypoints=" in url
    assert not geo.valid_point(0, 0) and not geo.valid_point(91, 0) and geo.valid_point(33.4, -112.0)
