# Bodega — Cierre del módulo contra lo que pidió el cliente — Plan

> **Para agentes:** se ejecuta en la sesión, fase por fase (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Que el módulo de bodega cumpla los 4 pedidos del dueño y el cuestionario respondido, y quede listo para cargar el catálogo real de AC Pro (~600 productos).

**Fuentes:** `docs/bodega/cuestionario-control-bodega (1).xlsx` (respuestas), `docs/bodega/partes.pdf` (kit «3 ton desde cero»), `docs/bodega/bodega.pdf` (material frecuente de AC Pro), pedido del dueño por WhatsApp (puntos 1 a 4), validación del 24 oct (artefacto, historial).

**Dueño del paquete:** `warehouse` es de Mateo (Cadena B). Nada se toca antes de la fase 0.

## Estado de partida (24 oct)

| Pedido | Estado | Qué falta |
|---|---|---|
| 1. Orden de salida autorizada electrónicamente | Cumple | — |
| 2. Lista base que el técnico use como checklist, con cantidades, calibres y extras editables | A medias | La lista no viaja como checklist; selectores cortados en 200 sin buscador |
| 3. Presupuesto por proyecto y comparación con lo real; comprar por adelantado | Cumple | Compras sugeridas no descuenta lo ya entregado |
| 4. Seguimiento día a día de obras de varios días con técnicos distintos | A medias | El diario es lista de lo que pasó; no hay calendario ni planeación por día |
| Cuestionario | Casi todo | Conteo mensual sin recordatorio; categorías fijas; una sola referencia por artículo |

Retirado el 24 oct: «renglones fuera de catálogo». El pedido decía «fuera de lo normal» (fuera de la lista base), no fuera de bodega; ya se cubre con «Agregar renglón», y lo que se compra directo entra por compras o gastos de la obra.

## Cierre de cada fase (obligatorio, no se salta)

- [ ] Pruebas nuevas del backend para lo que se agregó (incluido el permiso de cada ruta nueva y el aislamiento por organización).
- [ ] `pytest` completo en verde (desde `backend/`; en Docker ~25 min, en segundo plano).
- [ ] `npm run build` y `scripts/check_hooks.py` en verde.
- [ ] Migración (si hay) probada en ambos sentidos contra Postgres.
- [ ] QA de punta a punta: extender la sección de bodega de `backend/scripts/qa_e2e.py` con los pasos nuevos y correrlo completo.
- [ ] Recorrido en el navegador con los roles que tocan la fase (Administración, técnico y Gerencia como mínimo), a 390 px y a 1440 px, sin errores de consola ni de la API.
- [ ] Verificar la funcionalidad contra el pedido del cliente (la frase exacta), no solo contra el código.
- [ ] Manual de usuario (`docs/Manual_Usuario_CRM_Delta_HVAC.docx`): actualizar la sección de bodega con texto y capturas nuevas.
- [ ] Commit en `devjj` y push. A `main` solo cuando José lo diga; el artefacto se actualiza después de integrar.

---

## Fase 0 — Avisar a Mateo (antes de tocar código)

- [x] Decidido por José (24 oct): todas las fases las hacemos nosotros, en `devjj`.
- [ ] Avisarle a Mateo que se va a tocar su paquete `warehouse` (regla del CLAUDE.md) y mandarle este plan.
- [x] `CadenaB` no tiene nada nuevo en bodega (solo un merge de main y el tsbuildinfo).

## Fase 1 — Buscador de artículos (S · 1–2 días)

El catálogo real son ~600 productos; hoy los desplegables traen solo los primeros 200 y sin búsqueda. El servidor ya busca (`GET /warehouse/items?q=`).

- [x] Componente común de búsqueda (`components/SearchPicker.tsx`) y el de artículos (`features/warehouse/ItemPicker.tsx`): escribe y consulta al servidor, 20 resultados, teclado y dedo; la lista va debajo del campo para que la tabla del celular no la recorte.
- [x] Usado en: orden de salida, listas predefinidas, presupuesto y diario de obra.
- [x] El selector de obra de la salida tenía el mismo corte (200 proyectos): ahora busca por nombre o dirección.
- [x] QA en el navegador con 230 artículos: el 201, 215, 228 y 230 se encuentran y se eligen en los cuatro lugares, a 1440 y 390 px, sin desborde ni errores. Prueba `test_el_buscador_encuentra_fuera_de_la_primera_pagina` y paso nuevo en `qa_e2e.py` (365/365; se corrigió además el paso de rentabilidad, que la pedía con Administración y no tiene `profitability.read`).
- [x] Manual: sección 12 «Bodega» con tres capturas (el manual se genera desde `docs/manual/`, que se recuperó del respaldo local).

## Fase 2 — La lista como checklist (M · 1 sem) — necesita spec corto

Pedido: «algo preestablecido que el técnico use como checklist para que no se le olviden cosas que sí o sí debe llevar».

- [ ] Al aplicar la lista, el renglón de la salida guarda su sección, si es obligatorio y de qué lista vino (migración).
- [ ] La orden se ve agrupada por sección, con «Obligatorio» marcado.
- [ ] Quitar un renglón obligatorio pide motivo (queda escrito en la orden y lo ve quien autoriza).
- [ ] En la entrega, quien entrega confirma renglón por renglón lo que sale (cantidad entregada editable, sin pasar de lo pedido).
- [ ] El técnico ve su orden entregada en el celular como lista de chequeo al cargar la camioneta.
- **Decidido (24 oct):** chequean los dos, cada uno lo suyo. Bodega confirma al entregar cuánto sale de cada renglón; el técnico marca «lo llevo» en el celular al cargar la camioneta, y esa marca es la checklist del pedido. Un obligatorio sin marcar se avisa.

## Fase 3 — Catálogo listo para AC Pro (M · 1 sem)

- [x] Categorías por organización (`warehouse_categories`, migración 0034, `warehouse/categories.py`): se siembran la primera vez con las 9 del cuestionario más termostatos, filtros, ventilación (B-Vent), PVC y drenaje, hierro negro y gas, repuestos, químicos y limpieza, y cintas y sellantes. El artículo sigue guardando el código, así que no hubo que convertir datos. Se agregan, renombran y desactivan en **Artículos › Categorías**; no se borran y «Otro» no se desactiva.
- [x] Artículo con **marca** y **número del fabricante** además del código AC Pro. El buscador encuentra por nombre, código, fabricante, marca o proveedor.
- [x] Importación con las columnas «Código AC Pro», «Número del fabricante» y «Marca». Arreglado de paso: los códigos de AC Pro son números y la fila fallaba al importarlos. Una categoría que el Excel trae y no existe se crea y se avisa (antes caía en «Otro»). La plantilla de Excel no vive en la app (se mandó al cliente el 19 oct); cuando se mande la de AC Pro, agregar esas tres columnas.
- [x] Unidad «paquetes».
- [x] El buscador no ofrece la lista anterior mientras se escribe (Enter podía elegir un artículo que no correspondía).
- [x] Pruebas: `test_el_excel_de_ac_pro_trae_codigo_fabricante_y_marca` y `test_las_categorias_las_administra_la_organizacion` (permisos y aislamiento). QA 372/372. Navegador a 390 y 1440. Manual: 12.1 con dos capturas nuevas.

## Fase 4 — Compras sugeridas y conteo (S · 2–3 días)

- [ ] Compras sugeridas descuenta lo ya entregado a cada obra con presupuesto aprobado (hoy cuenta el presupuesto completo aunque ya haya salido parte).
- [ ] Recordatorio de conteo físico mensual (respuesta 8): aviso a quien administra la bodega cuando pasan 30 días desde el último conteo, con la alerta diaria que ya existe.

## Fase 5 — Calendario de jornadas (L · 2 sem) — necesita spec y acuerdo con Mateo

Pedido: «un calendario donde se vea qué se realiza cada día… el día 1 puede ir X técnico y el día 3 otro».

- [ ] La obra tiene fecha de inicio y de fin.
- [ ] Planear de antemano cada día de la obra: técnico(s) del día y qué se va a hacer; la jornada planeada se convierte en la registrada (lo que se hizo, material, faltantes, qué llevar mañana), sin escribirlo dos veces.
- [ ] Vista de calendario de mes y semana, por obra y por técnico.
- [ ] Desde la jornada planeada, pedir la salida de material de ese día.
- [ ] **Coordinar:** esto es también la base del calendario que el cliente usa hoy en Housecall Pro (agenda en `field_ops`). Diseñarlo una sola vez para los dos usos.

## Fase 6 — Datos reales del cliente (depende del cliente)

- [ ] Catálogo de AC Pro: con el acceso que prometieron, sacar los ~600 productos y cargarlos con el importador (fase 3).
- [ ] Lista «Instalación 3 ton desde cero» con los renglones de `partes.pdf` (una vez estén en el catálogo).
- [ ] Listas de minisplit y AC central (rebate): **las debe el cliente.**
- [ ] Herramientas que sí entran al inventario (respuesta 10): **la debe el cliente.**
- [ ] Conteo inicial en bodega (respuesta 12: un fin de semana).

## Relacionado, fuera de bodega

- Respuesta 15: serial obligatorio de los equipos principales en «Equipos instalados». Hoy se exige al menos un equipo, pero el serial es opcional. Va en `field_ops` (Mateo).
- El dueño debe poder autorizar salidas: confirmar qué rol tiene Aldo (hoy autorizan Administrador y Administración; Gerencia solo lee).

## Orden sugerido

0 → 1 → 3 → 2 → 4 → 5, con la 6 en cuanto llegue lo del cliente. La 1 y la 3 van primero porque sin ellas no se puede cargar el catálogo real, y la 2 y la 5 necesitan spec antes de código.
