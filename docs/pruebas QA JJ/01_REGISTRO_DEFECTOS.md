# Registro de defectos

Cada defecto con su ID `D-###`, en orden de aparición. Un defecto solo pasa a **Cerrado** después de reejecutar el escenario que lo encontró y su regresión.

**Estados:** Abierto · En análisis · En corrección · Corregido (pendiente de validar) · Cerrado · No es defecto · Diferido (con aprobación).

## Resumen

| ID | Título | Módulo | Prioridad | Estado | Encontrado en | Responsable | Fecha |
|---|---|---|---|---|---|---|---|
| D-001 | No existe la visita fallida de instalación, el reagendamiento con límite ni la cancelación de la obra | Instalación en campo / Bodega | P0 | Corregido (validado por API; falta pantalla) | Diagnóstico de código (INS-010 a INS-012) | José Javier Miranda (paquetes de Mateo: avisarle) | 2026-10-25 |
| D-002 | El margen negativo en Rentabilidad se corta y muestra «$-80,705.0…» con formato «$-» | Finanzas | P2 | Corregido (pendiente de validar en pantalla) | Toma de capturas del manual (FIN-005) | Mateo Mazo | 2026-10-25 |
| D-003 | Movimientos de bodega: el orden no tiene desempate y la paginación repite y omite filas | Bodega | P1 | Cerrado (2026-10-25) | API-002 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-004 | Filtros de texto no escapan `%` y `_` (funcionan como comodines) | Varios | P2 | Cerrado (2026-10-25) | SEC-004 | José Javier Miranda (compartido) | 2026-10-25 |
| D-005 | Ingreso: mensajes de la API en inglés y la pantalla no distingue la cuenta bloqueada | Acceso | P2 | Cerrado (2026-10-25) | AUTH-002 | José Javier Miranda (`auth`) | 2026-10-25 |
| D-006 | Los intentos fallidos y los bloqueos de ingreso no quedan en la auditoría | Acceso | P2 | Cerrado (2026-10-25) | AUTH-002 | José Javier Miranda (`auth`) | 2026-10-25 |
| D-007 | «Con serial» no tiene efecto: la bodega no registra seriales al entregar | Bodega | P2 | Corregido (validado por API; falta pantalla) | BOD-011 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-008 | La devolución a bodega no tiene tope: se devuelve más de lo que salió para la obra | Bodega | P1 | Cerrado (2026-10-25) | BOD-006 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-009 | Un artículo acepta costo unitario negativo | Bodega | P2 | Cerrado (2026-10-25) | BOD-002 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-010 | Crear un artículo con un SKU repetido responde 500 | Bodega | P1 | Cerrado (2026-10-25) | BOD-002 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-011 | Rotar antes de la fecha agendada deja el historial de responsables incoherente | Instalación en campo | P2 | Cerrado (2026-10-25) | INS-008 | Mateo Mazo (`field_ops`) | 2026-10-25 |
| D-012 | Dos autorizaciones simultáneas de la misma salida pasan las dos | Bodega | P2 | Cerrado (2026-10-25) | CON-001 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-013 | Un técnico descarga la foto de una obra que no es suya con solo el id | Seguridad / Instalación en campo | P1 | Cerrado (2026-10-25) | SEC-006 | José Javier Miranda (`field_ops`, paquete de Mateo: avisarle) | 2026-10-25 |
| D-014 | Siete permisos del catálogo no controlan nada | Seguridad / Roles | P3 | Cerrado (2026-10-25) | SEC-003 | José Javier Miranda y Mateo Mazo | 2026-10-25 |
| D-015 | Una factura acepta pagos por encima del saldo | Trabajo particular y facturación | P1 | Cerrado (2026-10-25) | PAR-003 | José Javier Miranda (`billing`, paquete de Mateo: avisarle) | 2026-10-25 |
| D-016 | Factura, pago y gasto con datos inválidos responden 500 | Finanzas | P2 | Cerrado (2026-10-25) | FIN-002 | José Javier Miranda (`finance`, paquete de Mateo: avisarle) | 2026-10-25 |
| D-017 | Importar dos veces el mismo extracto duplica los movimientos | Finanzas | P2 | Cerrado (2026-10-25) | FIN-003 | José Javier Miranda (`finance`, paquete de Mateo: avisarle) | 2026-10-25 |
| D-018 | La salida de bodega no guarda el costo: cambia el costo de obras cerradas | Bodega | P2 | Cerrado (2026-10-25) | BOD-007 | José Javier Miranda (`warehouse`, paquete de Mateo: avisarle) | 2026-10-25 |
| D-019 | La nómina no aplica las reglas de Don Aldo: almuerzo según la forma de pago y extras declaradas con el valor del jefe | Turnos y nómina | P2 | Abierto (decisión pendiente) | TUR-005 | José Javier Miranda y Mateo Mazo (`attendance`) | 2026-10-25 |
| D-020 | La auditoría no muestra el antes y el después | Seguridad / Auditoría | P2 | Cerrado (2026-10-25) | SEC-010 | José Javier Miranda (`organizations`) | 2026-10-25 |

