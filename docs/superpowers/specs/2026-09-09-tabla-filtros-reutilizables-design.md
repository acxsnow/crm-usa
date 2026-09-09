# Componente de tabla y filtros reutilizable (Fase 1)

Fecha: 2026-09-09
Estado: aprobado por el usuario, pendiente de plan de implementación.

## Contexto

Este es el primer sub-proyecto de una iniciativa en dos partes:

1. **Este spec**: base reutilizable de tabla + filtros, migrada a las páginas
   de listado más usadas.
2. **Fase 2 (spec aparte, después)**: vista de control estilo GTR para
   técnicos de campo (logueado / en cola / casos asignados / gestionados /
   tiempo de gestión), construida sobre esta base.

Hoy ninguna tabla del CRM tiene filtros reales — cada página
(`LeadsPage`, `CustomersPage`, `OpportunitiesPage`, `ProjectsPage`,
`InvoicesPage`, `UsersPage`, `ApplicationsAdminPage`, `AuditLogPage`)
dibuja su propio `<table className="data-table">` a mano, sin controles de
búsqueda (salvo un ícono de lupa decorativo en `CustomersPage`). La
paginación de servidor (`limit`/`offset` + header `X-Total-Count`, ver
`backend/app/shared/pagination.py` y `frontend/src/lib/pagination.ts`) ya
existe y funciona; algunos endpoints (`/leads`, `/applications`,
`/invoices`) ya aceptan un filtro `status` que el frontend nunca expone.

Las 3 imágenes de referencia enviadas por el usuario son de un sistema
externo (no nuestro) y se usan **solo como referencia de estructura**
(panel de filtros colapsable + Buscar/Limpiar arriba, tabla con cabecera
oscura debajo) — no se copia su marca, colores ni contenido.

## Objetivo

- Un componente `FilterBar` y un componente `DataTable` reutilizables,
  con un look consistente en toda la app (respetando la identidad visual
  ya definida en `index.css`).
- Filtros que de verdad funcionan: se resuelven en el backend (SQL), no
  sobre los 20 registros ya cargados en pantalla.
- Migrar las páginas de mayor uso a este estándar: **Leads, Proyectos,
  Clientes, Aplicaciones**.

Fuera de alcance para esta fase: `UsersPage` y `AuditLogPage` (bajo
tráfico, se migran en una pasada posterior reusando los mismos
componentes, sin diseño adicional), y todo lo relativo a la vista GTR de
técnicos.

## Componentes frontend

### `FilterBar` (`frontend/src/components/FilterBar.tsx`)

Panel colapsable (abierto por defecto) que recibe una lista de
definiciones de campo y renderiza los inputs correspondientes:

```ts
type FilterFieldDef =
  | { key: string; label: string; type: "text"; placeholder?: string }
  | { key: string; label: string; type: "select"; options: { value: string; label: string }[] }
  | { key: string; label: string; type: "dateRange" };

interface FilterBarProps {
  fields: FilterFieldDef[];
  values: Record<string, string>;      // filtros ya aplicados
  onApply: (values: Record<string, string>) => void;
  onClear: () => void;
}
```

Mantiene un estado de **borrador** interno (lo que el usuario está
tecleando/seleccionando) separado de `values` (lo aplicado). Los inputs
no disparan búsqueda en cada tecla — solo el botón **Buscar** (o Enter en
un campo de texto) llama a `onApply`, y **Limpiar** resetea borrador y
llama a `onClear`. Esto replica el patrón de la referencia y evita
requests de más.

### `DataTable` (`frontend/src/components/DataTable.tsx`)

```ts
interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;   // por defecto: String(row[key])
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  isLoading: boolean;
  emptyMessage?: string;
  getRowKey: (row: T) => string;
}
```

Reemplaza los `<table className="data-table">` hechos a mano. Estados
`isLoading` y vacío consistentes (mismo mensaje/estilo en todas las
páginas). No incluye paginación — `PaginationControls` (ya existente) se
sigue usando por fuera, sin cambios.

