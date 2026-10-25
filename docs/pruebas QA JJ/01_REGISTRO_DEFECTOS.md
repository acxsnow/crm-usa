# Registro de defectos

Cada defecto con su ID `D-###`, en orden de aparición. Un defecto solo pasa a **Cerrado** después de reejecutar el escenario que lo encontró y su regresión.

**Estados:** Abierto · En análisis · En corrección · Corregido (pendiente de validar) · Cerrado · No es defecto · Diferido (con aprobación).

## Resumen

| ID | Título | Módulo | Prioridad | Estado | Encontrado en | Responsable | Fecha |
|---|---|---|---|---|---|---|---|
| D-001 | No existe la visita fallida de instalación, el reagendamiento con límite ni la cancelación de la obra | Instalación en campo / Bodega | P0 | Corregido (validado por API; falta pantalla) | Diagnóstico de código (INS-010 a INS-012) | José Javier Miranda (paquetes de Mateo: avisarle) | 2026-10-25 |
| D-002 | El margen negativo en Rentabilidad se corta y muestra «$-80,705.0…» con formato «$-» | Finanzas | P2 | Abierto | Toma de capturas del manual (FIN-005) | Mateo Mazo | 2026-10-25 |
| D-003 | Movimientos de bodega: el orden no tiene desempate y la paginación repite y omite filas | Bodega | P1 | Abierto | API-002 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-004 | Filtros de texto no escapan `%` y `_` (funcionan como comodines) | Varios | P2 | Abierto | SEC-004 | José Javier Miranda (compartido) | 2026-10-25 |
| D-005 | Ingreso: mensajes de la API en inglés y la pantalla no distingue la cuenta bloqueada | Acceso | P2 | Abierto | AUTH-002 | José Javier Miranda (`auth`) | 2026-10-25 |
| D-006 | Los intentos fallidos y los bloqueos de ingreso no quedan en la auditoría | Acceso | P2 | Abierto | AUTH-002 | José Javier Miranda (`auth`) | 2026-10-25 |
| D-007 | «Con serial» no tiene efecto: la bodega no registra seriales al entregar | Bodega | P2 | Abierto | BOD-011 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-008 | La devolución a bodega no tiene tope: se devuelve más de lo que salió para la obra | Bodega | P1 | Abierto | BOD-006 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-009 | Un artículo acepta costo unitario negativo | Bodega | P2 | Abierto | BOD-002 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-010 | Crear un artículo con un SKU repetido responde 500 | Bodega | P1 | Abierto | BOD-002 | Mateo Mazo (`warehouse`) | 2026-10-25 |
| D-011 | Rotar antes de la fecha agendada deja el historial de responsables incoherente | Instalación en campo | P2 | Abierto | INS-008 | Mateo Mazo (`field_ops`) | 2026-10-25 |
| D-012 | Dos autorizaciones simultáneas de la misma salida pasan las dos | Bodega | P2 | Abierto | CON-001 | Mateo Mazo (`warehouse`) | 2026-10-25 |

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
- **Estado:** Abierto.
- **Encontrado en:** captura `rentabilidad` del manual de usuario (25 de octubre de 2026).
- **Qué pasa:** con pérdida, la columna del margen muestra «$-80,705.0…»: el número se corta y el signo queda después del símbolo.
- **Qué se espera:** «-$80,705.00» completo (o entre paréntesis), sin cortarse a 390 px ni en escritorio.
- **Escenarios relacionados:** FIN-005.
- **Evidencia:** `docs/manual/capturas/` (figura de Rentabilidad).
- **Responsable:** paquete de Mateo (`finance`): avisarle antes de tocarlo.
- **Corrección:**
- **Commit:**
- **Validación:**

## D-003 · Movimientos de bodega: paginación inestable

- **Módulo:** Bodega (`warehouse/router.py`, `list_movements`).
- **Prioridad:** P1. El libro de movimientos es la base de la auditoría de bodega: una fila repetida o perdida al pasar de página confunde el conteo.
- **Estado:** Abierto.
- **Encontrado en:** API-002, paso 1.
- **Pasos para reproducir:** con la base QA, bajar `GET /api/v1/warehouse/movements?limit=50&offset=0,50,100,150,200` y juntar los ids.
- **Resultado obtenido:** 244 filas, 243 ids distintos.
- **Resultado esperado:** 244 ids distintos.
- **Análisis / causa:** el orden es `movement_date desc, created_at desc`. Los 244 movimientos de la carga tienen la misma fecha y horas casi iguales; sin un desempate único (`id`), Postgres puede devolverlos en distinto orden en cada consulta. La regla del proyecto (`shared/pagination.py`) pide «un ORDER BY estable».
- **Corrección propuesta:** agregar `WarehouseMovement.id` al final del `order_by`, y revisar con el mismo criterio los demás listados.
- **Responsable:** paquete de Mateo: avisarle.

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
- **Estado:** Abierto.
- **Encontrado en:** SEC-004.
- **Pasos para reproducir:** `GET /api/v1/warehouse/items?q=%25` y `?q=_`.
- **Resultado obtenido:** 244 artículos.
- **Resultado esperado:** solo los que contienen el carácter literal.
- **Análisis / causa:** esos filtros arman `ilike(f"%{q}%")` sin escapar. El buscador global, cobros, expedientes de intake y banca ya usan `escape="\\"`.
- **Corrección propuesta:** usar el mismo helper de escape en todos los filtros.

