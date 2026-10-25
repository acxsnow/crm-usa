# [AUTH-006] Escribir a mano la dirección de una pantalla sin permiso

## 1. Información general

- **ID:** AUTH-006
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Que esconder el menú no sea la única barrera: la pantalla y su API rechazan al rol equivocado.

## 3. Precondiciones

- Sesiones de vendedor y técnico.

## 4. Datos de prueba

- Rutas: /banking, /payables, /users, /roles, /audit-log, /warehouse, /invoices, /attendance, /payroll.

## 5. Procedimiento paso a paso

1. [ ] Como vendedor, escribir cada ruta de la lista en la barra del navegador.
2. [ ] Como técnico, repetir.
3. [ ] Con F12 abierto, mirar qué responde la API en cada intento.

## 6. Resultado esperado

- Cada ruta sin permiso lleva al Inicio (o muestra «sin acceso») sin mostrar datos.
- Las llamadas a la API de esas pantallas responden 403.

## 7. Resultado obtenido

- Qué pasó: Vendedor y técnico reciben 403 en las APIs de Banca, Proveedores, Equipo, Roles, Auditoría, saldos de Bodega, Facturas, Asistencia, Nómina y Conciliación (20 de 20).
- Diferencias con lo esperado: Ninguna en la API. Falta escribir las rutas en la barra del navegador y ver que no alcanza a mostrar datos.
- Comprobaciones por API (20 de 20):
  - ✔ vendedor → Banca (/bank-feeds/transactions) responde 403 — `403 · 36 ms`
  - ✔ vendedor → Proveedores (/payables/invoices) responde 403 — `403 · 32 ms`
  - ✔ vendedor → Equipo (/users) responde 403 — `403 · 31 ms`
  - ✔ vendedor → Roles (/roles) responde 403 — `403 · 22 ms`
  - ✔ vendedor → Auditoría (/audit-events) responde 403 — `403 · 23 ms`
  - ✔ vendedor → Bodega (saldos) (/warehouse/stock/summary) responde 403 — `403 · 21 ms`
  - ✔ vendedor → Facturas (/invoices) responde 403 — `403 · 24 ms`
  - ✔ vendedor → Asistencia (/attendance/dashboard) responde 403 — `403 · 23 ms`
  - ✔ vendedor → Nómina (/attendance/payroll/periods) responde 403 — `403 · 22 ms`
  - ✔ vendedor → Conciliación (/reconciliation/summary) responde 403 — `403 · 24 ms`
  - ✔ tecnico → Banca (/bank-feeds/transactions) responde 403 — `403 · 24 ms`
  - ✔ tecnico → Proveedores (/payables/invoices) responde 403 — `403 · 25 ms`
  - ✔ tecnico → Equipo (/users) responde 403 — `403 · 24 ms`
  - ✔ tecnico → Roles (/roles) responde 403 — `403 · 22 ms`
  - ✔ tecnico → Auditoría (/audit-events) responde 403 — `403 · 24 ms`
  - ✔ tecnico → Bodega (saldos) (/warehouse/stock/summary) responde 403 — `403 · 25 ms`
  - ✔ tecnico → Facturas (/invoices) responde 403 — `403 · 32 ms`
  - ✔ tecnico → Asistencia (/attendance/dashboard) responde 403 — `403 · 36 ms`
  - ✔ tecnico → Nómina (/attendance/payroll/periods) responde 403 — `403 · 39 ms`
  - ✔ tecnico → Conciliación (/reconciliation/summary) responde 403 — `403 · 40 ms`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.
- [ ] Ningún dato de la pantalla alcanza a verse antes de redirigir.

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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
