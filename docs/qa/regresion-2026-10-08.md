# Regresión completa del CRM · 8 de octubre de 2026

Análisis de QA sobre `main` (commit `39e30c4`), en local con `docker compose`. La base se cargó desde cero con `scripts.seed --demo-org --demo-users`.

## Resultado

**No pasa la regresión.** Lo funcional se sostiene: el flujo completo, de la puerta al pago, funciona con los seis roles; los permisos por rol coinciden con el menú y no hubo fugas entre organizaciones. Pero la integración continua de `main` queda en rojo (cobertura 69,75% contra un mínimo de 70%, más una prueba que depende de la hora), y hay hallazgos de privacidad y de presentación que conviene cerrar antes de mostrarle la app a un cliente.

| Frente | Resultado |
|---|---|
| Pruebas del backend (`pytest` con cobertura) | 472 pasan, **1 falla**. Cobertura **69,75%** (mínimo 70%) |
| Compilación del frontend (`tsc -b` + `vite build`) | Pasa. Aviso: paquete JS de 620 KB sin dividir |
| QA de punta a punta contra la app real (`scripts/qa_e2e.py`) | **219 de 219 pasos**, después de preparar tres datos que la carga demo no trae (ver QA-REG-06) |
| Aislamiento entre organizaciones (en vivo) | **0 fugas.** 74 accesos a recursos de otra organización bloqueados con 404/403 |
| Barrido de pantallas por rol en navegador (Playwright) | 207 pantallas: 6 roles en escritorio, más Vendedor y Técnico en celular (390×844). La matriz de acceso coincide con el menú |

## Hallazgos

| ID | Severidad | Hallazgo | Estado |
|---|---|---|---|
| QA-REG-01 | Alta | La integración continua de `main` queda en rojo: cobertura bajo el mínimo y una prueba que depende de la hora | En parte: la prueba que dependía de la hora la corrigió Mateo (`fffd2d4`); falta la cobertura |
| QA-REG-02 | Media | Vendedor y Técnico ven el directorio completo de clientes con sus datos personales | Abierto |
| QA-REG-03 | Media | La pantalla de inicio muestra actividad inventada, fija en el código | Resuelto el 8 oct en `devjj`, sin integrar a `main` |
| QA-REG-04 | Media | La página pública de firma y los correos llevan la marca «PAP.CRM» | Abierto |
| QA-REG-05 | Media | El ingreso está en inglés y siempre dice «Invalid email or password.» | Abierto |
| QA-REG-06 | Media | La zona de venta y la jurisdicción de cobro se configuran por separado; la carga demo no deja la app lista para cobrar | Abierto |
| QA-REG-07 | Media | Una dirección inexistente muestra la pantalla de error técnico de React | Abierto |
| QA-REG-08 | Baja | El historial del expediente muestra un código interno | Resuelto el 8 oct en `devjj`, sin integrar a `main`: el backend manda las etiquetas de cada evento y las fechas llevan el mes en letras |
| QA-REG-09 | Baja | La revisión del expediente se desborda 343 px a lo ancho | Resuelto el 8 oct en `devjj`, sin integrar a `main`: el input de archivo oculto se ancla a su etiqueta |
| QA-REG-10 | Baja | Varias pantallas piden datos que el rol no puede ver (403/409 en consola) | Resuelto el 8 oct en `devjj`, sin integrar a `main`. El 409 del formulario sin programa se deja: es la respuesta prevista que muestra el selector de programa |
| QA-REG-11 | Baja | El paquete del frontend pesa 620 KB en un solo archivo | Abierto |
| QA-REG-12 | Baja | «Proyectos en curso» del Inicio marca 0 aunque hay proyectos | Abierto (encontrado el 8 oct al arreglar QA-REG-03) |
| QA-REG-13 | Baja | Dos pruebas del backend fallan según el orden en que se corran | Abierto (encontrado el 8 oct al arreglar QA-REG-03) |

### QA-REG-01 · Alta · La integración continua de `main` queda en rojo

**Qué pasa:**
1. **Una prueba falla según la hora.** `tests/test_campaigns.py::test_sending_in_test_mode_marks_not_sent` fija «siempre de día» (`monkeypatch` de `next_allowed`) *después* de lanzar la campaña. El lanzamiento ([campaigns.py:500](../../backend/app/modules/notifications/campaigns.py)) ya calculó la hora permitida del cliente (8 a. m. a 9 p. m.). Corrida a las 05:30 UTC, de noche en California, el envío queda para la mañana y `send_due` devuelve 0.
2. **La cobertura queda en 69,75%**, por debajo del 70% que exige `ci.yml` (`--cov-fail-under=70`).
3. **La cobertura probablemente se mide de menos.** No hay configuración de coverage con `concurrency = greenlet`. Con SQLAlchemy asíncrono suele perderse el código que corre dentro de las consultas: `billing/claims.py` sale con 29% aunque tiene muchas pruebas.