## D-001 · Visita fallida, reagendamiento con límite y cancelación de la obra

- **Módulo:** Instalación en campo (`field_ops`), Bodega (`warehouse`) y Proyectos.
- **Prioridad:** P0. Es un camino diario del negocio y no tenía salida en el sistema.
- **Estado:** Corregido (pendiente de validar con INS-010 a INS-012).
- **Encontrado en:** diagnóstico de código previo al QA (25 de octubre de 2026).
- **Qué pasa hoy (verificado en el código):**
  - La obra no tiene forma de registrar «llegué y el cliente no estaba». Solo se puede cambiar la fecha.
  - El estado `cancelled` de la obra existe, pero no hay acción que lo use: la edición de la obra solo acepta título y notas.
  - No hay contador ni límite de reagendamientos.
- **Qué se espera (lo pidió José el 25 de octubre de 2026):**
  1. El técnico registra la visita fallida con el motivo (cliente no estaba, no dejó entrar, falta material, otro), una nota y una foto con GPS.
  2. La obra vuelve a «por agendar» sin técnico ni fecha, y Administración recibe el aviso.
  3. Hay un contador de visitas fallidas y un límite que se configura por organización.
  4. Al llegar al límite ya no se reagenda sola: Administración decide entre cancelar o autorizar un intento más.
  5. Cancelar exige motivo, deja la obra en solo lectura y obliga a resolver el material: se reintegra a bodega o se traslada a otra obra o camioneta.
  6. Nada de esto cambia la etapa del expediente por fuera de `advance_case()` / `transition()`.
  7. Cada paso tiene su permiso, su prueba automática y queda en el manual.
- **Escenarios relacionados:** INS-010, INS-011, INS-012, BOD-006.
- **Evidencia:** no hay ruta en `field_ops/router.py` ni en `projects` que registre la visita fallida o cancele la obra.
- **Análisis / causa:** el alcance original solo cubría el camino de instalación exitosa.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):**
  - Servicio nuevo `backend/app/modules/field_ops/visits.py` y migración `0042_visitas_fallidas_y_cancelacion`.
  - Tablas `project_visit_attempts` y `field_ops_settings` (límite por organización, 2 por defecto, de 1 a 10). La obra gana `failed_visits_count`, `extra_visits_authorized` y los datos de cancelación.
  - Rutas:
    - `POST /projects/{id}/failed-visits` (`checklists.complete`, solo el técnico responsable o la oficina) y `GET` paginado.
    - `GET /projects/{id}/visit-status`.
    - `POST /projects/{id}/extra-visit` (`dispatch.manage`).
    - `GET /projects/{id}/cancellation-check` y `POST /projects/{id}/cancel` (`projects.close`).
    - `GET` y `PUT /field-ops/settings` (`PUT` con `projects.close`).
  - El catálogo de motivos viaja en `GET /field-ops/catalogs` (`visit_failure_reasons`).
  - Sub-estado nuevo del expediente «Listo para instalar · Visita fallida» (`cases/stages.py`), con su permiso propio (`checklists.complete`). `mark_substatus` ahora respeta el permiso del sub-estado.
  - «Liberar orden» se bloquea al llegar al límite (`visit_limit_reached`).
  - La obra cancelada queda congelada (`ensure_installation_open`) y el expediente se cierra por `advance_case`.
  - Avisos nuevos:
    - `installation.visit_failed`, a quien agenda.
    - `project.cancelled`, al técnico.
  - Pantalla: en el paso «Orden liberada» de la obra:
    - «No se pudo hacer la visita» e historial de visitas fallidas.
    - «Autorizar otro intento».
    - «Cancelar la obra…» con salidas abiertas y material afuera.
    - Límite de visitas fallidas.
  - Pruebas: `backend/tests/test_field_visits.py` (14).
  - Paquetes de Mateo tocados (`field_ops`, `notifications`): solo líneas nuevas; avisarle.
- **Commit:** ver el historial de `devjj` («feat(campo): visita fallida, límite de reagendamiento y cancelación de la obra»).
- **Validación (escenarios reejecutados):** por API el 25 oct (lote 2): INS-010 16/16, INS-011 14/14, INS-012 13/13. Falta la parte de pantalla de los tres. BOD-006 encontró D-008 (devolución sin tope), que afecta el reintegro antes de cancelar.
- **Tiempos:** análisis 1 h · corrección 3 h · reejecución pendiente.

## D-002 · Margen negativo cortado en Rentabilidad

