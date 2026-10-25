# Ataque a bodega-cierre y rotación del técnico · 24 oct 2026

**Qué se atacó:** lo que José integró a `main` el 24 oct (commits 480f173, 5c7b9a8, 72bc0ca, 9dec10e, 64566fa y 2232564; `main` en 2232564). El objetivo era romperlo, no confirmar que funciona.

**Contra qué:**
- **App real:** Docker, Postgres y migraciones hasta la 0036.
- **Usuarios:** los 6 roles de Demo, un segundo técnico (`tecnico2@demo-org.com`) y una segunda organización («Atacante SA», con `admin@atacante.com` y `tecnico@atacante.com`).
- **Navegador:** Chrome a 1440 y a 390 px.

**Cómo se repite:** `cd backend && PYTHONPATH=. .venv/bin/python -m scripts.qa_ataque`. El script crea sus propias obras y anota cada hallazgo y cada control que aguantó.

## Resumen

| | Antes de arreglar | Después de arreglar |
|---|---|---|
| Fallas encontradas por el script | 37 | 16 |
| Controles que aguantaron | 149 | 170 |

Agrupados por causa son **23 hallazgos**: ninguno crítico, 4 altos, 10 medios y 9 bajos.

**Lo alto ya está arreglado** en `CadenaB`, cada uno con su prueba de regresión en `backend/tests/test_bodega_ataque.py`. Lo medio y lo bajo queda listado abajo para decidirlo con José.

**Lo que aguantó todo lo que se intentó:**
- El aislamiento entre organizaciones: ninguna ruta nueva dejó ver ni tocar nada de Demo desde «Atacante SA».
- Los permisos de cada ruta nueva con los 6 roles: categorías, calendario, ayudantes, historial de responsables, «Lo llevo» y compras sugeridas.
- La separación de funciones al autorizar, incluida la salida pedida desde la obra a nombre del técnico.
- La concurrencia al entregar: tres entregas a la vez de la misma orden descuentan una sola vez.
- Las migraciones 0034 a 0036 de bajada y subida con datos.
- El calendario: rangos, fechas invertidas y técnico pidiendo lo de otro.
- Compras sugeridas con entrega de más, devolución y presupuesto reemplazado.
- El buscador con comillas e inyección SQL.

## Alto · arreglado

### A1 · Un número raro tumbaba el servidor (500) en toda bodega
- **Reproducir:** `POST /warehouse/releases` con `quantity` igual a `NaN`, `abc`, `Infinity`, `1e309`, `99999999999999999` o `1,5`. Lo mismo al entregar (`/deliver` con `lines[].quantity`), en movimientos, costo del artículo, conteo, listas, presupuesto, material del diario, cobro adicional y costo anotado.
- **Esperado:** 400 con un mensaje que se entienda.
- **Pasaba:** 500. Cada módulo hacía `Decimal(str(valor))` sin validar, y un número enorme reventaba en la columna de Postgres.
- **Dónde:** `_q` en `warehouse/{releases,service,kits,budgets,day_logs}.py` y `billing/money.py:to_money`.
- **Arreglo:** una conversión común en `app/shared/decimals.py`. Lo que no es un número finito que quepa en su columna responde 400 `invalid_number`. Las cantidades admiten hasta 99.999.999,99 y el dinero hasta 9.999.999.999,99. Por estos dos archivos pasan todos los `_q` de bodega y `to_money`.
- **Pruebas:** `test_cantidad_rara_en_la_salida_da_400`, `test_numero_raro_en_movimiento_costo_y_cobro_da_400` y `test_entregar_con_cantidad_rara_da_400`.
- **Decisión:** las cantidades redondean ahora como el dinero (0,005 sube; antes iba al par más cercano). La diferencia solo aparece en el tercer decimal.

### A2 · Dos productos de AC Pro con el mismo nombre se fundían en uno
- **Reproducir:** importar las dos «Foam Insulation Tape Black 1/8" x 2" x 30'» del PDF del cliente (`docs/bodega/bodega.pdf`): Armacell, AC Pro 36140, y Diversitech, AC Pro 3088.
- **Esperado:** dos artículos, uno por código.
- **Pasaba:** un solo artículo. El segundo se encontraba por el nombre y le pisaba el código y la marca al primero, así que el 36140 desaparecía del catálogo.
- **Dónde:** `warehouse/service.py:_find_item`.
- **Arreglo:** por nombre solo se busca un artículo que **no tenga código**. Así un catálogo cargado antes sin códigos los recibe en la carga siguiente, y dos códigos distintos son dos artículos. Si hay varios con el mismo nombre ya no revienta: toma el más viejo.
- **Pruebas:** `test_mismo_nombre_y_distinto_codigo_ac_pro_son_dos_articulos` y `test_el_codigo_nuevo_se_le_pone_al_articulo_que_no_tenia`.

