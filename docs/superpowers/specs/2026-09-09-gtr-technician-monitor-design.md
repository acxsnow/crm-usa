# Monitor GTR de técnicos de campo (Fase 2)

Fecha: 2026-09-09
Estado: aprobado por el usuario, pendiente de plan de implementación.

## Contexto

Segundo sub-proyecto de la iniciativa iniciada con la Fase 1
(`docs/superpowers/specs/2026-09-09-tabla-filtros-reutilizables-design.md`,
ya implementada y en `main`). El usuario pidió una vista de control estilo
GTR (call-center) adaptada a los técnicos de campo del CRM: quién está
logueado, quién está disponible/en cola, cuántos casos tiene asignados,
cuántos gestionó, y su tiempo de gestión — usando la referencia visual de
un sistema externo solo como inspiración de estructura, no de contenido ni
marca.

Decisiones ya confirmadas con el usuario durante el brainstorming:

- **Alcance de roles**: solo técnicos de campo (`field_technician`), no
  agentes de CRM ni todos los roles.
- **"En vivo" simple**: sin websockets. "Logueado" se deriva de actividad
  de sesión reciente; "en cola/disponible" es un toggle manual, no un
  estado de presencia en tiempo real.
- **Control del toggle**: solo admin/supervisor lo cambia, desde esta
  misma vista — el técnico no tiene una UI propia para esto.
- **Periodo de métricas**: "casos gestionados" y "tiempo de gestión" son
  del día de hoy (como un turno), no acumulados históricos.

## Objetivo

Una página nueva, `/technician-monitor`, con una fila por técnico de
campo de la organización, mostrando: nombre, logueado (sí/no), en cola
(toggle), casos asignados (proyectos activos), casos gestionados hoy,
tiempo de gestión promedio de hoy. Reutiliza `DataTable` (Fase 1); no
requiere `FilterBar` en esta primera versión — la tabla es de a lo sumo
unas pocas decenas de filas (un técnico por fila).

Fuera de alcance: agentes de CRM/ventas, presencia en tiempo real vía
websockets, autogestión del técnico sobre su propia disponibilidad,
historial/series de tiempo de métricas (solo el snapshot de "hoy").

## Modelo de datos

Dos columnas nuevas en `User` (`backend/app/modules/users/models.py`):

```python
last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Migración Alembic `0008_user_presence.py` (`down_revision = "0007"`),
agregando ambas columnas a `users` (nullable / con `server_default=false()`
para `is_available` igual que otros booleanos del esquema).

## "Logueado" — heartbeat sin nueva infraestructura

`app/api/deps.py::get_current_user` ya corre en **todo** request
autenticado (vía `Depends`). Se añade ahí, después de cargar el usuario:

```python
now = datetime.now(timezone.utc)
if user.last_seen_at is None or (now - as_utc(user.last_seen_at)) > timedelta(minutes=2):
    user.last_seen_at = now
    await db.commit()
```

Throttle de 2 minutos: evita un `UPDATE` en cada request (que en un CRM de
uso normal serían decenas por minuto por usuario activo) sin perder
precisión útil para un indicador que solo necesita granularidad de
"minutos". El commit es seguro en este punto porque `get_current_user` es
de las primeras dependencias en resolverse — no hay otros cambios
pendientes en la sesión todavía que este commit pudiera disparar
prematuramente.

Un técnico se considera **logueado** (columna calculada en la respuesta,
no almacenada) si `last_seen_at` está dentro de los últimos 5 minutos al
momento de responder — umbral mayor al throttle de escritura para
absorber el margen entre el último heartbeat y el momento de lectura.

## Backend — endpoints nuevos

Ambos en `backend/app/modules/field_ops/router.py` (mismo módulo que
`Project`), gateados con el permiso ya existente `dashboards.operations`
(lo tienen `project_manager` y `supervisor`; `organization_admin` y
`platform_super_admin` tienen todos los permisos).

### `GET /field-ops/technician-monitor`

```python
class TechnicianMonitorRow(BaseModel):
    user_id: uuid.UUID
    full_name: str
    logueado: bool
    en_cola: bool
    casos_asignados: int
    casos_gestionados_hoy: int
    tiempo_gestion_hoy_dias: float | None  # None si no completó nada hoy
