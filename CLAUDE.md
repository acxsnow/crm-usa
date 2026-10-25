# Delta HVAC · Contexto del proyecto

IMPORTANTE !!!!!!!!
Cada vez que se actualice el artefacto, se debe poner fecha, hora, y quien lo actualizo, tanto en el texto principal, como en el historico y con base en los commists, necesito que se actualicen lad funcionalidades que tenemos en el artefacto con esos datos que te digo mas el usuario que lo hizo.


Estándar del proyecto, basado en el estándar de auditoría integral creado por José Javier y Mateo Mazo. Cualquier ingeniero que desarrolle en este proyecto debe leer esta sección antes de empezar.

## Qué es el producto

CRM y plataforma de operación en campo para Delta HVAC, que inscribe hogares en programas de incentivos de climatización financiados por empresas de servicios o por el gobierno. La venta es puerta a puerta, sobre todo en parques de casas móviles de California, Arizona y Nevada. Programas iniciales: Eficiencia de Arizona (Desert Alliance Properties LLC) y TECH Clean California.

- **Roles** (decisión D1): `organization_admin` (Administrador), `salesperson` (Vendedor), `admin_staff` (Administración), `field_technician` (Técnico), `accounting` (Contabilidad), `management` (Gerencia).
- **Flujo principal:** todo cuelga de un expediente (`Case`) que nace cuando el vendedor toca la puerta y llega hasta el pago. Visita → formulario del programa, T&C y firma → revisión administrativa y sometimiento al programa → aprobación → permiso → instalación → inspección → cobro → pago → cierre.
- Referencias: `docs/Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`, `docs/requerimientos-formularios-programas-delta-hvac.md`, `docs/decisiones.md`.

## Estado y fechas

Etapa: desarrollo. Fecha de salida a producción: **Por definir**. Plan por módulos y fechas en `docs/cronograma-cadena-a.md` y `docs/cronograma-cadena-b.md`. El estado real y actualizado está en el artefacto del plan (enlace abajo). Consúltalo antes de asumir que algo está hecho o pendiente.

## Contexto técnico

- **Backend** (`backend/`): FastAPI + SQLAlchemy 2 async + PostgreSQL, Alembic, Redis y Celery. Un paquete por dominio en `app/modules/` (`auth`, `users`, `organizations`, `crm`, `cases`, `field_ops`, `billing`, `notifications`); piezas comunes en `app/shared/` (permisos, auditoría, errores, eventos). Guía: `backend/ARCHITECTURE.md`, `docs/MODULO-0-GUIA-TECNICA.md`, `docs/PERMISOS.md`, `docs/ERRORES.md`.
- **Frontend** (`frontend/`): React 18 + TypeScript + Vite, PWA. Menú por permiso en `src/config/navigation.ts`. Guía: `frontend/ARCHITECTURE.md`.
- **Levantar en local:** `cp backend/.env.example backend/.env`, `cp frontend/.env.example frontend/.env` y `docker compose up --build`; datos demo con `docker compose exec api python -m scripts.seed --demo-org`. Detalle en `README.md`.
- **Pruebas:** desde `backend/`, `.venv/bin/python -m pytest -q` (SQLite en memoria). Frontend: `npm run build` (incluye `tsc -b`). No hay pruebas automatizadas de frontend; sí hay integración continua en GitHub Actions.
- **Expediente:** 15 etapas y transiciones en `backend/app/modules/cases/stages.py`. Solo `cases/service.py` escribe `stage_code`, a través de `transition()`; cada cadena registra sus guardas (pueden ser `async`) y efectos con `register_guard()` / `register_effect()`. Contratos: `docs/contratos/case.md` (Cadena A) y `docs/contratos-cadena-b.md` (Cadena B).
- **Tramo de campo** (`approved` → `inspection_pending`): el expediente avanza por hechos registrados en `field_ops` (permiso, cierre de instalación, inspección) a través de `field_ops/case_flow.py`, `advance_case()`, nunca llamando a `transition()` desde otro sitio de `field_ops`. Las guardas de `field_ops/guards.py` impiden saltarse esos hechos por la ruta manual. Para «Listo para instalar» el permiso debe estar aprobado, salvo con `PERMIT_FILED_ALLOWS_INSTALL=true`, que también acepta el radicado (`permits.allows_install`); el cobro siempre exige el aprobado (`all_cleared`).
- **Tramo de cobro** (→ `billing_in_progress` → `paid`): lo mueven los cobros de programa (`billing/claims.py`, `_sync_case()`, con `advance_case()`), con guardas en `billing/case_hooks.py`; entrar a cobro exige el acta confirmada por Administración. El trabajo particular (cotizaciones en `/billing/quotes`) nunca mueve el expediente. Dinero siempre `Decimal` (`billing/money.py`) y numeración con `billing/numbering.py`.
- **Archivos:** `app/shared/files/` (`storage.py`, `watermark.py`) es común a todos los módulos.
- **Integraciones externas:** correo SMTP (Gmail en pruebas). SMS Masiv: Por verificar (módulo 7). Despliegue objetivo en Render (plan pago para producción). Almacenamiento de archivos: por definir según el cierre de salida a producción.

