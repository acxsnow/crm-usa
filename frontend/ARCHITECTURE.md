# Arquitectura — Frontend (React 18 + TypeScript + Vite)

> 🔒 **Documento canónico — CONGELADO.** Junto con `backend/ARCHITECTURE.md`
> y la cadena de verdad de `.claude/CLAUDE.md`, es **fuente de verdad**. No se
> modifica automáticamente; solo cambia con **aprobación explícita** del
> responsable (José Javier).

Frontend del proyecto **crm-usa** (Delta HVAC). Consume **exclusivamente** la
API REST del backend FastAPI (`/api/v1`). Arquitectura **feature-based**: el
routing y el shell (`src/app/`) se separan de la lógica de dominio
(`src/features/`). Es una **PWA** (`vite-plugin-pwa`) — el vendedor y el
técnico la usan desde el celular.

## Stack de datos (decisión fija)

- **TanStack Query + Axios**. Nunca `fetch`.
- Instancia **única** de Axios en `@/lib/apiClient` (baseURL, JWT en request,
  refresh automático en 401, redirección a `/login` si el refresh falla).
  Los endpoints `/auth/login|refresh|logout` están **excluidos** del refresh
  automático: su 401 es "credenciales inválidas", no "token vencido".
- Todo el acceso a datos es **client-side**. No hay SSR.
- El estado de servidor vive en TanStack Query. **No** se duplica en
  `useState`/context salvo para formularios en edición.

---

## Estructura de carpetas (estado real)

```
frontend/
├── index.html · vite.config.ts · tsconfig.json     # alias "@/*" → "src/*"
├── .env.example                                    # VITE_API_BASE_URL
└── src/
    ├── main.tsx · App.tsx                          # monta <AppProviders> + <RouterProvider>
    ├── index.css                                   # identidad visual (tokens, layout, .data-table, .auth-*)
    ├── app/                                        # SOLO shell y routing
    │   ├── router.tsx                              #   createBrowserRouter: rutas públicas + "/" protegido
    │   ├── providers.tsx                           #   QueryClientProvider + AuthProvider
    │   ├── DashboardLayout.tsx                     #   sidebar + <Outlet/>
    │   └── DashboardHome.tsx
    ├── components/                                 # presentacional reutilizable (sin dominio)
    │   ├── DataTable.tsx · FilterBar.tsx · PaginationControls.tsx
    │   └── ProtectedRoute.tsx                      #   redirige a /login si no hay sesión
    ├── features/                                   # un slice por dominio (espeja app/modules/ del backend)
    │   ├── auth/         AuthContext.tsx, LoginPage, ForgotPassword, ResetPassword, AcceptInvitation
    │   ├── crm/          api.ts, LeadsPage, CustomersPage, CustomerDetailPage, OpportunitiesPage,
    │   │                 ApplicationPage, ApplicationsAdminPage
    │   ├── field-ops/    api.ts, ProjectsPage, ProjectDetailPage, TechnicianMonitorPage,
    │   │                 CustomerSignaturePage, SignaturePad
    │   ├── billing/      api.ts, InvoicesPage
    │   ├── users/        api.ts, UsersPage
    │   └── audit/        api.ts, AuditLogPage
    ├── lib/                                        # transversal, sin UI
    │   ├── apiClient.ts                            #   Axios único + interceptores + tokens (localStorage)
    │   ├── pagination.ts                           #   fetchPage<T>: ?limit=&offset= + X-Total-Count → Page<T>
    │   ├── usePaginatedQuery.ts                    #   gancho común de listados paginados (página, total, controles)
    │   └── useTableFilters.ts                      #   filtros y página en la URL (?status=&q=&page=)
    └── types/                                      # DTOs que espejan los schemas Pydantic del backend
        auth.ts · crm.ts · fieldOps.ts · billing.ts · users.ts · audit.ts
```

---

## Flujo de datos

```
Página / componente (features/<f>/XxxPage.tsx)
  → useQuery / useMutation                       (hoy inline en la página; ver convención abajo)
    → función de servicio                         features/<f>/api.ts
      → apiClient (Axios centralizado)            @/lib/apiClient.ts
        → REST /api/v1/…                          (FastAPI)
        ← respuesta tipada                        @/types/<f>.ts
```

- **Interceptor de request**: `Authorization: Bearer <access_token>`.
- **Interceptor de response**: en 401 (fuera de `/auth/*`) intenta un refresh
  único compartido y reintenta la petición; si falla, limpia tokens y va a
  `/login`.
- **Listados**: todo listado del backend viene paginado (máximo 100 por
  defecto). Una tabla o lista **nueva** usa el gancho común
  `lib/usePaginatedQuery.ts` + `<PaginationControls {...lista.controls} />`:
  maneja la página, pide solo esa y vuelve a la 1 al cambiar filtros. Las
  pantallas anteriores usan `fetchPage` + `useTableFilters` + `FilterBar` +
  `DataTable` + `PaginationControls` y siguen igual. Los filtros se resuelven
  en el **backend** (SQL), no en memoria.