```

Query: todos los `User` de la org con rol `field_technician` (join
`UserRole`/`Role` igual que el filtro `role` de `/users` en la Fase 1),
`status == active`. Para cada uno:

- `casos_asignados`: `count(Project)` donde
  `primary_technician_user_id == user.id` y
  `status IN (planning, scheduled, in_progress)`.
- `casos_gestionados_hoy`: `count(Project)` donde
  `primary_technician_user_id == user.id` y
  `completed_date == date.today()`.
- `tiempo_gestion_hoy_dias`: promedio de
  `(completed_date - created_at.date()).days` sobre esos mismos proyectos
  completados hoy; `None` si el conteo es 0.
- `logueado`: `last_seen_at` dentro de los últimos 5 minutos.
- `en_cola`: `is_available`.

Estas cuatro métricas se calculan con una query por técnico agregada en
Python (no una única mega-query con subqueries correlacionadas) — el
volumen esperado (decenas de técnicos, cientos de proyectos por
organización) hace innecesaria la complejidad de una sola consulta SQL
agregada; prioriza legibilidad sobre el ahorro marginal de roundtrips.

### `PATCH /field-ops/technicians/{user_id}/availability`

```python
class AvailabilityUpdate(BaseModel):
    is_available: bool
```

Verifica que `user_id` pertenezca a la organización actual y tenga el rol
`field_technician`; si no, 404. Actualiza `is_available` y comitea.

## Frontend

### `frontend/src/features/field-ops/TechnicianMonitorPage.tsx`

- `useQuery` con `refetchInterval: 30_000` (refresco automático cada 30s,
  sin websockets, para que la vista se sienta viva).
- `DataTable` con columnas: Técnico, Logueado (pill verde/rojo), En cola
  (toggle/botón), Casos asignados, Casos gestionados hoy, Tiempo de
  gestión hoy (`"—"` si `null`, si no `"X.X días"`).
- El toggle de "En cola" dispara la mutación `PATCH .../availability` e
  invalida la query al éxito.

### Navegación

Nuevo ítem en `NAV_ITEMS` de `frontend/src/app/DashboardLayout.tsx`:
`{ to: "/technician-monitor", label: "Monitor de técnicos", icon: "◉", permissions: ["dashboards.operations"] }`,
y la ruta correspondiente en `frontend/src/app/router.tsx` dentro del
`ProtectedRoute`.

## Testing

- Backend: test de `/field-ops/technician-monitor` que siembra un técnico
  con proyectos activos, uno completado hoy y uno completado ayer, y
  verifica que `casos_asignados`/`casos_gestionados_hoy`/
  `tiempo_gestion_hoy_dias` reflejen solo lo esperado (el de ayer no debe
  contar). Test del toggle de disponibilidad (cambia el valor, rechaza
  `user_id` de otra organización o que no sea `field_technician`).
- Test del throttle de heartbeat: dos requests seguidos del mismo usuario
  no deben generar dos `UPDATE` (se verifica indirectamente comprobando
  que `last_seen_at` no cambia si se fuerza a un valor "reciente" antes
  del segundo request).
- Frontend: verificación manual en navegador — cargar la vista, cambiar
  el toggle de un técnico, confirmar refresco automático.

## Riesgos / decisiones explícitas

- **Sin websockets**: ya decidido — "en vivo" simple vía heartbeat +
  polling de 30s es suficiente para el caso de uso, evita la
  infraestructura de conexiones persistentes.
- **`tiempo_gestion_hoy_dias` en días, no horas**: dado que `Project` solo
  tiene columnas `Date` (no `DateTime`) para `scheduled_date`/
  `completed_date`, la granularidad natural es días. Si en el futuro se
  necesita precisión de horas, requeriría agregar un timestamp de
  asignación/cierre — fuera de alcance de esta fase.
- **Cálculo en Python, no SQL agregado**: decisión explícita de
  simplicidad dado el volumen actual (mismo criterio ya aplicado en la
  Fase 1 para `/invoices`).