### A3 · El técnico anterior enviaba a autorizar material para la obra rotada
- **Reproducir:**
  1. Obra liberada a T1; T1 arma un borrador de salida para ella.
  2. Se rota la obra a T2.
  3. T1 hace `POST /warehouse/releases/{id}/submit`.
- **Esperado:** 403 `project_read_only`, como el resto de las escrituras del técnico anterior.
- **Pasaba:** 200. Quedaba una orden «Por autorizar» para una obra que ya no es suya. Crear y editar la orden sí estaban cerrados; el envío no.
- **Dónde:** `warehouse/releases.py:submit_order`.
- **Arreglo:** el envío vuelve a validar la obra con `get_workable_project` (función `_check_project`).
- **Prueba:** `test_el_tecnico_anterior_no_envia_a_autorizar_su_borrador_de_la_obra`.

### A4 · Se pedía material para una obra cerrada
- **Reproducir:** con una obra en `completed`, el técnico responsable (o la oficina) hace `POST /warehouse/releases` con esa obra, o envía un borrador viejo de ella.
- **Esperado:** rechazo; ese material iría a un costo que ya nadie revisa.
- **Pasaba:** 201 y 200.
- **Dónde:** `warehouse/releases.py:_check_refs` y `submit_order`.
- **Arreglo:** 409 `project_closed` al crear, editar o enviar una salida para una obra cerrada o cancelada.
- **Prueba:** `test_no_se_pide_material_para_una_obra_cerrada`.

## Medio · para decidir con José

### M1 · El técnico anterior carga gastos a la obra rotada
- **Reproducir:** rotar la obra de T1 a T2; T1 hace `POST /expenses` con `project_id` de esa obra.
- **Esperado:** depende. Hoy el gasto se cargaría a la obra sin restricción.
- **Pasa:** 201.
- **Dónde:** `finance/expenses.py:46` (`_check_project` usa `get_visible_project`).
- **Por qué no se cerró:** un gasto real del turno de T1 (la gasolina de ayer) es legítimo.
- **Propuesta:** aceptarlo solo si `expense_date` cae dentro del turno de T1 en el historial de responsables.

### M2 · El técnico anterior marca «Lo llevo» en una salida de la obra rotada
- **Reproducir:** T1 tiene una salida entregada para la obra; se rota a T2; T1 hace `POST /warehouse/releases/{id}/lines/{line}/load`.
- **Pasa:** 200.
- **Dónde:** `warehouse/releases.py:434` (`mark_loaded` revisa el dueño de la orden, no la obra).
- **A decidir:** el material ya salió a su nombre y puede que sí lo haya cargado. Se puede dejar así o pedir que lo marque el responsable de hoy.

### M3 · Rotar con fecha futura quita la obra hoy, pero el historial dice que el anterior sigue
- **Reproducir:** obra de T1; Orden liberada a T2 para dentro de 10 días.
- **Pasa:** T1 queda en solo lectura desde ya, porque el acceso sale de `primary_technician_user_id`, que cambia al instante. Mientras tanto, el historial muestra el turno de T1 hasta dentro de 10 días.
- **Dónde:** `field_ops/installation.py:211` y `:169`.
- **Propuesta:** decidir uno de los dos caminos y que el acceso y el historial digan lo mismo:
  - el cambio se aplica el día que empieza, o
  - el turno del anterior se cierra hoy.

### M4 · Una obra creada con técnico se salta el historial y acepta técnicos ajenos
- **Reproducir:** `POST /projects` con `primary_technician_user_id`.
  - Con el id de un técnico de otra organización: 201, y lo guarda.
  - Con T1 y después rotando a T2: T1 pierde la obra del todo (404), porque nunca tuvo turno registrado.
- **Dónde:** `field_ops/service.py:80` y `field_ops/schemas.py:42`.
- **Propuesta:** validar que el técnico sea un instalador activo de la organización y registrar su turno, o quitar el campo y obligar a usar la Orden liberada.

### M5 · Obra cerrada: el técnico todavía registra jornada y anota cobro adicional
- **Reproducir:** con la obra en `completed`, el responsable hace `POST /warehouse/projects/{id}/day-logs` y `POST /warehouse/projects/{id}/extra-charges`.
- **Pasa:** 201 en las dos. La evidencia sí se rechaza (400).
- **Dónde:** `field_ops/access.py:49` (`can_work` no mira el estado), `warehouse/day_logs.py:256` y `warehouse/jobcost.py:461`.
- **A decidir:** el cobro adicional puede llegar después del cierre. La jornada después del cierre parece un error.

