# Instalar con el permiso solo radicado — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Interruptor `PERMIT_FILED_ALLOWS_INSTALL` (por defecto `false`, como hoy) que permite pasar a «Listo para instalar» con el permiso solo radicado, sin tocar la regla del cobro.

**Spec:** `docs/superpowers/specs/2026-10-16-instalar-con-permiso-radicado-design.md`

## Global Constraints

- Por defecto todo queda igual.
- El requisito de cobro `permit_approved` no cambia.
- Rechazado y aprobado-vencido bloquean siempre.
- Paquete de Mateo: avisarle. Sin commit hasta que José lo pida.

## Review Focus

- Que el cobro no se destrabe.
- Que la guarda manual y el avance automático usen la misma regla.

---

### Task 1: Regla y pruebas

- [x] Pruebas que fallan (`tests/test_permits_filed_install.py`): con `false` igual que hoy; con `true` radicado avanza y rechazado/vencido no; cobro sigue estricto; `allows_install` en la respuesta.
- [x] `config.py` y `.env.example`: la variable.
- [x] `permits.py`: `allows_install` / `all_allow_install`; `_finish` y `as_response` la usan; `schemas.PermitResponse.allows_install`.
- [x] `guards.py`: la guarda usa la regla nueva y un mensaje según la variable.
- [x] Ver pasar; correr pruebas de campo y cobro.

### Task 2: Pantalla

- [x] `types/fieldOps.ts`: `allows_install`.
- [x] `PermitsPanel.tsx`: frase de arriba y texto de la tarjeta según `allows_install`.
- [x] `npm run build` y `check_hooks.py`.

### Task 3: Verificación

- [x] Batería completa de pytest (540 en verde).
- [x] Informar a José; comiteado en devjj el 16 oct a pedido suyo.