### Hook `useTableFilters` (`frontend/src/lib/useTableFilters.ts`)

Sincroniza filtros aplicados + página actual con la query string de la
URL (`?status=active&q=maria&page=2`), para que el estado de una
búsqueda sea recargable/compartible. Expone `{ filters, page, setFilters,
setPage, extraParams }`, donde `extraParams` es directamente lo que
`fetchPage` espera como cuarto argumento — no se toca `fetchPage` ni
`paginate()` del backend, ambos ya soportan parámetros extra.

## Cambios de backend

Mismo patrón que ya usa `list_leads` (query param opcional + `stmt.where`
condicional), extendido por endpoint:

| Endpoint | Filtros nuevos a agregar |
|---|---|
| `GET /leads` | `q` (texto libre sobre `full_name`, `phone`, `email` con `ILIKE`) — `status` ya existe, solo falta exponerlo en el UI |
| `GET /projects` | `status`, `q` (texto sobre `title`/dirección), `technician_id` (`primary_technician_user_id`) |
| `GET /customers` | `q` (texto sobre `legal_name`, `email`, `main_phone`), `status` |
| `GET /applications` | `q` (texto sobre nombre del lead/cliente asociado), `status` ya existe |

`InvoicesPage` no se migra en esta fase (su filtrado ya es en Python
sobre estado calculado — se deja igual). `list_invoices` no cambia.

Todos los filtros de texto usan `ILIKE '%valor%'` sobre las columnas
indicadas, combinados con `AND` junto a los demás filtros activos y el
`organization_id` (scoping existente, sin tocar). Ninguno de estos
campos requiere índices nuevos dado el volumen actual (cientos, no
millones, de filas por organización).

## Estilo visual

Se mantiene la paleta y tipografía ya definidas en `frontend/src/index.css`
(rojo/negro industrial) — de la referencia externa se toma solo la
**estructura**: panel de filtros arriba (colapsable, título "FILTROS"),
tabla con cabecera de fondo oscuro debajo, botón primario "Buscar" +
botón secundario "Limpiar". Se agregan las clases CSS necesarias
(`.filter-bar`, `.filter-bar-fields`, `.data-table thead` con fondo
oscuro) a `index.css`, siguiendo las variables ya existentes
(`--ink`, `--red`, `--sidebar`, etc.), sin introducir una paleta nueva.

## Migración de páginas (fase 1)

Para cada una de `LeadsPage`, `ProjectsPage`, `CustomersPage`,
`ApplicationsAdminPage`:

1. Backend: agregar los `Query()` de la tabla de arriba a su endpoint de
   listado.
2. Frontend: reemplazar el `<table>` manual por `DataTable`, agregar
   `FilterBar` con los campos correspondientes, y cablear ambos a
   `useTableFilters` + `fetchPage`.

El formulario de creación/alta que ya existe en cada página (crear lead,
crear cliente, etc.) no cambia — solo se toca la tabla de listado y se
agrega el panel de filtros encima.

## Testing

- Backend: un test por endpoint modificado (pytest, siguiendo los tests
  existentes en `backend/tests`) que verifique que cada filtro nuevo
  reduce correctamente el resultado.
- Frontend: verificación manual en navegador por página migrada —
  aplicar cada filtro, limpiar, combinar filtro + paginación.
- No se agregan tests de componente para `FilterBar`/`DataTable` en esta
  fase (son de presentación; su corrección se valida a través de las
  páginas que los usan).

## Riesgos / decisiones explícitas

- **Filtrado en SQL, no en frontend**: ya decidido con el usuario —
  necesario porque hay más de una página de datos en la mayoría de estas
  tablas.
- **`InvoicesPage` fuera de alcance**: su status es calculado en Python
  (no columna), migrarlo requeriría cambiar cómo se pagina — se deja para
  una fase posterior si se pide explícitamente.
- **`UsersPage`/`AuditLogPage` fuera de alcance**: bajo tráfico, se
  migran después reusando los mismos componentes sin rediseño.
