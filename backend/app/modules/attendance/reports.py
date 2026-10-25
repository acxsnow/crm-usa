"""Panel de asistencia y reporte para nómina. Las fórmulas están en `calc.py`;
aquí solo se juntan los datos de un rango y se agrupan.

El panel nunca deduce ausencia de la conectividad: «turno», «ubicación» y
«verificado» son tres columnas separadas (spec, «Panel de Don Aldo»).
"""
import io
import uuid
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from xml.sax.saxutils import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance import calc
from app.modules.attendance.models import (
    AttendanceEvent,
    AttendanceNovelty,
    PayrollPeriod,
    TimeEntry,
    TimeEntryCorrection,
    WorkShift,
)
from app.modules.attendance.service import get_settings, now
from app.modules.users.models import User
from app.shared.datetime_utils import as_utc
from app.shared.errors import InvalidInputError

MAX_RANGE_DAYS = 62
FRESH_LOCATION = timedelta(minutes=15)


def _check_range(date_from: date, date_to: date) -> None:
    if date_to < date_from or (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise InvalidInputError(f"El rango debe ser de 1 a {MAX_RANGE_DAYS} días.", code="invalid_range")


async def _load(db: AsyncSession, organization_id: uuid.UUID, date_from: date, date_to: date,
                user_id: uuid.UUID | None, project_id: uuid.UUID | None):
    turnos = select(WorkShift).where(WorkShift.organization_id == organization_id,
                                     WorkShift.shift_date >= date_from, WorkShift.shift_date <= date_to)
    marcas = select(TimeEntry).where(TimeEntry.organization_id == organization_id,
                                     TimeEntry.work_date >= date_from, TimeEntry.work_date <= date_to)
    if user_id:
        turnos = turnos.where(WorkShift.user_id == user_id)
        marcas = marcas.where(TimeEntry.user_id == user_id)
    if project_id:
        turnos = turnos.where(WorkShift.project_id == project_id)
        con_obra = select(AttendanceEvent.time_entry_id).where(
            AttendanceEvent.organization_id == organization_id, AttendanceEvent.project_id == project_id)
        marcas = marcas.where((TimeEntry.shift_id.in_(select(WorkShift.id).where(
            WorkShift.organization_id == organization_id, WorkShift.project_id == project_id)))
            | TimeEntry.id.in_(con_obra))
    return list((await db.execute(turnos)).scalars()), list((await db.execute(marcas)).scalars())


async def _names(db, organization_id, ids) -> dict:
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.full_name).where(
        User.organization_id == organization_id, User.id.in_(ids)))).all())