**Cómo se reproduce:** `docker compose exec api python -m pytest -q --cov=app --cov-fail-under=70` fuera del horario de 8 a. m. a 9 p. m. de California.

**Evidencia:** [evidencia-2026-10-08/pytest-salida.txt](evidencia-2026-10-08/pytest-salida.txt) (`1 failed, 472 passed`, `Total coverage: 69.75%`).

**Recomendación:**
- Mover el `monkeypatch` antes del `launch` en la prueba.
- Agregar `[coverage:run] concurrency = greenlet, thread`, o un `.coveragerc`, y volver a medir.
- No bajar el umbral.

### QA-REG-02 · Media · Vendedor y Técnico ven el directorio completo de clientes

**Qué pasa:** `customers.read` no distingue «los míos» de «todos». Los cuatro roles probados (Administrador, Vendedor, Técnico y Contabilidad) reciben los mismos 7 clientes de la organización, con nombre, teléfono, correo y dirección. En cambio, los expedientes sí separan `cases.read_own` de `cases.read_all`. La documentación (`docs/decisiones.md`, `docs/PERMISOS.md`) no registra que esto sea a propósito.

**Cómo se reproduce:**
1. Entrar como `vendedor@demo-org.com`.
2. Abrir «Clientes»: aparecen clientes de otros vendedores y los particulares de Contabilidad.

**Evidencia:** [vendedor-directorio-clientes.png](evidencia-2026-10-08/vendedor-directorio-clientes.png). `GET /customers` devuelve `total` 7 para admin, vendedor, técnico y contabilidad.

**Recomendación:**
- Decidir con el cliente si Vendedor y Técnico deben ver solo los clientes de sus expedientes y proyectos.
- Si es así, separar `customers.read_own` y `customers.read_all` como en expedientes.
- Si se decide dejarlo abierto, anotarlo en `docs/decisiones.md`.

### QA-REG-03 · Media · La pantalla de inicio muestra actividad inventada

**Qué pasa:** el panel «Actividad reciente» de [DashboardHome.tsx:86](../../frontend/src/app/DashboardHome.tsx) está escrito a mano. Todos los roles ven «María convirtió un prospecto · James Wilson · Programa CARE», «INV-2026-0042 · $2,450.00», «Robert Chen · San Francisco». Ninguno existe en la base, y el botón «Ver todo →» no hace nada. Gerencia podría tomar esas cifras como reales.

**Cómo se reproduce:** entrar con cualquier usuario y abrir «Inicio».

**Evidencia:** [vendedor-celular-inicio.png](evidencia-2026-10-08/vendedor-celular-inicio.png).

**Recomendación:** alimentar el panel con `case_stage_events` y la auditoría, o quitarlo hasta que exista.

### QA-REG-04 · Media · La página pública de firma y los correos llevan la marca «PAP.CRM»

**Qué pasa:**
- **El cliente final ve otra marca.** La página que abre el cliente para firmar el acta ([CustomerSignaturePage.tsx:17-20](../../frontend/src/features/field-ops/CustomerSignaturePage.tsx)) dice «PAP.CRM», no Delta HVAC. Los avisos por correo también dicen «PAP.CRM» ([notifications/email.py:107](../../backend/app/modules/notifications/email.py), [notifications/service.py:214,247](../../backend/app/modules/notifications/service.py)).
- **El idioma y la fecha no corresponden al cliente.** La página está solo en español y la fecha de vencimiento usa el formato de Colombia (`es-CO`), aunque los clientes están en California, Arizona y Nevada.
- **La pestaña del navegador dice «CRM Field Operations»** (`frontend/index.html`).

**Cómo se reproduce:** pedir la firma remota del acta desde un proyecto y abrir el enlace.

**Recomendación:**
- Llevar el nombre de la marca a la configuración de la organización.
- Confirmar con el cliente el idioma de las páginas públicas (inglés o bilingüe).

### QA-REG-05 · Media · El ingreso está en inglés y siempre dice «Invalid email or password.»

**Qué pasa:** [LoginPage.tsx:23-24](../../frontend/src/features/auth/LoginPage.tsx) captura cualquier error y muestra el mismo mensaje en inglés. En el QA, el bloqueo por demasiados intentos (HTTP 429) apareció como «Invalid email or password.». Pasaría lo mismo con el servidor caído o sin señal en el parque, y el vendedor creería que olvidó su clave. El resto de la pantalla también está en inglés («SIGN IN», «Forgot password?»), igual que las de recuperar contraseña y aceptar la invitación.

**Cómo se reproduce:**
1. Intentar entrar varias veces con una clave equivocada hasta el bloqueo.
2. Entrar con la clave correcta: dice «Invalid email or password.».

