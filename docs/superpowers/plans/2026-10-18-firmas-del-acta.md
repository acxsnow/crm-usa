# Firmas del acta como paso propio — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Las firmas pasan a ser el paso 5 del acta, el cliente puede firmar en el celular del técnico, se puede consultar si ya firmó por el enlace y el técnico ya no puede ver ni firmar órdenes ajenas.

**Spec:** `docs/superpowers/specs/2026-10-18-firmas-del-acta-design.md`

## Global Constraints

- Las firmas no bloquean el cierre ni el cobro (decisión pendiente con Mariana).
- Técnico: solo sus órdenes (`get_visible_project`).
- Paquete de Mateo: avisarle. Commit solo cuando José lo pida; nada a main.

## Review Focus

- Una firma no se reescribe.
- La firma en persona queda distinguible en la auditoría.
- Tras recargar, la pantalla sigue sabiendo que el enlace se envió.

---

### Task 1: API

- [x] Pruebas que fallan (`tests/test_attestation_signing.py`): técnico ajeno → 404 en firmar, pedir enlace y ver; firmar dos veces → 409; firma en persona con `method` en la auditoría; enlace pendiente en la respuesta.
- [x] Servicio, router y esquema.
- [x] Ver pasar las nuevas, `test_customer_remote_signature.py`, `test_field_ops.py` y `test_rbac_full.py`.

### Task 2: Pantalla

- [x] `SignaturesPanel.tsx` (técnico, cliente con enlace y en persona, «Consultar si ya firmó»); sale de Anexos.
- [x] Paso «Firmas del acta» en `ProjectDetailPage` y `deriveStates`; el acta baja hasta el paso nuevo cuando se abre solo.
- [x] Aviso de «Guardar equipos instalados» invita a las firmas.
- [x] `npm run build` y `check_hooks.py`.

### Task 3: Verificación

- [x] Batería completa de pytest: 556 pasan.
- [x] Navegador como técnico: guardar equipos → se abre «Firmas del acta»; firma del técnico; cliente en este celular → PDF; «Consultar si ya firmó» con el enlace pendiente; celular de 390 px.
- [ ] Recorrido manual actualizado (hecho). Informar a José; commit cuando lo pida.
