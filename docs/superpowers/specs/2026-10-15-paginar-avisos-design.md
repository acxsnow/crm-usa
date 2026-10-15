# Paginar «Mis avisos» y cerrar el hueco de la prueba guardiana

Fecha: 15 de octubre de 2026. Cadena A (José). Toca el paquete de Mateo
(`notifications/router.py`, `NotificationsPage.tsx`, `NotificationBell.tsx`,
`notifications/api.ts`): se le avisa antes de integrar.

## Problema

En la revisión manual del 15 de octubre, Notificaciones → Mis avisos mostraba
un bloque largo sin botones de página.

- `GET /notifications` devuelve `{"items": [...], "unread": N}` con `limit`
  hasta 100 y sin `offset`; la pantalla pide los 100 más recientes. Pasados 100,
  los más viejos desaparecen sin aviso y no hay forma de llegar a ellos. La
  alerta diaria crea un aviso por expediente demorado cada día, así que crece
  rápido (Administración ya tiene 69).
- La prueba guardiana `tests/test_pagination_everywhere.py` solo mira los GET
  que devuelven una **lista**; este devuelve un objeto con `items`, por eso no lo
  vio.
- Otros objetos con `items`: `GET /users` (ya paginado) y
  `GET /reconciliation/lines/{id}/candidates` (pagos del mismo monto en ±5 días:
  pocos por definición).

## Diseño

1. **API** (`GET /notifications`): pasa a la paginación común — lista de avisos,
   `Depends(pagination_params)`, total en `X-Total-Count`, del más nuevo al más
   viejo, con el filtro `unread`. El conteo de no leídos ya tiene su ruta
   (`GET /notifications/unread-count`), que es lo que usa la campana.
2. **Pantalla Mis avisos**: `usePaginatedQuery` + `PaginationControls`, 30 por
   página; «Solo sin leer» vuelve a la página 1. «Marcar todas como leídas» y
   abrir un aviso refrescan la página actual y el contador de la campana.
3. **Campana**: sigue mostrando los 8 más recientes (pide la página 1 con 8).
4. **Prueba guardiana**: también revisa los GET cuya respuesta es un objeto con
   una lista en `items` (por `response_model` o, si devuelven `dict`, por su
   código). Los candidatos de conciliación entran en `EXCEPTIONS` con el motivo.

## Fuera de alcance

Borrar o archivar avisos viejos.

## Pruebas

- `GET /notifications?limit=2&offset=0` y `offset=2`: páginas distintas, total
  en `X-Total-Count`, más nuevo primero; `unread=true` filtra y su total cambia;
  cada quien ve solo los suyos; `limit=501` → 422.
- La guardia falla si un GET con `items` no pagina (se verifica que hoy detecta
  `/notifications` antes del cambio).
- Navegador: Mis avisos con botones de página, filtro sin leer y campana.