### M6 · Crear la misma categoría a la vez da 500
- **Reproducir:** tres `POST /warehouse/categories` iguales al mismo tiempo.
- **Pasa:** respuestas 201, 409 y 500. El índice único lo atrapa la base, no el código.
- **Dónde:** `warehouse/categories.py:71`.
- **Arreglo propuesto:** atrapar `IntegrityError` y responder 409.

### M7 · Una fila que falla deja una categoría fantasma para las siguientes
- **Reproducir:** importar dos filas con la misma categoría nueva, la primera con costo «abc».
- **Pasa:** el savepoint deshace la categoría, pero queda en la memoria de la carga. La segunda fila guarda el artículo con un código de categoría que no existe.
- **Dónde:** `warehouse/service.py:514`.
- **Arreglo propuesto:** agregar la categoría a la memoria solo después de que la fila termina bien, o volver a leerla tras un error.

### M8 · Buscar con un byte nulo da 500
- **Reproducir:** `GET /warehouse/items?q=%00`.
- **Pasa:** 500, porque Postgres rechaza el carácter.
- **Dónde:** `warehouse/service.py:119` (`items_stmt`).
- **Arreglo propuesto:** quitar `\x00` del texto de búsqueda. Solo se llega con una URL fabricada.

### M9 · «Pedir material» con una obra que no existe abre la salida sin obra y sin avisar
- **Reproducir:** abrir `/warehouse/releases?nueva=1&obra=<uuid inventado>` (o `obra=basura`).
- **Pasa:** la consulta de la obra da 404 o 422 y el formulario queda «vacío = uso interno». La salida se guardaría sin cargarse a ninguna obra.
- **Dónde:** `frontend/src/features/warehouse/WarehouseReleasesPage.tsx:64` y `:436`.
- **Propuesta:** si la obra pedida no se puede abrir, avisar y no dejar guardar como uso interno.

### M10 · Bajar la migración 0036 borra el historial de rotaciones
- **Pasa:** al bajar y volver a subir, el historial se rehace solo con el técnico actual de cada obra (85 turnos quedaron en 69), y los técnicos anteriores pierden su acceso de solo lectura. Bajar la 0034 borra las categorías propias y la marca y el número del fabricante.
- **A decidir:** es esperable en una reversión, pero el procedimiento debería advertirlo.

## Bajo · para decidir con José

| ID | Hallazgo | Dónde |
|---|---|---|
| B1 | Se crean categorías que solo difieren en una tilde («Filtros» y «Fíltros»). | `warehouse/categories.py:71` |
| B2 | Renombrar una categoría a «%» o con «_» choca con otras: `ilike` sin escapar los comodines. | `warehouse/categories.py:113` |
| B3 | Buscar «%» o «_» trae todo el catálogo (28 resultados con ese comodín), y «códo» no encuentra «Codo». | `warehouse/service.py:119` |
| B4 | En el Excel, un proveedor o unas notas numéricas hacen fallar la fila (`'int' object has no attribute 'strip'`). | `warehouse/service.py:532` |
| B5 | Se puede poner de ayudante a cualquier usuario activo (un vendedor, un contador). La lista de ayudantes trae al Administrador. | `warehouse/day_logs.py:231`, `warehouse/router.py:912` |
| B6 | Quien pidió la salida puede «rechazarla» él mismo, como si fuera el autorizador. Retirarla sí tiene sentido; rechazarla, no. | `warehouse/releases.py:307` |
| B7 | La bandeja de Salidas muestra «Autorizar» en todas las órdenes por autorizar, también en las que la API rechaza a quien mira (las que pidió o tiene a su nombre). El panel de la obra solo revisa quién la pidió, no a nombre de quién está. Al tocarlo sale el error 403. | `WarehouseReleasesPage.tsx:257`, `MaterialsPanel.tsx:119` |
| B8 | El técnico anterior ve «Solo lectura», pero «Agregar tarea», «Empezar» y «Comentarios» siguen activos. La API los rechaza (403). | `field-ops/ProjectDetailPage.tsx` (tareas) |
| B9 | La obra que no existe en `?obra=` deja errores 404/422 en la consola del navegador (va con M9). | `WarehouseReleasesPage.tsx:436` |

## Verificación

- `pytest` completo: 689 pruebas en verde (672 de antes y 17 nuevas), cobertura 90,04%.
- Pruebas nuevas: `tests/test_bodega_ataque.py`.
- Frontend: `npm run build` y `scripts/check_hooks.py` en verde. El frontend no cambió en este arreglo.
- Ataque repetido contra la app real después de arreglar: de 37 fallas a 16. Las 4 altas ya no aparecen; lo que queda es lo medio y lo bajo de este informe.
- Manual: sección 12, dos frases (cómo se reconoce un artículo al importar, y que no se pide material para una obra cerrada o rotada). `docs/Manual_Usuario_CRM_Delta_HVAC.docx` regenerado.