- **Módulo:** Finanzas › Conciliación y rentabilidad.
- **Prioridad:** P2. Es visual y el dato es correcto, pero se lee mal.
- **Estado:** Corregido (pendiente de validar).
- **Encontrado en:** captura `rentabilidad` del manual de usuario (25 de octubre de 2026).
- **Qué pasa:** con pérdida, la columna del margen muestra «$-80,705.0…»: el número se corta y el signo queda después del símbolo.
- **Qué se espera:** «-$80,705.00» completo (o entre paréntesis), sin cortarse a 390 px ni en escritorio.
- **Escenarios relacionados:** FIN-005.
- **Evidencia:** `docs/manual/capturas/` (figura de Rentabilidad).
- **Responsable:** paquete de Mateo (`finance`): avisarle antes de tocarlo.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `finance/api.ts`, `money` usa el formato de moneda («-$80,705.00», con el signo antes del símbolo). En el indicador «Margen» de Rentabilidad el porcentaje pasa a una línea propia, y los montos de los indicadores de finanzas bajan de línea si no caben, en vez de cortarse con «…» (`finance.css`).
- **Validación:** pendiente, reejecutar FIN-005 en pantalla (escritorio y 390 px).

## D-003 · Movimientos de bodega: paginación inestable

- **Módulo:** Bodega (`warehouse/router.py`, `list_movements`).
- **Prioridad:** P1. El libro de movimientos es la base de la auditoría de bodega: una fila repetida o perdida al pasar de página confunde el conteo.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** API-002, paso 1.
- **Pasos para reproducir:** con la base QA, bajar `GET /api/v1/warehouse/movements?limit=50&offset=0,50,100,150,200` y juntar los ids.
- **Resultado obtenido:** 244 filas, 243 ids distintos.
- **Resultado esperado:** 244 ids distintos.
- **Análisis / causa:** el orden es `movement_date desc, created_at desc`. Los 244 movimientos de la carga tienen la misma fecha y horas casi iguales; sin un desempate único (`id`), Postgres puede devolverlos en distinto orden en cada consulta. La regla del proyecto (`shared/pagination.py`) pide «un ORDER BY estable».
- **Corrección propuesta:** agregar `WarehouseMovement.id` al final del `order_by`, y revisar con el mismo criterio los demás listados.
- **Responsable:** paquete de Mateo: avisarle.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `warehouse/service.py`, `movements_stmt` ordena por `movement_date desc, created_at desc, id desc`. Prueba `test_la_paginacion_de_movimientos_no_repite_filas` (7 movimientos con la misma fecha y hora, páginas de 2).
- **Validación:** API-002 reejecutado el 25 oct con la base QA reiniciada: 244 de 244 distintos. Regresión: lotes 1 y 2 completos sin otros cambios y 760 pruebas del backend pasan. **Cerrado.**

## D-004 · Filtros de texto que no escapan `%` y `_`

- **Módulo:** varios.
  - `cases/router.py`
  - `crm/router.py`
  - `field_ops/projects_router.py`
  - `finance/router.py` (proveedores)
  - `organizations/audit_router.py`
  - `users/router.py`
  - `warehouse/kits.py`, `warehouse/releases.py` y `warehouse/service.py`
- **Prioridad:** P2. No es una inyección (las consultas van parametrizadas y ningún texto alteró la consulta), pero buscar `%` o `_` trae todo.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** SEC-004.
- **Pasos para reproducir:** `GET /api/v1/warehouse/items?q=%25` y `?q=_`.
- **Resultado obtenido:** 244 artículos.
- **Resultado esperado:** solo los que contienen el carácter literal.
- **Análisis / causa:** esos filtros arman `ilike(f"%{q}%")` sin escapar. El buscador global, cobros, expedientes de intake y banca ya usan `escape="\\"`.
- **Corrección propuesta:** usar el mismo helper de escape en todos los filtros.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** función común `app/shared/text_search.py` (`contains_pattern` + `escape=LIKE_ESCAPE`) en los 10 filtros que no escapaban: expedientes, clientes, obras, usuarios, proveedores, auditoría, artículos, kits y salidas. La categoría de bodega compara el nombre exacto con `lower()` en vez de `ilike`. Prueba `tests/test_text_search.py`.
- **Validación:** SEC-004 reejecutado el 25 oct: 16 de 16 por API, `%` trae solo lo que contiene `%`. Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend. **Cerrado.**

## D-005 · Ingreso: mensajes en inglés y bloqueo indistinguible

- **Módulo:** Acceso (`auth/router.py`, `frontend/src/features/auth/LoginPage.tsx`).
- **Prioridad:** P2.
- **Estado:** Corregido (pendiente de validar).
- **Encontrado en:** AUTH-002.
- **Resultado obtenido:**
  - La API responde «Invalid email or password.» y «Too many attempts. Try again later.».
  - La pantalla muestra «El correo o la contraseña no son correctos» en los dos casos.
  - Quien quedó bloqueado cree que la clave está mal y sigue intentando, lo que alarga el bloqueo.
