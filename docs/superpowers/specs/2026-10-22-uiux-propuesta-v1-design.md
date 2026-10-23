# Propuesta UI/UX V1 — Diseño de la migración

**Fecha:** 22 de octubre de 2026 · **Pidió:** José Javier · **Fuente:** `docs/PAP_Ventas_Propuesta_UIUX_V1.md` y `docs/Tablero integral de interfaces PAP Ventas.png`

Es solo la capa visual. No cambian APIs, rutas, campos, validaciones, permisos ni lógica.

## 1. Lo que ya existe (inventario del 22 oct)

- **Stack:** React 18, TypeScript, Vite y React Query. Sin librería de componentes ni de íconos: los íconos son caracteres Unicode del menú (`config/navigation.ts`) y SVG propios (`features/field-ops/components/icons.tsx`). Sin librería de gráficas: las del costo del trabajo son SVG propios.
- **Estilos:** un solo `index.css` de 3.561 líneas, más 7 CSS de módulo. Usan variables (`--red`, `--ink`, `--line`, `--canvas`…) en unas 400 reglas, más 129 colores fijos en `index.css`. Algunas variables (`--ok`, `--warn`, `--card-soft`, `--line-input`) están definidas a mitad del archivo.
- **Identidad actual:** «industrial». Títulos en Archivo Expanded y en mayúsculas, cifras y etiquetas en IBM Plex Mono, tarjetas de KPI negras, fondo arena (#F3EFE9) y radios de 3 a 10 px. La propuesta pide lo contrario en tipografía (sin condensadas) y en fondo (claro y frío).
- **Layout (`app/DashboardLayout.tsx`):** barra lateral oscura de 250 px y barra superior de 68 px.
  - Por debajo de 700 px la barra lateral se vuelve un menú que se abre con ☰, con fondo oscurecido y cierre con Escape.
  - El buscador de la barra superior **no hace nada**: es un input sin acción.
  - La tarjeta «¿Necesitas ayuda? Visita el centro de soporte» **no lleva a ningún lado**.
- **Patrones comunes que ya existen:**
  - `DataTable` ya se vuelve tarjetas por debajo de 640 px (`.is-cards`, con título y acciones).
  - `FilterBar` (plegable), `PaginationControls` con `usePaginatedQuery`, `Toaster` y `toast`, y `PasswordInput`.
  - Clases muy usadas: `acta-btn` (232 usos), `acta-empty` (113), `form-error` (74), `billing-chip`, `status-pill` y `acta-chip`.
- **Diálogos nativos:** quedan 14 `window.confirm`/`window.prompt`, la mayoría en finanzas y campañas.
- **Breakpoints:** hoy hay cortes sueltos en 640, 700, 760, 900 y 980 px.

## 2. Lo que la propuesta trae y no existe en la app

El tablero de referencia muestra pantallas que **no son de este producto**: «Oportunidades» (kanban), «Calendario» y «Perfil/Configuración» propio con tema, ayuda y cambio de contraseña. **No se construyen**, porque serían funcionalidad inventada. Se toma del tablero solo el lenguaje visual.

Hay otros tres puntos que pide la propuesta y que la app no tiene:

| Punto | Decisión |
|---|---|
| Búsqueda global en la barra superior | Hoy es un input sin acción. Se conserva igual, sin prometer resultados. Si se quiere de verdad, es una funcionalidad aparte (pendiente de decisión). |
| Marca «PAP Ventas» | La app y los correos dicen «PAP.CRM». No se cambia el nombre sin decisión del negocio. |
| SSO en el ingreso | No existe; no se muestra. |

## 3. Mapa de componentes

Los componentes nuevos van en `src/components/ui/`. Los existentes se reestilizan sin cambiar su API.

| Patrón de la propuesta | Componente | Estado |
|---|---|---|
| Tokens | `:root` en `index.css` (paleta, radios, sombras, espaciado y tipografía) | **Fase 1** |
| Sidebar y menú móvil | `DashboardLayout` (`.app-sidebar`, `.menu-toggle`) | Reestilizar en **fase 1**; menú móvil por debajo de 1024 px |
| Navegación inferior | `MobileTabBar` (nuevo, dentro del layout) | **Fase 1**: máximo 4 destinos según permisos, más «Más», que abre el menú |
| Topbar | `DashboardLayout` (`.app-topbar`) | **Fase 1** |
| PageHeader | `ui/PageHeader` | Se crea en la **fase 1**; se adopta por módulo desde la fase 2 |
| KpiCard | `ui/KpiCard` | **Fase 1**, adoptado en Inicio |
| StatusBadge | `ui/StatusBadge` y las clases existentes `status-pill`, `billing-chip`, `acta-chip` con semántica uniforme | **Fase 1** (CSS) |
| EmptyState / Skeleton | `ui/EmptyState`, `ui/Skeleton` | **Fase 1**; `DataTable` usa el skeleton al cargar |
| DataTable / MobileRecordCard | `DataTable` (mismo componente, tarjeta mejorada por CSS) | **Fase 1** |
| FilterBar | `FilterBar` (ya plegable) | Restyle en la fase 1; panel móvil en la fase 2 |
| ConfirmDialog | `ui/ConfirmDialog` y el hook `useConfirm` | Se crea en la **fase 1**; reemplaza los 14 diálogos nativos módulo por módulo |
| DetailView / FormSection | Acta (`InstallationRecord`) y formularios existentes | Fases 2 y 3 |

## 4. Fases

1. **Base (esta entrega):** tokens; tipografía Inter sin mayúsculas forzadas; sidebar, menú móvil, topbar, navegación inferior y área de contenido de 1440 px; restyle global de botones, chips, paneles, tablas y tarjetas; componentes base; Inicio con `KpiCard`.
2. Ingreso, Inicio, Clientes, Mi día, Campañas, Expedientes y Por revisar.
3. Proyectos (acta), Monitor, Agenda, Checklists, Permisos e inspecciones.
4. Bodega completa.
5. Finanzas, Conciliación y rentabilidad, Reportes.
6. Configuración de programas, Usuarios, Roles, Auditoría, Notificaciones y QA final a 360, 390, 430, 768, 1024 y 1440 px.

Cada fase se cierra con build, revisión de hooks, capturas a 1440 y 390 px y validación visual de José antes de seguir.

## 5. Reglas de la fase 1

- Breakpoints: móvil hasta 767 px, tablet de 768 a 1023 px y escritorio desde 1024 px. El menú pasa a cajón por debajo de 1024 px; la navegación inferior solo aparece por debajo de 768 px.
- La navegación inferior sale de `buildNavForUser`, así que respeta los permisos y no duplica rutas: muestra los primeros destinos permitidos de Inicio, Clientes, Expedientes, Agenda, Proyectos y Por revisar (máximo 4), más «Más».
- Los cambios en `DashboardLayout.tsx` y en `index.css` (archivos compartidos) se avisan a Mateo.
- Sin dependencias nuevas.