- **Mutaciones**: `onSuccess` → `queryClient.invalidateQueries({ queryKey: [...] })`.
  Nunca mutar caché a mano salvo optimistic updates justificados.

---

## Responsabilidades por capa

| Capa | Responsabilidad | NO hace |
|------|-----------------|---------|
| `app/` | Routing, layout, providers | Lógica de datos ni de negocio |
| `features/<f>/api.ts` | Funciones `async` que llaman a `apiClient` y devuelven DTOs tipados | Estado, UI |
| `features/<f>/*Page.tsx` | Composición de UI + hooks de Query + formularios | Llamar a `apiClient` directo |
| `components/` | Presentacional puro, reutilizable, sin conocer el dominio | Fetch, rutas |
| `lib/` | Infra transversal (HTTP, paginación, filtros en URL) | UI |
| `types/` | Contratos que reflejan los `XxxResponse` del backend | Lógica |

Regla de oro: **una página no habla con Axios**; habla con `api.ts` de su
feature. **Un componente de `components/` no sabe qué es un Lead**.

---

## Convención para features nuevas (Cadena A en adelante)

Las features existentes meten `useQuery` en la página. Para lo nuevo se
adopta el patrón de `ventas_pap`, que escala mejor y se testea aparte:

```
features/<feature>/
├── api.ts              # servicio HTTP (obligatorio)
├── queries.ts          # hooks: useXxxList(), useXxx(id), useCreateXxx() — encapsulan queryKey e invalidaciones
├── components/         # piezas propias de la feature (formularios, tarjetas, modales)
├── XxxPage.tsx         # páginas (una por ruta)
└── index.ts            # (opcional) superficie pública
```

- Los **tipos** siguen en `src/types/<feature>.ts` (contrato compartido). Si un
  tipo es solo interno de la feature, va en `features/<f>/types.ts`.
- Las `queryKey` se centralizan en `queries.ts` (`const keys = { all: ["programs"], detail: (id) => [...] }`)
  para que las invalidaciones no dependan de strings repetidos.
- **Formularios**: `react-hook-form` + `zod` (ya son dependencias; hoy las páginas
  usan `useState` a mano — lo nuevo no).
- **Formulario dinámico** (módulo 2): el renderer de campos por `field_type` es
  un componente de `features/applications/components/`, no de `components/`,
  hasta que un segundo consumidor demuestre que es genérico.

---

## Convenciones generales

- **Imports** con alias `@/*` (`@/lib/apiClient`, `@/types/crm`). Relativos
  solo dentro de la misma feature (`./api`).
- **Naming**: `camelCase` funciones/variables, `PascalCase` componentes/tipos,
  carpetas de feature en `kebab-case`, archivos de página `XxxPage.tsx`.
- **Textos de UI en español** (decisión cerrada con el cliente). El código,
  identificadores y commits en inglés.
- **Mobile-first** en todo lo que usan vendedor y técnico: patrón de tarjetas
  colapsables en celular, tabla en escritorio. Probar a 375px de ancho.
- **Estilos**: `index.css` con clases semánticas (`.data-table`, `.auth-card`,
  `.form-error`). Sin CSS-in-JS ni Tailwind. Un componente nuevo agrega sus
  clases al final de `index.css` bajo un comentario con su nombre.
- **Estados obligatorios** en toda pantalla que carga datos: cargando, vacío,
  error. No dejar un `<table>` en blanco.
- **Rutas**: se registran en `app/router.tsx`; las protegidas cuelgan de `"/"`
  bajo `<ProtectedRoute>`. Permisos por pantalla con `useAuth().hasPermission("x.y")`.
- **Nunca** `window.location` para navegar dentro de la app (solo lo usa el
  interceptor para expulsar sesión); usar `useNavigate`/`<Link>`.

---

## Deuda conocida (no arreglar "de paso"; cada punto es una tarea)

- `npm run lint` está declarado pero **no hay ESLint instalado ni configurado**.
- No hay runner de tests de frontend (sin Vitest / Testing Library). La
  verificación hoy es `tsc -b` + `vite build` + prueba en navegador.
- No hay normalización de errores HTTP (`NormalizedApiError` de ventas_pap);
  cada página interpreta `error.response` a su manera.
- Pantallas de auth (`LoginPage`, etc.) siguen en inglés.
- `index.css` tiene 1.300+ líneas en un solo archivo.

---

## Puesta en marcha y verificación

```bash
# El frontend corre en Docker (docker compose up). Vite usa polling para ver
# cambios desde el volumen de Windows (vite.config.ts → server.watch.usePolling).
docker compose exec frontend sh -c "npx tsc -b && npx vite build"   # debe quedar limpio
# http://localhost:5173  ·  API: http://localhost:8000/api/docs
```