- **Resultado esperado:**
  - Mensajes en español en la API.
  - Con 429, la pantalla dice algo como «Demasiados intentos. Espera 15 minutos o usa ¿Olvidaste tu contraseña?».
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `auth/router.py` responde en español: «El correo o la contraseña no son correctos.» (401) y «Demasiados intentos de ingreso. Espera 15 minutos e inténtalo de nuevo, o recupera tu contraseña.» (429). También se tradujeron cerrar sesión y recuperar contraseña. `LoginPage.tsx` muestra el mensaje del bloqueo y uno propio cuando no hay conexión, en vez de decir siempre «clave errada». El código de error (`http_401`, `http_429`) no cambió. Pruebas en `test_auth.py`.
- **Validación:** AUTH-002 reejecutado el 25 oct: 5 de 5 por API, con los mensajes en español. Falta ver en pantalla que el bloqueo muestra su propio mensaje.
- **Validación en pantalla (2026-10-25, Claude con Playwright):** la pantalla de ingreso muestra el mensaje del bloqueo y el de clave errada por separado (captura `evidencias/pantalla/AUTH-002/bloqueo.jpg`). Capturas en `evidencias/pantalla/D-005/`.

## D-006 · Intentos fallidos y bloqueos fuera de la auditoría

- **Módulo:** Acceso / Auditoría.
- **Prioridad:** P2.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** AUTH-002, validación 2.
- **Resultado obtenido:** `audit_events` solo tiene `auth.login.success`.
- **Resultado esperado:**
  - Registrar el ingreso fallido, sin la clave y con el correo normalizado e IP.
  - Registrar el bloqueo, para detectar ataques de fuerza bruta.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `auth/service.py`, `record_failed_login`: cada intento fallido deja `auth.login.failed` y el bloqueo deja `auth.login.locked` (una sola vez por ventana de 15 minutos, para que un ataque no llene la tabla), en la organización del usuario, con la IP. Un correo que no existe no tiene organización: queda en el log del servidor (`auth.login_failed_unknown_email`). La respuesta al cliente no cambia, así que no revela si el correo existe. Prueba `test_los_ingresos_fallidos_y_el_bloqueo_quedan_en_la_auditoria`.
- **Validación:** AUTH-002 reejecutado el 25 oct: la auditoría tiene `auth.login.failed` (6) y `auth.login.locked` (1). Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend. **Cerrado.**

## D-007 · «Con serial» no tiene efecto en bodega

- **Encontrado en:** BOD-011.
- **Resultado obtenido:**
  - La entrega de una salida (`DeliverIn`) solo recibe nota y cantidades.
  - `has_serial` se guarda en el artículo pero ningún proceso lo usa.
  - El serial aparece recién en «Equipos instalados» de la obra, sin cruce con lo que salió de bodega.
- **Resultado esperado:**
  - Al entregar un artículo con serial, bodega anota el serial de cada unidad.
  - El técnico, en «Equipos instalados», elige entre los seriales que salieron para su obra.
- **Nota:** el formulario dice «Con serial: se rastrea por equipo», lo que promete algo que hoy no pasa. Si no se va a construir, quitar la promesa del texto.
- **Decisión (25 oct, José Javier Miranda):** se construye el control de seriales antes de salir a producción, con su prueba.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** según la spec de bodega del 19 oct (`inventory_serials`, «un serial está en un solo lugar»):
  - Tabla `warehouse_serials` (migración `0043`): un registro por unidad, con estado `in_stock` / `delivered` / `installed`, la obra, la orden y el renglón con que salió, y el equipo donde quedó instalado. Único por organización, artículo y serial.
  - Servicio `warehouse/serials.py`, el único que cambia el estado de un serial.
  - **Entrega** (`POST /warehouse/releases/{id}/deliver`, `lines[].serials`): un artículo con serial sale por unidades enteras y con un serial por unidad; sin ellos responde 400 `serials_count_mismatch`. Un serial que no está en bodega responde 409 `serial_not_in_stock`. Uno no registrado (lo que había antes del control) se registra al entregar.
  - **Entrada** (`POST /warehouse/movements`, `serials`): opcional; si van, uno por unidad y ninguno ya registrado. **Devolución**: obligatoria; solo vuelven los entregados a esa obra y no instalados (409 `serial_not_delivered_here`).
  - **Equipos instalados** (`warehouse_serial_id` o el serial escrito): se cruza con lo que salió para la obra y queda `installed`. Un serial en bodega, de otra obra o ya instalado responde 409 `serial_not_available_here`. Un equipo que no pasó por bodega (D-BOD-3) se registra sin cruce. Borrar el equipo devuelve el serial a `delivered`.
  - Consulta: `GET /warehouse/serials` (Bodega › Seriales, con `warehouse.read`) y `GET /projects/{id}/serials` (el técnico, solo sus obras).
  - Pantalla: campos de serial por unidad en **Entregar**, selector **Equipo que salió de bodega** en Equipos instalados, página **Bodega › Seriales**. Las entradas y devoluciones no tienen formulario en pantalla (tampoco antes): sus seriales van por API.
  - Pruebas: `tests/test_warehouse_serials.py` (5: el recorrido completo, no sale dos veces ni se instala en otra obra, equipo directo sin cruce, reglas de captura, aislamiento por organización y por obra). Manual actualizado (8.4 Equipos instalados, Bodega › Movimientos, Seriales y Entregar).