**Recomendación:** mostrar el mensaje que devuelve la API (ya viene en español según `docs/ERRORES.md`), con textos propios para 429 y para falta de conexión.

### QA-REG-06 · Media · La zona de venta y la jurisdicción de cobro se configuran por separado

**Qué pasa:**
- **Se configura dos veces y nada lo avisa.** Para vender, el módulo de programas usa zonas de venta (`program_zones`). Para cobrar, el módulo de cobro usa jurisdicciones por ciudad o código postal (`program_jurisdictions`). Un expediente vendido dentro de una zona y aprobado llega hasta la instalación y se bloquea al crear el cobro: «La dirección no está en la zona de… en la fecha de la instalación».
- **La carga demo no deja la app lista para cobrar.** No trae zonas, tarifas ni jurisdicciones, así que con una base nueva no se puede cobrar.
- **El script de punta a punta ya no corre sobre una base nueva.** Asume datos preparados a mano. Sobre la base recién cargada falló 8 de 210 pasos, primero por la tarifa y luego por la jurisdicción. Con la preparación hecha como lo haría el Administrador (zona de TECH para el vendedor, tarifas de TECH y Arizona, ZIP 91340 y 85001 como jurisdicción de cobro), pasaron 219 de 219.

**Cómo se reproduce:** base nueva con la carga demo, vender un expediente de TECH, aprobarlo, instalar y confirmar el acta, y crear el cobro.

**Recomendación:**
- Que la carga demo deje cada programa listo para cobrar.
- Que el script prepare lo que necesita.
- Avisar en la configuración del programa cuando una zona de venta no tiene jurisdicción de cobro equivalente, o derivar una de la otra.

### QA-REG-07 · Media · Una dirección inexistente muestra la pantalla de error técnico de React

**Qué pasa:** las entradas en gris del menú (`/permits`, `/expenses`, `/payables`, `/finance-close`, `/reports`), o cualquier dirección que no exista, muestran «Unexpected Application Error! 404 Not Found… Hey developer 👋» en inglés, sin menú ni forma de volver. El router no define `errorElement`.

**Evidencia:** [ruta-inexistente-404.png](evidencia-2026-10-08/ruta-inexistente-404.png).

**Recomendación:** una página «No encontrado» dentro del layout, con enlace a Inicio.

### QA-REG-08 · Baja · El historial del expediente muestra un código interno

**Qué pasa:** en la revisión del expediente, el historial muestra «install_scheduled» en lugar de un texto en español; las demás entradas sí están traducidas. Las fechas salen como «8/10/2026», que en Estados Unidos se lee como 10 de agosto.

**Evidencia:** [revision-expediente-historial.png](evidencia-2026-10-08/revision-expediente-historial.png).

### QA-REG-09 · Baja · La revisión del expediente se desborda a lo ancho

**Qué pasa:** en `/cases/{id}/review`, a 1366 px de ancho, la página mide 343 px más que la ventana y aparece barra de desplazamiento horizontal (Administrador y Administración).

### QA-REG-10 · Baja · Varias pantallas piden datos que el rol no puede ver

**Qué pasa:** la pantalla funciona, pero quedan errores en consola y peticiones de más:
- **Proyectos y Auditoría** piden `GET /users` (403) para Administración, Técnico, Contabilidad y Gerencia.
- **El acta, abierta por Contabilidad**, pide las evidencias (403).
- **El formulario del expediente**, sin programa elegido, hace `GET /cases/{id}/form` (409) antes de mostrar «¿Para qué programa es?».
- **El formulario, abierto por Contabilidad y Gerencia**, llama a `POST /program-versions/{id}/preview` (403).

Con señal débil, cada petición que sobra cuesta.

**Evidencia:** [contabilidad-acta.png](evidencia-2026-10-08/contabilidad-acta.png).

### QA-REG-11 · Baja · El paquete del frontend pesa 620 KB en un solo archivo

**Qué pasa:** `vite build` avisa que el archivo principal pesa 620 KB (177 KB comprimido). En un parque con señal débil, la primera carga del vendedor tarda.

**Recomendación:** dividir por ruta con `import()`.

### QA-REG-12 · Baja · «Proyectos en curso» del Inicio marca 0 aunque hay proyectos

**Qué pasa:** la tarjeta cuenta los proyectos con estado `planning`, `scheduled` o `in_progress` ([DashboardHome.tsx](../../frontend/src/app/DashboardHome.tsx)), pero los proyectos que nacen de un expediente aprobado no usan esos estados. Con proyectos instalados y en cobro en la base, la tarjeta muestra 0.

**Cómo se reproduce:** entrar como `admin@demo-org.com` después de correr el QA de punta a punta y mirar la tarjeta «Proyectos en curso».