## Trabajo en paralelo

- **Cadena A** (José Javier Miranda, rama `cadenaA`): `users`, `auth`, `organizations`, `crm`, `programs`, `cases`, `documents`.
- **Cadena B** (Mateo Mazo, rama `CadenaB`): `field_ops`, `billing`, `notifications`.
- **Desde el 4 de octubre de 2026 Mateo cubre también la Cadena A** (José no puede trabajar por ahora; acordado con él). Módulo 1 en `app/modules/programs/` (spec `docs/superpowers/specs/2026-10-04-modulo-1-programas-design.md`). Cuando José vuelva, retoma desde el estado anotado en el artefacto.
- Nadie edita el paquete del otro sin avisar antes. Los archivos compartidos (`alembic/env.py`, `tests/conftest.py`, `api/v1/router.py`, `shared/permissions.py`, `app/router.tsx`, `DashboardLayout.tsx`) solo reciben líneas nuevas; no se reordenan ni se borran las del otro.
- Ciclo de integración:
  1. Cada uno sube a su rama.
  2. Quien integra trae la rama del otro, hace el merge, corre `pytest` y `npm run build` y, si todo pasa, lleva el resultado a `main` y lo sube. Quien integra segundo renumera su migración de Alembic encima de la del otro.
  3. Con `main` ya unificado, se actualiza el artefacto una sola vez con lo que cambió en las dos cadenas.
- No agregar líneas `Co-Authored-By` de Claude en commits ni PRs.

## Verificaciones específicas

- Aislamiento por organización en toda consulta, con el `organization_id` del token y nunca del cliente.
- Cada ruta con su permiso, y cada transición de etapa del expediente con el permiso que le corresponde (hallazgo SEG-07 abierto).
- El historial `case_stage_events` es la única fuente de los reportes de tiempos y rechazos: nada escribe `stage_code` fuera de `transition()`.
- Uso en celular en campo, con señal débil en los parques.
- Subida de archivos: tipo, tamaño, marca de agua con GPS y fecha.
- Protección de datos personales: la autorización de tratamiento es obligatoria en los cuatro puntos donde se capturan datos del cliente (alta de cliente, edición de cliente, T&C del expediente y firma pública del cliente). La constancia queda en `data_consents` (`app/modules/crm/privacy.py`, migración `0038`) con versión del texto, fecha, IP y GPS; el aviso es público en `GET /api/v1/privacy/consent-notice`. Norma aplicable (definida el 24 de octubre de 2026): CCPA/CPRA de California, SB 220 y SB 370 de Nevada y A.R.S. § 18-552 de Arizona.
- Turnos, asistencia y mapa (respuestas confirmadas por Don Aldo): tiempo de llegada y tiempo del trabajo; seguimiento GPS por eventos con punto horario si se implementa el seguimiento periódico; retención de coordenadas por 90 días; el mapa lo ven Administrador y supervisor/Administración; la malla la ven Administrador y supervisor/Administración con tolerancia de 10 minutos; cuando pagan por día o por hora el almuerzo va incluido, y cuando pagan por trabajo no; las horas extras se declaran en horas y el jefe define el valor; lo de «Mateo y José» queda tal como ya está definido en el código y en las decisiones vigentes.

