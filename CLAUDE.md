# Delta HVAC · Contexto del proyecto

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
- **Pruebas:** desde `backend/`, `.venv/bin/python -m pytest -q` (SQLite en memoria). Frontend: `npm run build` (incluye `tsc -b`). No hay pruebas de frontend ni integración continua.
- **Expediente:** 15 etapas y transiciones en `backend/app/modules/cases/stages.py`. Solo `cases/service.py` escribe `stage_code`, a través de `transition()`; cada cadena registra sus guardas (pueden ser `async`) y efectos con `register_guard()` / `register_effect()`. Contratos: `docs/contratos/case.md` (Cadena A) y `docs/contratos-cadena-b.md` (Cadena B).
- **Tramo de campo** (`approved` → `inspection_pending`): el expediente avanza por hechos registrados en `field_ops` (permiso, cierre de instalación, inspección) a través de `field_ops/case_flow.py`, `advance_case()`, nunca llamando a `transition()` desde otro sitio de `field_ops`. Las guardas de `field_ops/guards.py` impiden saltarse esos hechos por la ruta manual.
- **Archivos:** `app/shared/files/` (`storage.py`, `watermark.py`) es común a todos los módulos.
- **Integraciones externas:** correo SMTP (Gmail en pruebas). SMS Masiv: Por verificar (módulo 7). Almacenamiento de archivos en disco local; paso a la nube Por verificar.

## Trabajo en paralelo

- **Cadena A** (José Javier Miranda, rama `cadenaA`): `users`, `auth`, `organizations`, `crm`, `programs`, `cases`, `documents`.
- **Cadena B** (Mateo Mazo, rama `CadenaB`): `field_ops`, `billing`, `notifications`.
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

## Plan y auditorías (artefacto compartido)

- Enlace: https://claude.ai/code/artifact/e87bc170-086f-4777-ad5e-2ee15766cdfe
- Dueño del artefacto (cuenta que lo publicó): José Javier Miranda. Mateo Mazo tiene permiso de edición.
- Estándar de auditoría: `docs/auditoria/auditoria-integral.md`
- Es el documento oficial de estado del proyecto. Lo consultan el equipo y la gerencia de desarrollo.

## Reglas

- El artefacto se actualiza después de integrar a `main` (paso 3 del ciclo), lo haga José o Mateo. Esta regla reemplaza la de "solo el dueño actualiza" del estándar, por acuerdo del 26 de septiembre de 2026.
- Antes de actualizarlo, léelo de nuevo: el otro pudo haber publicado una versión más reciente. Construye la actualización sobre esa versión y nunca crees un artefacto nuevo.
- En cada actualización: cambia solo lo afectado, marca los hallazgos cerrados con su fecha, recalcula calificaciones, avance y veredicto si cambian, actualiza la fecha del encabezado y agrega una línea al historial indicando quién la hizo.
- No repitas las auditorías completas salvo que se pida o antes de una salida a producción.
- Si terminas una tarea que afecta el plan y todavía no está en `main`, deja un resumen de qué cambió y qué hallazgos cierra (por ID) para incluirlo en la próxima actualización.
- Al escribir código nuevo, no introduzcas problemas del tipo de los hallazgos abiertos del plan (por ejemplo, endpoints sin control por rol, secretos en el código o lógica sin pruebas).
- Al final de cada sesión, si hubo cambios que afectan el plan y no se han reflejado, recuérdalo antes de cerrar.