- **Validación:** BOD-011 reejecutado el 25 oct: lote 2 18 de 18 (entrega de la lista de 3 ton con los seriales del 85980, consulta, técnico, instalación y vuelta a «Entregado») y paso 2 aparte 4 de 4 (mismo serial en otra salida 409, vacío 400). Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend. Falta la parte de pantalla: campos de serial al entregar, selector en Equipos instalados y Bodega › Seriales.

## D-008 · Devolución a bodega sin tope

- **Encontrado en:** BOD-006 (lote 2).
- **Pasos para reproducir:**
  - Obra con 4 unidades entregadas y 3 ya devueltas (queda 1 afuera).
  - `POST /warehouse/movements` con `movement_type=devolucion`, `quantity=50` y la obra.
- **Resultado obtenido:** 201; la existencia de bodega sube 50 y el costo de la obra queda negativo para ese artículo.
- **Resultado esperado:** rechazar con un mensaje como «A esta obra solo le quedan 1 por devolver».
- **Impacto:** infla la existencia y el valor de bodega, y descuadra el costo real de la obra. Afecta también la cancelación (D-001), que exige reintegrar el material.
- **Nota de QA:** la existencia inflada por la prueba se corrigió con un ajuste de -50 («QA: deshacer la devolución de más»).
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `warehouse/service.py`, `record_movement` rechaza una devolución con obra mayor que lo que salió para ella y no ha vuelto (nueva `project_outstanding`: salidas menos devoluciones de esa obra y artículo). Responde 400 `return_exceeds_delivered` con «A esta obra solo le quedan N por devolver de este artículo». Vale para cualquier camino que registre la devolución. Prueba en `test_field_visits.py` (devolver 4 cuando quedan 3).
- **Límite que queda:** una devolución **sin obra** no tiene contra qué compararse y se sigue aceptando.
- **Validación:** BOD-006 reejecutado el 25 oct: 4 de 4, el exceso responde 400 y la existencia no cambia. INS-012 (cancelación con reintegro) sigue pasando. Regresión: lotes 1 y 2 y 760 pruebas del backend. **Cerrado.**

## D-009 · Costo unitario negativo

- **Encontrado en:** BOD-002.
- **Resultado obtenido:** `POST /warehouse/items` con `unit_cost: "-1"` responde 201.
- **Resultado esperado:** 400, «El costo no puede ser negativo». Revisar también el precio de venta y la importación desde Excel.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `warehouse/service.py`, `_price`: costo y precio de venta negativos responden 400 `negative_amount` en el formulario, en la carga del Excel (la fila mala queda como error y las demás se cargan) y en el costo de un movimiento. Los demás montos de bodega (presupuesto, plantillas, costos y cobros adicionales) ya lo validaban. Prueba `test_costo_y_precio_negativos_se_rechazan`.
- **Validación:** BOD-002 reejecutado el 25 oct: 15 de 15. Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend. **Cerrado.**

## D-010 · SKU repetido responde 500

- **Encontrado en:** BOD-002.
- **Resultado obtenido:** `POST /warehouse/items` con un SKU que ya existe (`3496`) responde 500. El log muestra `UniqueViolationError uq_warehouse_item_sku`.
- **Resultado esperado:** 409 con «Ya existe un artículo con el código 3496».
- **Nota:** revisar la edición (cambiar el SKU a uno existente) y si el manejador global de `IntegrityError` debería devolver 409 en vez de 500.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `warehouse/service.py`, `save_item` revisa el código antes de guardar, al crear y al editar, y responde 409 `duplicate_sku` con «Ya existe un artículo con el código N». Prueba `test_el_sku_repetido_responde_409`. El manejador global de `IntegrityError` no se tocó.
- **Validación:** BOD-002 reejecutado el 25 oct: el SKU repetido responde 409. El escenario sigue fallido solo por D-009. Regresión: lotes 1 y 2 y 760 pruebas del backend. **Cerrado.**

## D-011 · Historial de responsables incoherente al rotar antes de la fecha

- **Encontrado en:** INS-008 (rotación de `qa_e2e`).
- **Pasos para reproducir:**
  - Obra agendada para dentro de 2 días con Tito.
  - Hoy, cambiar el técnico a otro con fecha de hoy.
- **Resultado obtenido:**
  - El turno de Tito queda «del 27 al 27».
  - El nuevo queda «desde el 25»: el anterior termina después de que empezó el nuevo.
  - `GET /projects/{id}/assignments` sale ordenado por `started_on` y el actual aparece primero.
