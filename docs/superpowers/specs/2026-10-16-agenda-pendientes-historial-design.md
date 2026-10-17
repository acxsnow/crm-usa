# Agenda: «Pendientes» primero e «Historial» aparte

Fecha: 16 de octubre de 2026. Pedido por José en la revisión manual (rol Técnico).
Toca el paquete de Mateo (`field_ops`: agenda y su pantalla): se le avisa antes
de integrar.

## Problema

«Mi agenda» abría la semana en curso con todas las órdenes mezcladas: el 16 de
octubre, el técnico veía primero las del 12 y el 13, ya **cerradas**, y la suya
pendiente quedaba al final. Una orden de un día pasado que sigue **sin cerrar**
solo aparecía si el rango la incluía. Además el servidor pagina (100 por
página) pero la pantalla no tenía botones: pasado el tope, lo demás no se veía.

## Decisión (16 oct, con José)

Dos pestañas:

1. **Pendientes** (por defecto): solo órdenes sin cerrar (ni cerradas ni
   canceladas), con fecha de instalación hasta un «Hasta» (por defecto hoy + 14
   días), **sin límite hacia atrás**. Orden: la más vieja primero. La pantalla
   las agrupa en **Atrasadas** (fecha anterior a hoy, en rojo, con los días de
   atraso), **Hoy** y los días siguientes.
2. **Historial**: órdenes cerradas o canceladas en un rango Desde/Hasta (por
   defecto el último mes), de la más reciente a la más vieja, con botones de
   página de a 30.

Lo mismo para Administración, que usa la misma pantalla con el filtro de técnico.

## Diseño

- `GET /dispatch/agenda` suma `view` = `pending` | `history`:
  - `pending`: exige `date_to`; ignora `date_from`; estados distintos de
    `completed` y `cancelled`; `scheduled_date <= date_to`; orden ascendente.
  - `history`: exige `date_from` y `date_to` (máximo 366 días); estados
    `completed` y `cancelled`; orden descendente.
  - Sin `view`: como hoy (rango de hasta 62 días, todos los estados), para no
    romper a quien la use así.
  - La paginación pasa a la base (`paginate`), no en memoria.
  - Cada fila suma `days_late` (días calendario de atraso según el «hoy» de la
    organización; `null` si no está atrasada o ya se cerró).
  - El técnico solo ve lo suyo, como hoy.
- **Pantalla** (`AgendaPage.tsx`): pestañas en la dirección (`?vista=historial`),
  filtros que se conservan al volver de una orden, `usePaginatedQuery` y
  `PaginationControls`.

## Pruebas

- Pendientes: incluye una orden atrasada sin cerrar (con `days_late`), la de hoy
  y una futura dentro del «Hasta»; excluye cerradas, canceladas y las que pasan
  del «Hasta»; orden ascendente.
- Historial: solo cerradas o canceladas del rango, orden descendente, total en
  `X-Total-Count`.
- El técnico solo ve lo suyo en las dos vistas.
- Sin `view` sigue como antes (las pruebas actuales pasan sin cambios).