## D-005 · Ingreso: mensajes en inglés y bloqueo indistinguible

- **Módulo:** Acceso (`auth/router.py`, `frontend/src/features/auth/LoginPage.tsx`).
- **Prioridad:** P2.
- **Estado:** Abierto.
- **Encontrado en:** AUTH-002.
- **Resultado obtenido:**
  - La API responde «Invalid email or password.» y «Too many attempts. Try again later.».
  - La pantalla muestra «El correo o la contraseña no son correctos» en los dos casos.
  - Quien quedó bloqueado cree que la clave está mal y sigue intentando, lo que alarga el bloqueo.
- **Resultado esperado:**
  - Mensajes en español en la API.
  - Con 429, la pantalla dice algo como «Demasiados intentos. Espera 15 minutos o usa ¿Olvidaste tu contraseña?».

## D-006 · Intentos fallidos y bloqueos fuera de la auditoría

- **Módulo:** Acceso / Auditoría.
- **Prioridad:** P2.
- **Estado:** Abierto.
- **Encontrado en:** AUTH-002, validación 2.
- **Resultado obtenido:** `audit_events` solo tiene `auth.login.success`.
- **Resultado esperado:**
  - Registrar el ingreso fallido, sin la clave y con el correo normalizado e IP.
  - Registrar el bloqueo, para detectar ataques de fuerza bruta.

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

## D-008 · Devolución a bodega sin tope

- **Encontrado en:** BOD-006 (lote 2).
- **Pasos para reproducir:**
  - Obra con 4 unidades entregadas y 3 ya devueltas (queda 1 afuera).
  - `POST /warehouse/movements` con `movement_type=devolucion`, `quantity=50` y la obra.
- **Resultado obtenido:** 201; la existencia de bodega sube 50 y el costo de la obra queda negativo para ese artículo.
- **Resultado esperado:** rechazar con un mensaje como «A esta obra solo le quedan 1 por devolver».
- **Impacto:** infla la existencia y el valor de bodega, y descuadra el costo real de la obra. Afecta también la cancelación (D-001), que exige reintegrar el material.
- **Nota de QA:** la existencia inflada por la prueba se corrigió con un ajuste de -50 («QA: deshacer la devolución de más»).

## D-009 · Costo unitario negativo

- **Encontrado en:** BOD-002.
- **Resultado obtenido:** `POST /warehouse/items` con `unit_cost: "-1"` responde 201.
- **Resultado esperado:** 400, «El costo no puede ser negativo». Revisar también el precio de venta y la importación desde Excel.

## D-010 · SKU repetido responde 500

- **Encontrado en:** BOD-002.
- **Resultado obtenido:** `POST /warehouse/items` con un SKU que ya existe (`3496`) responde 500. El log muestra `UniqueViolationError uq_warehouse_item_sku`.
- **Resultado esperado:** 409 con «Ya existe un artículo con el código 3496».
- **Nota:** revisar la edición (cambiar el SKU a uno existente) y si el manejador global de `IntegrityError` debería devolver 409 en vez de 500.

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

## D-012 · Doble autorización simultánea

- **Encontrado en:** CON-001.
- **Pasos para reproducir:** dos `POST /warehouse/releases/{id}/approve` al mismo tiempo (script `ejecucion/carrera.py`, 10 repeticiones).
- **Resultado obtenido:** en 6 de 10 las dos responden 200 y quedan dos `warehouse.release_authorized` en la auditoría.
- **Resultado esperado:** una pasa y la otra recibe 409.
- **Impacto:** hoy bajo, porque la entrega doble sí está protegida (BOD-016) y la autorización no mueve existencias. Pero el mismo patrón (leer el estado, decidir y escribir sin bloqueo) puede repetirse en acciones de dinero.
- **Corrección propuesta:** `SELECT … FOR UPDATE` de la orden, o un `UPDATE … WHERE status = 'por_autorizar'` que verifique cuántas filas cambió. Revisar el mismo patrón en aprobar expediente, confirmar acta y radicar o pagar cobros.

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