## Plan y auditorías (artefacto compartido)

- Enlace: https://claude.ai/artifact/Vi4rriEgvkZ3AeJ4dBR8NZ (enlace actualizado el 24 de octubre de 2026)
- Dueño del artefacto (cuenta que lo publicó): José Javier Miranda. Mateo Mazo tiene permiso de edición.
- Estándar de auditoría: `docs/auditoria/auditoria-integral.md`
- Es el documento oficial de estado del proyecto. Lo consultan el equipo y la gerencia de desarrollo.
- Subido al artefacto el 24 de octubre de 2026, 23:50 (hora de Colombia), por Mateo Mazo (versión 35, sobre `main` en `7de16e4`): consentimiento y autorización de datos, respuestas de Don Aldo de turnos y mapa, SEG-09 como incidente histórico mitigado con rotación pendiente, prueba en celular real sobre Render, producción en Render en vez de AWS, auditoría de código por antes/después y abierto/desactualizado/cerrado (COD-02 a COD-07 cerrados) y Housecall Pro con la premisa de reemplazar QuickBooks (price book cubierto). Nuevos en esa versión: SEG-10 (organización de demostración en el arranque de Render), COD-11 (linters parciales) y TST-05 (pruebas que dependían de la hora local).

## Reglas

- El artefacto se actualiza después de integrar a `main` (paso 3 del ciclo), lo haga José o Mateo. Esta regla reemplaza la de "solo el dueño actualiza" del estándar, por acuerdo del 26 de septiembre de 2026.
- Antes de actualizarlo, léelo de nuevo: el otro pudo haber publicado una versión más reciente. Construye la actualización sobre esa versión y nunca crees un artefacto nuevo.
- En cada actualización: cambia solo lo afectado, marca los hallazgos cerrados con su fecha, recalcula calificaciones, avance y veredicto si cambian, actualiza la fecha del encabezado y agrega una línea al historial indicando quién la hizo.
- Si una sesión deja decisiones confirmadas por el cliente o por Don Aldo y todavía no están reflejadas en el artefacto, anótalas en `CLAUDE.md` y súbelas en la siguiente actualización del artefacto después de integrar a `main`.
- Si una sesión cambia el alcance comparativo contra Housecall Pro o QuickBooks, actualizar también el apartado `Housecall Pro: qué ya cubrimos y qué no` del artefacto; no dejar allí textos viejos que asuman exportación o integración con QuickBooks si la meta vigente es reemplazarlo dentro de la plataforma.
- Para identificar rápido qué falta de verdad en el artefacto: marcar cada pendiente como `faltante real`, `parcial en código` o `ya cubierto y pendiente de actualizar el artefacto`. Si el código, las pruebas y el QA ya existen en el repo, no dejarlo como faltante; moverlo a cubierto en la siguiente actualización y citar el módulo o archivo que lo demuestra.
- En la sección `Auditoría de código y deuda técnica`, además de la severidad y el tamaño, agrupar por `antes de salir` y `después de salir`, y separar explícitamente lo `abierto real` de lo `desactualizado`. Si una deuda ya cambió de estado por código nuevo, el artefacto debe decir qué archivo o prueba la cerró.
- No repitas las auditorías completas salvo que se pida o antes de una salida a producción.
- Si terminas una tarea que afecta el plan y todavía no está en `main`, deja un resumen de qué cambió y qué hallazgos cierra (por ID) para incluirlo en la próxima actualización.
- Al escribir código nuevo, no introduzcas problemas del tipo de los hallazgos abiertos del plan (por ejemplo, endpoints sin control por rol, secretos en el código o lógica sin pruebas).
- Al final de cada sesión, si hubo cambios que afectan el plan y no se han reflejado, recuérdalo antes de cerrar.