async def dashboard(db: AsyncSession, *, organization_id: uuid.UUID, date_from: date, date_to: date,
                    user_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None) -> dict:
    _check_range(date_from, date_to)
    s = await get_settings(db, organization_id)
    ahora = now()
    turnos, marcas = await _load(db, organization_id, date_from, date_to, user_id, project_id)
    por_turno = {e.shift_id: e for e in marcas if e.shift_id}
    vivos = [t for t in turnos if t.status == "scheduled"]
    estados = {t.id: calc.shift_status(t, por_turno.get(t.id), now=ahora, late_tolerance=s.late_tolerance_minutes,
                                       early_tolerance=s.early_leave_tolerance_minutes) for t in vivos}
    horas = {e.id: calc.entry_hours(e, now=ahora, paid_pauses=s.paid_pauses) for e in marcas}
    cerradas = [e for e in marcas if e.status in ("closed", "approved")]

    pendientes = (await db.execute(select(func.count()).select_from(AttendanceNovelty).where(
        AttendanceNovelty.organization_id == organization_id, AttendanceNovelty.status == "pending",
        AttendanceNovelty.work_date >= date_from, AttendanceNovelty.work_date <= date_to,
        *( [AttendanceNovelty.user_id == user_id] if user_id else [])))).scalar_one()

    lista = list(estados.values())
    kpis = {
        "scheduled_people": len({t.user_id for t in vivos}),
        "started": sum(1 for t in vivos if t.id in por_turno),
        "pending_clock_in": lista.count(calc.PENDING),
        "late_arrivals": sum(1 for t in vivos if t.id in por_turno
                             and calc.late_minutes(t, por_turno[t.id].clock_in_at, s.late_tolerance_minutes) > 0),
        "early_departures": sum(1 for x in lista if x in (calc.EARLY, calc.LATE_EARLY)),
        "completed": sum(1 for x in lista if x in (calc.COMPLETED, calc.LATE, calc.EARLY, calc.LATE_EARLY)),
        "incomplete": lista.count(calc.INCOMPLETE),
        "missed": lista.count(calc.MISSED),
        "scheduled_minutes": sum(calc.scheduled_minutes(t) for t in vivos),
        "recorded_minutes": sum(horas[e.id].effective for e in cerradas),
        "open_minutes": sum(horas[e.id].effective for e in marcas if e.status == "open"),
        "approved_minutes": sum(e.approved_minutes or 0 for e in marcas if e.status == "approved"),
        "pending_novelties": pendientes,
        "compliance_pct": calc.compliance_pct(lista),
        "offline_marks": sum(1 for e in marcas if e.clock_in_offline or e.clock_out_offline),
    }

    # Por persona: programadas, registradas, aprobadas, puntualidad.
    personas: dict = defaultdict(lambda: {"scheduled": 0, "recorded": 0, "approved": 0, "late": 0, "shifts": 0,
                                          "statuses": []})
    for t in vivos:
        p = personas[t.user_id]
        p["scheduled"] += calc.scheduled_minutes(t)
        p["shifts"] += 1
        p["statuses"].append(estados[t.id])
        if t.id in por_turno and calc.late_minutes(t, por_turno[t.id].clock_in_at, s.late_tolerance_minutes):
            p["late"] += 1
    for e in cerradas:
        personas[e.user_id]["recorded"] += horas[e.id].effective
        personas[e.user_id]["approved"] += e.approved_minutes or 0 if e.status == "approved" else 0
    nombres = await _names(db, organization_id, list(personas))
    por_persona = sorted(({
        "user_id": str(uid), "user_name": nombres.get(uid, "—"), "scheduled_minutes": v["scheduled"],
        "recorded_minutes": v["recorded"], "approved_minutes": v["approved"], "shifts": v["shifts"],
        "late": v["late"], "compliance_pct": calc.compliance_pct(v["statuses"]),
    } for uid, v in personas.items()), key=lambda r: r["user_name"])

    # Puntualidad por día: entradas a tiempo ÷ entradas con turno.
    dias: dict = defaultdict(lambda: [0, 0])
    for t in vivos:
        e = por_turno.get(t.id)
        if e is None:
            continue
        dias[t.shift_date][1] += 1
        if not calc.late_minutes(t, e.clock_in_at, s.late_tolerance_minutes):
            dias[t.shift_date][0] += 1
    puntualidad = [{"date": (date_from + timedelta(days=i)).isoformat(),
                    "on_time": dias[date_from + timedelta(days=i)][0],
                    "with_entry": dias[date_from + timedelta(days=i)][1],
                    "pct": round(100 * dias[date_from + timedelta(days=i)][0] / dias[date_from + timedelta(days=i)][1],
                                 1) if dias[date_from + timedelta(days=i)][1] else None}
                   for i in range((date_to - date_from).days + 1)]
    return {"kpis": kpis, "by_person": por_persona, "punctuality": puntualidad,
            "settings": {"late_tolerance_minutes": s.late_tolerance_minutes,
                         "early_leave_tolerance_minutes": s.early_leave_tolerance_minutes}}


