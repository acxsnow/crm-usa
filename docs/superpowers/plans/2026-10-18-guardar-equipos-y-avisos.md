# «Guardar equipos instalados» y avisos de guardado — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** El paso «Equipos instalados» se completa al guardar la lista, no al agregar el primer equipo, y toda acción que guarda muestra un aviso.

**Spec:** `docs/superpowers/specs/2026-10-18-guardar-equipos-y-avisos-design.md`

## Global Constraints

- Agregar o quitar un equipo deshace la confirmación.
- El backend decide el cierre; el frontend usa la misma regla.
- Avisos con un solo mecanismo (`MutationCache`), sin repetir código en cada pantalla.
- Paquetes de Mateo (`field_ops`, `notifications`): avisarle. Commit solo cuando José lo pida; nada a main.

## Review Focus

- Un proyecto cerrado antes del cambio sigue cerrado y con su paso completo.
- No salen dos mensajes de éxito en la misma pantalla.
- Marcar avisos como leídos no muestra aviso.

---

### Task 1: API

- [x] Pruebas que fallan (`tests/test_equipment_confirm.py`): confirmar exige equipos, agregar o quitar deshace la confirmación, el cierre pide la confirmación, el técnico ajeno no puede, no se confirma con la instalación cerrada.
- [x] Modelo, migración 0026 (con relleno de los cerrados), servicio, router y esquema.
- [x] Ajustar las pruebas existentes que cierran instalaciones (helper de confirmar).
- [x] Ver pasar las nuevas y las de campo.

### Task 2: Pantalla de equipos

- [x] `module5Api.ts`: `confirmEquipment`; tipo `Project.equipment_confirmed_at`.
- [x] `EquipmentPanel`: botón «Guardar equipos instalados».
- [x] `deriveStates` y `closeRequirements` con la confirmación.

### Task 3: Avisos

- [x] `lib/toast.ts`, `components/Toaster.tsx`, estilos, `MutationCache` en `providers.tsx` y tipos de `meta`.
- [x] `silent` en las acciones que no guardan; textos propios donde aporten.
- [x] Quitar los 7 mensajes de éxito duplicados.

### Task 4: Verificación

- [x] `npm run build`, `check_hooks.py` y la batería completa de pytest (551 + la del cierre, aparte: 7 de 7).
- [x] Navegador como técnico: agregar → «En curso» y aviso; guardar → «Completado» y aviso; quitar → vuelve a «En curso».
- [ ] Recorrido manual actualizado (hecho). Informar a José; commit cuando lo pida.