- **Resultado esperado:** si la obra no había empezado, el anterior queda sin días («no alcanzó a trabajarla») o se reemplaza su turno, y la lista sale en orden cronológico.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `field_ops/installation.py`, `_record_assignment`: si se rota antes de que empiece el turno del anterior, su turno se corre al día del cambio; ya no termina después de que empieza el nuevo y la lista sale en orden. Conserva la fila y con ella la obra en solo lectura. Prueba `test_rotar_antes_de_la_fecha_no_cruza_los_turnos`.
- **Validación:** INS-008 reejecutado el 25 oct: 9 de 9. Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend. **Cerrado.**

## D-012 · Doble autorización simultánea

- **Encontrado en:** CON-001.
- **Pasos para reproducir:** dos `POST /warehouse/releases/{id}/approve` al mismo tiempo (script `ejecucion/carrera.py`, 10 repeticiones).
- **Resultado obtenido:** en 6 de 10 las dos responden 200 y quedan dos `warehouse.release_authorized` en la auditoría.
- **Resultado esperado:** una pasa y la otra recibe 409.
- **Impacto:** hoy bajo, porque la entrega doble sí está protegida (BOD-016) y la autorización no mueve existencias. Pero el mismo patrón (leer el estado, decidir y escribir sin bloqueo) puede repetirse en acciones de dinero.
- **Corrección propuesta:** `SELECT … FOR UPDATE` de la orden, o un `UPDATE … WHERE status = 'por_autorizar'` que verifique cuántas filas cambió. Revisar el mismo patrón en aprobar expediente, confirmar acta y radicar o pagar cobros.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `warehouse/releases.py`, `get_order(..., for_update=True)` bloquea la fila de la orden (`SELECT … FOR UPDATE` y relectura) al autorizar, rechazar y entregar: la segunda persona espera y ve el estado que dejó la primera. Las pruebas automáticas corren en SQLite, que no tiene este bloqueo: se valida con `carrera.py` contra Postgres. Queda por revisar el mismo patrón en aprobar expediente, confirmar acta y radicar o pagar cobros.
- **Validación:** CON-001 reejecutado el 25 oct: 2 de 2, y `carrera.py` 3 veces: 0 de 30 con doble autorización (antes 6 de 10). La segunda recibe 400 `release_not_pending` (el mismo código que ya daba al autorizar dos veces seguidas), no 409, para no cambiar el contrato. Regresión: lotes 1 y 2 completos sin otros cambios, 770 pruebas del backend y build del frontend. **Cerrado.**

## D-013 · Descarga de evidencias de otra obra

- **Módulo:** Instalación en campo (`field_ops/evidence_router.py`, `GET /evidence/{id}/file`).
- **Prioridad:** P1. Fuga de datos dentro de la organización: fotos de casas de clientes de otra obra.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** SEC-006, lote 3 (25 oct).
- **Pasos para reproducir:** Carlos sube una foto a su obra; Luis (otro técnico, sin esa obra) pide `GET /evidence/{id}/file` con su token.
- **Resultado obtenido:** 200, Luis baja la foto.
- **Resultado esperado:** 404, como en la lista de evidencias de la obra.
- **Análisis / causa:** la descarga solo filtraba por organización; la lista (`GET /projects/{id}/evidence`) sí revisaba la obra con `get_visible_project`. Las demás descargas de archivos (documentos y firma del expediente, adjuntos de facturas, documentos de proveedores, PDF del acta) ya revisaban dueño u obra, o son de roles que ven todo.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** la descarga llama a `get_visible_project` con la obra de la evidencia. Prueba `test_a_technician_cannot_download_evidence_of_another_project` (`tests/test_field_ops.py`).
- **Validación:** SEC-006 reejecutado el 25 oct: sin sesión 401, Luis 404, admin ajeno 404, Carlos y Administración 200.
- **Regresión:** 782 pruebas del backend pasan y el frontend compila. **Cerrado.**

## D-014 · Permisos del catálogo que no controlan nada