async def live_board(db: AsyncSession, *, organization_id: uuid.UUID, with_locations: bool) -> list[dict]:
    """El tablero de hoy, una fila por persona con turno hoy o marcación abierta,
    con las tres columnas separadas: turno, ubicación y verificado."""
    from app.modules.field_ops import clock

    s = await get_settings(db, organization_id)
    ahora = now()
    hoy = await clock.org_today(db, organization_id)
    turnos = list((await db.execute(select(WorkShift).where(
        WorkShift.organization_id == organization_id, WorkShift.status == "scheduled",
        WorkShift.shift_date == hoy))).scalars())
    abiertas = list((await db.execute(select(TimeEntry).where(
        TimeEntry.organization_id == organization_id,
        (TimeEntry.status == "open") | (TimeEntry.work_date == hoy)))).scalars())
    por_turno = {e.shift_id: e for e in abiertas if e.shift_id}
    usuarios = {t.user_id for t in turnos} | {e.user_id for e in abiertas}
    nombres = await _names(db, organization_id, list(usuarios))
    ultimos = await last_locations(db, organization_id, list(usuarios)) if with_locations else {}
    filas = []
    for uid in usuarios:
        mios = sorted((x for x in turnos if x.user_id == uid), key=lambda x: x.starts_at)
        abierta = next((x for x in abiertas if x.user_id == uid and x.status == "open"), None)
        if abierta is not None:
            # Manda lo que está pasando ahora: la marcación abierta y su turno.
            e = abierta
            t = next((x for x in mios if x.id == abierta.shift_id), None)
        else:
            # El turno que sigue vigente; si todos terminaron, el último del día.
            t = next((x for x in mios if as_utc(x.ends_at) > ahora), mios[-1] if mios else None)
            e = por_turno.get(t.id) if t else None
            e = e or next((x for x in abiertas if x.user_id == uid), None)
        estado = calc.shift_status(t, e, now=ahora, late_tolerance=s.late_tolerance_minutes,
                                   early_tolerance=s.early_leave_tolerance_minutes) if t else (
            "unscheduled_open" if e and e.status == "open" else "unscheduled")
        ubic = ultimos.get(uid)
        fila = {
            "user_id": str(uid), "user_name": nombres.get(uid, "—"),
            "shift": {"starts_at": as_utc(t.starts_at).isoformat(), "ends_at": as_utc(t.ends_at).isoformat()}
            if t else None,
            "shift_status": estado,
            "entry_status": e.status if e else None,
            "clock_in_at": as_utc(e.clock_in_at).isoformat() if e else None,
            "clock_out_at": as_utc(e.clock_out_at).isoformat() if e and e.clock_out_at else None,
            "paused": bool(e and any(p.ended_at is None for p in e.pauses)),
            "offline": bool(e and (e.clock_in_offline or e.clock_out_offline)),
            # Verificado = aprobado por Administración, no «tuvo señal».
            "verified": bool(e and e.status == "approved"),
            "location": None,
        }
        if ubic:
            edad = int((ahora - as_utc(ubic["at"])).total_seconds() // 60)
            fila["location"] = {**{k: v for k, v in ubic.items() if k != "at"},
                                "at": as_utc(ubic["at"]).isoformat(), "age_minutes": edad,
                                "fresh": edad <= FRESH_LOCATION.total_seconds() / 60}
        filas.append(fila)
    return sorted(filas, key=lambda f: f["user_name"])


async def last_locations(db: AsyncSession, organization_id: uuid.UUID, user_ids: list) -> dict:
    """La última ubicación conocida de cada persona (no la actual: la de su
    última marca con GPS)."""
    if not user_ids:
        return {}
    ultima = (select(AttendanceEvent.user_id, func.max(AttendanceEvent.occurred_at).label("at"))
              .where(AttendanceEvent.organization_id == organization_id, AttendanceEvent.user_id.in_(user_ids),
                     AttendanceEvent.location_status == "ok")
              .group_by(AttendanceEvent.user_id).subquery())
    filas = (await db.execute(select(AttendanceEvent).join(
        ultima, (ultima.c.user_id == AttendanceEvent.user_id) & (ultima.c.at == AttendanceEvent.occurred_at)
    ).where(AttendanceEvent.organization_id == organization_id, AttendanceEvent.location_status == "ok"))).scalars()
    salida = {}
    for ev in filas:
        salida[ev.user_id] = {"latitude": ev.latitude, "longitude": ev.longitude, "accuracy_m": ev.accuracy_m,
                              "event_type": ev.event_type, "at": ev.occurred_at,
                              "project_id": str(ev.project_id) if ev.project_id else None}
    return salida


# ---------------------------------------------------------------------------
# Nómina
# ---------------------------------------------------------------------------

async def payroll_report(db: AsyncSession, *, organization_id: uuid.UUID, date_from: date, date_to: date,
                         user_id: uuid.UUID | None = None) -> dict:
    _check_range(date_from, date_to)
    s = await get_settings(db, organization_id)
    ahora = now()
    turnos, marcas = await _load(db, organization_id, date_from, date_to, user_id, None)
    vivos = [t for t in turnos if t.status == "scheduled"]
    por_turno = {e.shift_id: e for e in marcas if e.shift_id}
    usuarios = {t.user_id for t in vivos} | {e.user_id for e in marcas}
    if not user_id:
        usuarios |= set((await db.execute(select(TimeEntry.user_id).where(
            TimeEntry.organization_id == organization_id, TimeEntry.work_date >= date_from,
            TimeEntry.work_date <= date_to))).scalars())
    nombres = await _names(db, organization_id, list(usuarios))
    correcciones = defaultdict(int)
    ids = [e.id for e in marcas]
    if ids:
        for eid, n in (await db.execute(select(TimeEntryCorrection.time_entry_id, func.count()).where(
                TimeEntryCorrection.organization_id == organization_id,
                TimeEntryCorrection.time_entry_id.in_(ids)).group_by(TimeEntryCorrection.time_entry_id))).all():
            correcciones[eid] = n
    novedades = defaultdict(int)
    for uid, n in (await db.execute(select(AttendanceNovelty.user_id, func.count()).where(
            AttendanceNovelty.organization_id == organization_id, AttendanceNovelty.work_date >= date_from,
            AttendanceNovelty.work_date <= date_to).group_by(AttendanceNovelty.user_id))).all():
        novedades[uid] = n

    filas = []
    for uid in usuarios:
        mis_turnos = [t for t in vivos if t.user_id == uid]
        mis_marcas = [e for e in marcas if e.user_id == uid]
        cerradas = [e for e in mis_marcas if e.status in ("closed", "approved")]
        horas = {e.id: calc.entry_hours(e, now=ahora, paid_pauses=s.paid_pauses) for e in cerradas}
        por_dia = defaultdict(int)
        for e in cerradas:
            por_dia[e.work_date] += horas[e.id].effective
        ext_d, ext_s = calc.overtime(por_dia, daily_after=s.daily_overtime_after_minutes,
                                     weekly_after=s.weekly_overtime_after_minutes)
        estados = [calc.shift_status(t, por_turno.get(t.id), now=ahora, late_tolerance=s.late_tolerance_minutes,
                                     early_tolerance=s.early_leave_tolerance_minutes) for t in mis_turnos]
        filas.append({
            "user_id": str(uid), "user_name": nombres.get(uid, "—"),
            "scheduled_minutes": sum(calc.scheduled_minutes(t) for t in mis_turnos),
            "recorded_minutes": sum(h.effective for h in horas.values()),
            "pause_minutes": sum(h.pauses for h in horas.values()),
            "daily_overtime_minutes": ext_d, "weekly_overtime_minutes": ext_s,
            "approved_minutes": sum(e.approved_minutes or 0 for e in mis_marcas if e.status == "approved"),
            "absences": estados.count(calc.MISSED),
            "late_arrivals": sum(1 for x in estados if x in (calc.LATE, calc.LATE_EARLY)),
            "early_departures": sum(1 for x in estados if x in (calc.EARLY, calc.LATE_EARLY)),
            "open_entries": sum(1 for e in mis_marcas if e.status == "open"),
            "unapproved_entries": sum(1 for e in mis_marcas if e.status == "closed"),
            "corrections": sum(correcciones[e.id] for e in mis_marcas),
            "novelties": novedades[uid],
        })
    filas.sort(key=lambda f: f["user_name"])
    periodo = (await db.execute(select(PayrollPeriod).where(
        PayrollPeriod.organization_id == organization_id, PayrollPeriod.start_date == date_from,
        PayrollPeriod.end_date == date_to))).scalar_one_or_none()
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
            "period_status": periodo.status if periodo else "sin período", "rows": filas,
            "rules": {"daily_overtime_after_minutes": s.daily_overtime_after_minutes,
                      "weekly_overtime_after_minutes": s.weekly_overtime_after_minutes,
                      "paid_pauses": s.paid_pauses}}


