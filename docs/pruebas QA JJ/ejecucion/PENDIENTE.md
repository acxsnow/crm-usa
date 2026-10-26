# Dónde quedó la QA (25 oct 2026, noche) · para retomar

Pruebas de pantalla con Playwright, «probado por Claude» (ver `ui_comun.py` para correrlas).

## Hecho
- Lote 4a de pantalla (registrado): AUTH-001, AUTH-002, AUTH-006, BUS-002, SEC-009; D-005, D-014 y D-020 cerrados.
- Lote 4b corrido (`lote4b.json`), **todavía sin registrar**. Pasó: INS-010, INS-011, FIN-005 (margen -$80,705.00 completo), VEN-001, REV-001, REV-002, API-001, AUTH-007, TUR-001, TEC-003, TUR-009.

## Pendiente, en orden
1. ~~D-021~~ hecho: corregido en `sistema.css` y validado con `barrido390.py` (133 pantallas de los 6 roles, ninguna se desborda). Registrado y cerrado.
2. Repetir en lote 4b lo que falló por el script:
   - INS-012: llenar «Qué pasó con ese material» y «Por qué se cancela» con `get_by_label` (no son `input[type=text]`).
   - BOD-011 / D-007: en Salidas la orden autorizada está en la pestaña «Todas», no en «Por autorizar»; luego entregar con serial, Equipos instalados y Bodega › Seriales.
   - PER-001 / PER-004: medir con el build de producción (`npm run preview`), no con el servidor de desarrollo (dio 2.2–3.8 s por ser Vite sin empaquetar).
3. Registrar lote 4b con `registrar_pantalla.py` (decisiones como en `decisiones4a.json`).
4. Lote 4c: VEN-004 (formulario a 390 px, marca de agua, campana), INS-004 (fotos, firma con el dedo, PDF), SEC-004 (textos guardados y PDF del acta), SEC-008 (aviso antes de firmar en T&C y firma pública), INS-015 (Slow 3G, doble toque, Offline), PER-003 (build de producción con Slow 3G y CPU 4×), AUTH-005 (16 min sin tocar, Offline, Atrás tras Salir).
5. Antes de cada lote: base QA limpia (`seed_qa --reiniciar --si-borrar-todo`) y, para 4b, `prep4b.py`.
6. Al final: suite completa, commit en `devjj`, y recordar a José: avisar a Mateo, llaves de Stripe/Plaid, D-019 con Don Aldo, integrar a `main` solo cuando él diga y después actualizar el artefacto.
