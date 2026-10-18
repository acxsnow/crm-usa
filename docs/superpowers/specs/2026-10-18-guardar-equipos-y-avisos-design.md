# «Guardar equipos instalados» y avisos de guardado en toda la app — Diseño

**Fecha:** 18 de octubre de 2026 · **Pidió:** José Javier (recorrido manual como técnico)

## Problema

1. En el acta de instalación, el paso «Equipos instalados» queda «Completado» apenas se agrega el primer equipo. El técnico no tiene cómo decir «ya terminé de registrar los equipos», y si la casa lleva tres, el paso se ve terminado con uno.
2. Al guardar algo en la app casi nunca hay confirmación visible. Solo 7 pantallas muestran un «Guardado.» dentro del formulario, cada una a su manera. Hay 121 acciones que guardan datos.

## Lo que ya existe

- Mensajes sueltos de éxito: `form-success` y `setMsg("Guardado.")` en Roles, Usuario, Plantillas de checklist, Ajustes de finanzas y Notificaciones. No hay un sistema común de avisos (toasts) ni librería para eso.
- Los errores ya se muestran en cada formulario (`form-error`). No cambian.
- El cierre de la instalación ya exige al menos un equipo (`installation_gaps`).

## Diseño

### 1. Guardar la lista de equipos

- **Datos:** `projects.equipment_confirmed_at` y `projects.equipment_confirmed_by_user_id` (migración 0026). Al migrar, los proyectos ya cerrados que tienen equipos quedan confirmados, para no reabrir nada viejo.
- **API:** `POST /projects/{id}/equipment/confirm` con el permiso `equipment.manage`, que ya es el de agregar y quitar equipos. Exige al menos un equipo y que la instalación no esté cerrada. Deja auditoría (`equipment.confirmed`). La respuesta del proyecto lleva `equipment_confirmed_at`.
- **Regla:** agregar o quitar un equipo deshace la confirmación, porque la lista cambió y hay que volver a guardarla.
- **Cierre:** `installation_gaps` pide «Guardar la lista de equipos instalados» cuando hay equipos pero no están confirmados.
- **Pantalla:** debajo de la tabla aparece el botón «Guardar equipos instalados», activo solo si hay equipos y la lista no está guardada. Mientras no se guarde, el paso queda «En curso»; al guardar pasa a «Completado». Si luego se agrega o se quita un equipo, vuelve a «En curso».
- La regla del frontend (`deriveStates`, `closeRequirements`) usa la misma condición que el backend.

### 2. Avisos de guardado en toda la app

- Un solo componente de avisos (`Toaster`) en `AppProviders` y una función `toast()` en `src/lib/toast.ts`.
- Se engancha una vez en el `MutationCache` de React Query: **toda acción que guarda con éxito muestra un aviso**, por defecto «Cambios guardados.», sin tocar las 121 pantallas.
- Cada acción puede dar su propio texto con `meta: { successMessage: "…" }`, o no mostrar nada con `meta: { silent: true }`. Esto último aplica a lo que no es guardar: marcar avisos como leídos, abrir la vista previa de una factura y «Revisar ahora», que ya muestra su propio resultado.
- Los 7 mensajes de éxito que hoy salen dentro de los formularios pasan al aviso común, con el mismo texto, para no mostrar dos.
- El aviso sale abajo al centro, se cierra solo a los 3,5 s o al tocarlo y lo leen los lectores de pantalla (`role="status"`). En el celular no tapa los botones del formulario.
- Los errores siguen dentro de cada formulario, como hoy.

## Fuera de alcance

- Conectar los equipos con la bodega. Eso está en la propuesta de inventario.
- Avisos para errores. Ya hay mensajes en cada formulario.

## Paquetes de Mateo

`field_ops` (modelo, servicio, router y pantallas del acta) y `notifications` (pantalla de preferencias). Hay que avisarle.