- **Módulo:** Roles y permisos (`shared/permissions.py`).
- **Prioridad:** P3. No abre ningún acceso, pero el Administrador marca o quita permisos en «Roles y permisos» que no cambian nada.
- **Estado:** Abierto (decisión pendiente).
- **Encontrado en:** SEC-003, lote 3 (25 oct): barrido de las 406 rutas con permiso.
- **Resultado obtenido:** `customers.delete`, `dashboards.commercial`, `projects.assign`, `evidence.delete`, `reports.generate`, `organization.manage` y `profile.manage` no los exige ninguna ruta ni los usa ninguna pantalla (búsqueda en `backend/app` y `frontend/src`).
- **Resultado esperado:** cada permiso del catálogo controla algo, o no se ofrece.
- **Opciones:** quitarlos del catálogo (y de `DEFAULT_ROLE_PERMISSIONS`), o conectarlos a lo que dicen (por ejemplo, `customers.delete` si se llega a permitir borrar clientes). Decide José con Mateo.
- **Decisión (25 oct, José Javier Miranda):** conectarlos a lo que dicen.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):**
  - `customers.delete`: `DELETE /customers/{id}` y el botón **Borrar cliente**; solo sin expedientes, obras, facturas ni cotizaciones (409 `customer_in_use`); las constancias de autorización se conservan.
  - `evidence.delete`: `DELETE /evidence/{id}` y **Quitar evidencia** en la vista de la foto; borrado lógico, solo con la instalación abierta; si era la única foto de un renglón del checklist que la exige, el renglón vuelve a pendiente.
  - `projects.assign`: poner o cambiar el técnico (agendar y crear obra) lo exige; mover solo la fecha sigue con `dispatch.manage` (403 `assign_not_allowed`).
  - `organization.manage`: los datos de la organización (nombre, logo, dirección, contacto); `settings.manage` queda para la zona horaria y la moneda; para leer basta cualquiera.
  - `profile.manage`: `PATCH /auth/me` y la pantalla **Mi perfil** (el propio nombre).
  - `dashboards.commercial` y `reports.generate`: el reporte comercial pide el primero y los de operación y finanzas el segundo; la página muestra solo las pestañas permitidas. **Cambio de acceso:** con los roles de fábrica, Administración deja de ver los reportes de operación y finanzas, y Contabilidad el comercial.
  - Pruebas: `tests/test_permissions_connected.py` (7), incluida una que falla si algún permiso del catálogo vuelve a quedar sin usar. Manual actualizado.
- **Validación:** pruebas automáticas; falta la parte de pantalla (botones de borrar cliente y quitar evidencia, Mi perfil y pestañas de Reportes).
- **Validación en pantalla (2026-10-25, Claude con Playwright):** «Borrar cliente» solo lo ve el Administrador y al confirmar vuelve a la lista; «Mi perfil» guarda el nombre y se ve en el encabezado (enlace en el menú, también a 390 px); Reportes muestra Comercial a Administración, Operación y Finanzas a Contabilidad, y las tres a Gerencia. Capturas en `evidencias/pantalla/D-014/`.

## D-015 · Pago de factura por encima del saldo

- **Módulo:** Facturación (`billing/service.py`, `record_payment`).
- **Prioridad:** P1. Dinero: el saldo queda negativo y la factura «pagada» con plata de sobra que nadie devuelve.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** PAR-003, lote 3 (25 oct).
- **Pasos para reproducir:** factura de USD 500.00 pagada completa; `POST /invoices/{id}/payments` con 0.01.
- **Resultado obtenido:** 201 y saldo -0.01.
- **Resultado esperado:** rechazo con el saldo que queda.
- **Análisis / causa:** solo se revisaba que el monto fuera mayor que cero. Las cuentas por pagar (`finance/payables.py`) sí topaban cada abono al saldo.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** un pago mayor que el saldo responde 400 `payment_exceeds_balance` («El pago supera el saldo de la factura (USD N).»). Prueba `test_a_payment_cannot_exceed_the_balance`.
- **Validación:** PAR-003 reejecutado: 0.01 de más se rechaza y el saldo sigue en 0.
- **Regresión:** 782 pruebas del backend pasan y el frontend compila. **Cerrado.**

## D-016 · Error 500 con datos inválidos en formularios con archivo

- **Módulo:** Finanzas (`finance/router.py`: gastos, facturas y pagos de proveedores).
- **Prioridad:** P2. Rompe la regla «nunca 500 por una entrada del usuario» (API-004) y deja un error sin explicación en pantalla.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** FIN-002, lote 3 (25 oct).
- **Pasos para reproducir:** `POST /payables/invoices` con `data={"supplier_id": null, ...}`.
- **Resultado obtenido:** 500 `internal_error` (en el log, `ValidationError` de Pydantic sin manejar).
- **Resultado esperado:** 422 con el campo marcado.
- **Análisis / causa:** el JSON del campo `data` se validaba a mano con `model_validate_json`, fuera de la validación de FastAPI.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** `_form_json` convierte el error en el 422 normal (`validation_error`, «Hay datos inválidos en: data.supplier_id.»). Prueba `test_invalid_form_json_is_a_422_not_a_500`.
- **Validación:** FIN-002 reejecutado: el proveedor vacío responde 422.
- **Regresión:** 782 pruebas del backend pasan y el frontend compila. **Cerrado.**

## D-017 · Extracto bancario importado dos veces

- **Módulo:** Finanzas › Conciliación (`finance/reconciliation.py`, `import_statement`).
- **Prioridad:** P2. Duplica movimientos del banco y descuadra la conciliación.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** FIN-003, lote 3 (25 oct).
- **Resultado obtenido:** el mismo CSV dos veces dejaba 8 movimientos en vez de 4.
- **Resultado esperado:** la segunda importación no duplica.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** solo entran los movimientos que no estaban en otro extracto de la misma cuenta, contados por ocurrencias (dos compras iguales el mismo día siguen siendo dos; un extracto que se solapa solo agrega lo nuevo). Si todo estaba, responde 409 `statement_already_imported`. La respuesta trae `duplicated`. Prueba `test_the_same_statement_twice_does_not_duplicate`.
- **Validación:** FIN-003 reejecutado: la segunda importación responde 409 y quedan 4 movimientos.
- **Regresión:** 782 pruebas del backend pasan y el frontend compila. **Cerrado.**