COLUMNS = [
    ("user_name", "Empleado"), ("scheduled_minutes", "Horas programadas"), ("recorded_minutes", "Horas registradas"),
    ("pause_minutes", "Pausas"), ("daily_overtime_minutes", "Extras diarias"),
    ("weekly_overtime_minutes", "Extras semanales"), ("approved_minutes", "Horas aprobadas"),
    ("absences", "Ausencias"), ("late_arrivals", "Llegadas tarde"), ("early_departures", "Salidas anticipadas"),
    ("corrections", "Correcciones"), ("novelties", "Novedades"), ("open_entries", "Sin salida"),
    ("unapproved_entries", "Sin aprobar"),
]
MINUTE_COLUMNS = {k for k, _ in COLUMNS if k.endswith("_minutes")}


def _hours(minutes: int) -> float:
    return round(minutes / 60, 2)


def to_xlsx(report: dict) -> bytes:
    """Un .xlsx mínimo escrito a mano (sin dependencias nuevas): una hoja con
    encabezado y una fila por persona. Las horas van en horas decimales."""
    filas = [[f"Nómina {report['date_from']} a {report['date_to']} · {report['period_status']}"],
             [t for _, t in COLUMNS]]
    for r in report["rows"]:
        filas.append([_hours(r[k]) if k in MINUTE_COLUMNS else r[k] for k, _ in COLUMNS])

    def celda(ref: str, valor) -> str:
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return f'<c r="{ref}"><v>{valor}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(valor))}</t></is></c>'

    def col(i: int) -> str:
        letras = ""
        i += 1
        while i:
            i, resto = divmod(i - 1, 26)
            letras = chr(65 + resto) + letras
        return letras

    hoja = "".join(f'<row r="{n + 1}">' + "".join(celda(f"{col(i)}{n + 1}", v) for i, v in enumerate(fila))
                   + "</row>" for n, fila in enumerate(filas))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/'
                   '2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
                   'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
                   'officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/'
                   'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                   'relationships"><sheets><sheet name="Nomina" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/'
                   f'spreadsheetml/2006/main"><sheetData>{hoja}</sheetData></worksheet>')
    return buf.getvalue()


def to_pdf(report: dict, organization_name: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24,
                            bottomMargin=24, title="Reporte de nómina")
    estilos = getSampleStyleSheet()
    reglas = report["rules"]
    partes = [
        Paragraph(f"{escape(organization_name)} · Reporte para nómina", estilos["Title"]),
        Paragraph(f"Del {report['date_from']} al {report['date_to']} · Período: {report['period_status']}. "
                  f"Horas en horas decimales. Extras desde {_hours(reglas['daily_overtime_after_minutes'])} h al día "
                  f"y {_hours(reglas['weekly_overtime_after_minutes'])} h a la semana. "
                  "Este reporte no calcula pagos ni descuentos.", estilos["Normal"]),
        Spacer(1, 10),
    ]
    datos = [[t for _, t in COLUMNS]]
    for r in report["rows"]:
        datos.append([_hours(r[k]) if k in MINUTE_COLUMNS else r[k] for k, _ in COLUMNS])
    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    partes.append(tabla)
    doc.build(partes)
    return buf.getvalue()

