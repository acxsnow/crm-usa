# Consentimiento y autorización de tratamiento de datos — Plan

> **Para agentes:** se ejecuta en la sesión, fase por fase (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Que el cliente autorice —y quede constancia de— el tratamiento de sus datos personales (nombre, teléfono, correo y dirección) en los cuatro puntos donde se capturan, conforme a lo que aplica en California, Arizona y Nevada.

**Pedido:** «Se guardan nombre, teléfono, correo y dirección de clientes. No se registra autorización de tratamiento. Norma aplicable de California, Arizona y Nevada: por definir… entonces necesitamos el consentimiento y que autoricen el tratamiento de datos». Alcance confirmado por el usuario: **los cuatro puntos de captura** (alta de cliente, edición de cliente, expediente de venta y firma pública del cliente).

**Marco legal verificado (24 oct):** CCPA/CPRA («aviso al momento de la recolección» de California), SB 220 y SB 370 de Nevada (oposición a la venta y datos de salud), A.R.S. § 18-552 de Arizona (sin ley integral: solo notificación de brechas) y TCPA federal (la publicidad por llamada o SMS no puede ser condición para contratar; se advierte aparte y no se pide aquí).

## Decisiones

- Autorización **obligatoria** en cada captura de datos personales; sin ella la API responde `400 consent_required`.
- Evidencia en **tabla propia con historial** (`data_consents`, migración `0038`): una fila nueva por autorización, inmutable, con el texto completo que vio el cliente.
- El aviso vive en el servidor (`crm/privacy.py`) y se sirve por `GET /privacy/consent-notice` (público) para que la pantalla muestre exactamente lo que se guarda.
- La edición de cliente solo pide autorización si cambian campos personales (`legal_name`, `main_phone`, `email`, `billing_address`); notas y etiquetas no.

## Fase 1 — Backend (hecha)

- [x] `crm/privacy.py`: aviso versionado (`2026.1`, español) de 7 puntos (datos, finalidad, con quién se comparten, retención de 7 años, derechos, lo que no cubre, constancia), `require_consent`, `contact_snapshot` y `record_consent`.
- [x] Modelo `DataConsent` (`data_consents`) y migración `0038` con índices y claves foráneas (`organization_id`, `customer_id`, `case_id`).
- [x] `POST /customers` y `PATCH /customers/{id}` exigen `data_consent_accepted` y dejan la constancia con IP y equipo.
- [x] Expediente: `accept_terms` registra la constancia (`case_intake`) con `case_id`, cliente, GPS, IP y equipo; `form_state` devuelve el aviso. El paso de autorización ya era obligatorio para enviar.
- [x] Firma pública del acta (`field_ops.public_customer_sign`): constancia con `public_signature`, cliente del proyecto, IP y equipo del navegador.
- [x] Auditoría: `customer.consent_recorded` y la versión del aviso en `cases.terms_accepted` / `attestation.customer_signed_public`.

## Fase 2 — Frontend (hecha)

- [x] `components/DataConsentNotice.tsx`: el aviso y la casilla, alimentados por `GET /privacy/consent-notice` (una sola consulta en caché para toda la sesión).
- [x] **Clientes**: el alta rápida muestra el aviso y la casilla; sin marcar no se puede agregar.
- [x] **Ficha del cliente**: al cambiar nombre, teléfono, correo o dirección aparecen el aviso y la casilla; guardar queda bloqueado hasta marcarla.
- [x] **Expediente**: el paso de autorización muestra el aviso completo junto a los términos y la firma.
- [x] **Firma pública**: el cliente lee el aviso antes de firmar y el texto de cierre lo dice.
- [x] Estilos (`ui-consent`, `ui-consent-check`) en `index.css`.

## Fase 3 — Pruebas y validación (hecha)

- [x] Pruebas nuevas en `tests/test_crm.py`: sin autorización no se guarda el cliente, la constancia guarda el texto versionado, corregir un dato personal la vuelve a pedir (y las notas no), y el aviso es público.
- [x] Ajustados los `POST /customers` existentes (`test_billing`, `test_field_ops`, `test_customer_remote_signature`, `test_cases_api`, `test_security_hardening`) y `qa_e2e.py`.
- [x] `pytest -q` en verde: **732 pasan**.
- [x] `python3 scripts/check_hooks.py` (frontend) y `npx tsc -b` en verde.
- [x] Migración `0038` aplicada contra Postgres: `alembic upgrade head` (0037 → 0038).
- [x] QA de punta a punta: sección 16 de `backend/scripts/qa_e2e.py` (alta sin/con autorización, edición de notas y de teléfono, aviso público y constancias en la base).

## Fase 4 — Cierre

- [ ] Recorrido en el navegador de los cuatro puntos (Administración y Vendedor; el enlace público con el token del acta), a 1440 px y 390 px.
- [x] `docs/qa/recorrido-manual.md`: Fase 1.5, tabla transversal de la Fase 6 y la migración `0038` en «Antes de empezar».
- [x] Commit en `CadenaB` (committer `mateom`, sin rastro de IA) y merge a `main`: `7998a96`, ya en las dos ramas; al publicar, Render corre `alembic upgrade head` en la API.
- [ ] Publicar en Render (API + frontend) y confirmar en producción que el aviso sale y que la migración `0038` quedó aplicada.
- [ ] Artefacto del plan (claude.ai): no se pudo actualizar desde esta sesión (pide sesión de Claude). El resumen para la próxima actualización quedó anotado en `CLAUDE.md`.