## D-018 · Salida de bodega sin costo guardado

- **Módulo:** Bodega (`warehouse/releases.py`, `deliver_order`) y Costo del trabajo (`warehouse/costing.py`).
- **Prioridad:** P2. Al editar el costo de un artículo cambiaba el costo y la rentabilidad de obras ya cerradas.
- **Estado:** Cerrado (25 oct).
- **Encontrado en:** BOD-007, lote 3 (25 oct): la salida de la obra mostraba valor 0 en el libro de movimientos.
- **Análisis / causa:** la entrega registraba el movimiento sin `unit_cost` y el costo de la obra se calculaba con el costo vigente del catálogo. El material del diario sí guardaba su costo.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** la entrega guarda el costo del día; la migración `0044` completa las salidas anteriores con el costo actual del catálogo. Prueba `test_la_salida_guarda_el_costo_del_dia`.
- **Validación:** BOD-007 reejecutado: la salida tiene su costo y coincidió al centavo con el costo de materiales de la obra.
- **Regresión:** 782 pruebas del backend pasan y el frontend compila. **Cerrado.**

## D-019 · Nómina sin las reglas de pago de Don Aldo

- **Módulo:** Turnos, asistencia y nómina (`attendance`).
- **Prioridad:** P2. Las horas que salen en la nómina no siguen dos respuestas confirmadas por Don Aldo (CLAUDE.md, «Turnos, asistencia y mapa»).
- **Estado:** Abierto (decisión pendiente): es funcionalidad que falta, no una falla de lo construido.
- **Encontrado en:** TUR-005, lote 3 (25 oct).
- **Lo confirmado por Don Aldo:**
  - Cuando pagan por día o por hora el almuerzo va incluido; cuando pagan por trabajo, no.
  - Las horas extra se declaran en horas y el jefe define el valor.
- **Lo que hay en el código:**
  - Ningún dato dice si a un técnico se le paga por día/hora o por trabajo (el perfil del usuario no lo tiene).
  - «Pausas pagadas» es una sola opción para toda la organización (`attendance_settings.paid_pauses`).
  - Las extras se calculan solas desde 8 h al día y 40 a la semana (`calc.overtime`, regla de California); no se declaran ni llevan valor.
- **Opciones:** agregar la forma de pago por técnico y aplicar con ella la regla del almuerzo; y permitir declarar extras en horas con el valor que pone el jefe (o confirmar con Don Aldo que el cálculo automático le sirve). Decide José con Mateo; es del módulo de Mateo.

## D-020 · Auditoría sin el antes y el después

- **Módulo:** Auditoría (`organizations/audit_router.py` y `features/audit/AuditLogPage.tsx`).
- **Prioridad:** P2. Se sabía quién hizo qué y cuándo, pero no qué cambió: no servía para revisar un cambio de dinero, permisos o datos personales.
- **Estado:** Corregido (validado por API; falta pantalla).
- **Encontrado en:** SEC-010, lote 3 (25 oct).
- **Análisis / causa:** `record_audit_event` guarda `before_data`, `after_data` e IP (sin secretos), pero `GET /audit-events` no los devolvía y la pantalla tampoco los mostraba.
- **Corrección (25 de octubre de 2026, José Javier Miranda, en `devjj`):** la API agrega `before_data`, `after_data` e `ip_address` a cada evento (sin quitar nada de lo que ya devolvía) y la pantalla de Auditoría muestra «Ver cambios»: cada campo con su valor anterior → el nuevo, y desde qué IP. Prueba `test_audit_shows_before_and_after`.
- **Validación:** SEC-010 por API: 16 de 16 (12 acciones con su detalle y los permisos de quién ve la auditoría). Falta ver la columna en pantalla.
- **Validación en pantalla (2026-10-25, Claude con Playwright):** la columna «Cambios» muestra «Ver cambios» con cada campo que cambió (antes → después) y la IP. Al revisar la captura se corrigió que mostraba como borrados campos que no cambiaron (nombre, zona y moneda de la organización). Capturas en `evidencias/pantalla/D-020/`.

## Plantilla para defectos nuevos

```
## D-### · Título corto

- Módulo:
- Prioridad: P0 / P1 / P2
- Estado: Abierto
- Encontrado en: escenario y paso
- Pasos para reproducir:
- Resultado obtenido:
- Resultado esperado:
- Evidencia: capturas, ids y respuesta HTTP
- Análisis / causa:
- Corrección y commit:
- Validación (escenarios reejecutados):
- Tiempos: análisis · corrección · reejecución
```