**Recomendación:** contar por la etapa del expediente (aprobado a inspección pendiente) o alinear los estados del proyecto, y que la tarjeta diga qué cuenta.

### QA-REG-13 · Baja · Dos pruebas del backend fallan según el orden en que se corran

**Qué pasa:** si `tests/test_cases_api.py` corre justo antes que `tests/test_cases_service.py`, fallan `test_a_guard_can_block_a_transition` y `test_changing_the_stage_clears_the_previous_substatus`: quedan registrados los efectos de campo (crear el proyecto al aprobar) y el expediente de la prueba no tiene cliente. Solas pasan. En la corrida completa no aparece porque `test_cases_intake.py` corre en medio y limpia los registros. Ya pasaba antes de los cambios del 8 de octubre.

**Cómo se reproduce:** `python -m pytest tests/test_cases_api.py tests/test_cases_service.py`.

**Recomendación:** que `test_cases_api.py` limpie guardas y efectos al terminar, como ya lo hacen `test_programs.py` y `test_case_documents.py` con su fixture `_clean_registries`.

## Lo que se verificó y está bien

- **Flujo completo con un usuario por rol** (219 pasos):
  - Salidas tempranas y reapertura de la misma puerta, aunque la dirección esté escrita distinto.
  - Venta, devolución y aprobación de TECH.
  - Permiso, agenda, checklist y acta devuelta y confirmada.
  - Cobro rechazado, reintentado y pagado, y cierre.
  - Arizona con inspección fallida y luego aprobada.
  - Expediente rechazado, corregido y cerrado.
  - Notificaciones, alertas diarias, campañas, y cotización → factura → pago.
- **Lo que no se debe poder hacer:**
  - El vendedor no puede aprobar su propio expediente.
  - Un archivo disfrazado (un ejecutable con nombre `.jpg`) se rechaza.
  - Un cobro duplicado se bloquea.
  - Sin sesión responde 401, y el webhook de Masiv rechaza un token falso.
- **Aislamiento entre organizaciones:** se creó «QA Org B» con un administrador con todos los permisos. Con su token se llamó a cada ruta que recibe un identificador, usando identificadores reales de la organización demo: 74 respondieron 404/403 y ninguna 2xx.
- **Acceso por rol en el navegador:** las 18 rutas por los 6 roles coinciden con el menú. Nadie entra a lo que no ve, y nada visible queda bloqueado. Las pantallas de detalle (cliente, expediente, formulario, acta, versión de programa) abren para quien debe.
- **Celular:** las pantallas de Vendedor y Técnico no se desbordan a 390 px.

## Lo que no se pudo probar

- **GPS real, señal débil o sin conexión, y la cámara del teléfono:** se necesita un teléfono en campo.
- **Envío real de SMS por Masiv** (sin credenciales) **y de correo de campañas:** corrieron en modo de prueba.
- **Las rutas que borran (`DELETE`) y las que envían mensajes** se excluyeron de la prueba entre organizaciones. Otras 49 respondieron 422 porque la validación del cuerpo va antes de buscar el recurso, así que en esas no queda probado el aislamiento. Las pruebas del backend sí lo cubren en 18 archivos.
- **No hay pruebas automatizadas de frontend.**

## Datos que quedaron en la base local

- **Registros de las tres corridas del QA de punta a punta**, con el prefijo «QA 1008…».
- **La organización «QA Org B»**, con el usuario `qa-orgb-admin@example.com`.
- **La configuración creada para la prueba:**
  - Zonas de venta: «QA San Fernando…» y «QA Desert Palms Phoenix…».
  - Tarifas: TECH $4,500 y Arizona $6,000, desde el 1 de enero de 2026.
  - Jurisdicciones de cobro: ZIP 91340 y 85001.

Todo es de prueba. Para volver a una base limpia: `docker compose down -v` y cargar de nuevo los datos demo.

## Cómo se ejecutó

- **Pruebas del backend:** `docker compose exec api python -m pytest -q --cov=app --cov-report=term --cov-fail-under=70`.
- **Frontend:** `npx tsc -b && npx vite build`, dentro del contenedor `frontend`.
- **QA de punta a punta:** `scripts/qa_e2e.py` dentro del contenedor `api`. En una copia temporal se agregó la preparación descrita en QA-REG-06, y un sustituto del comando `docker` que habla directo con Redis y Postgres. El script del repositorio no se modificó. Informe: [qa-e2e-2026-10-08-1008053909.md](qa-e2e-2026-10-08-1008053909.md).
- **Barrido en navegador:** Playwright 1.47 (Chromium) en un contenedor dentro de la red de `docker compose`. Por cada rol, 23 rutas y la primera pantalla de detalle que enlaza cada lista. Se registraron errores de consola, respuestas de la API ≥ 400, desbordes y capturas.
