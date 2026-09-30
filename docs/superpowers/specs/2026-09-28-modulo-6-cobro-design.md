# Módulo 6 — Facturación y cobro

Fecha: 28 de septiembre de 2026. Autor: Mateo Mazo (Cadena B).
Base: documento del cliente (`docs/Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`
§3.4, §4 y §7), `docs/requerimientos-formularios-programas-delta-hvac.md` §12,
`docs/Especificacion_interna_programas_y_aplicaciones.md` (invoice templates),
`docs/validacion-pdf-vs-modulos.md` (G12, G14, G16), `docs/cronograma-cadena-b.md`
(módulo 6) y la sesión de definición con Mateo del 28 de septiembre.

---

## 1. Qué es esto

Cómo Delta HVAC convierte una instalación terminada en dinero. Hay dos negocios
distintos y el diseño los mantiene separados:

1. **Rebate** (el negocio principal). El cliente **no paga nada**: Delta HVAC
   instala y le cobra a uno o varios **programas**. Cada programa paga **un
   monto fijo por dirección**, haga lo que haga la instalación (hoy: TECH
   $4.000, LADWP $7.500, GoZero $3.000), y ese monto **cambia cada año**. La
   factura muestra el trabajo y los rebates, y su balance es **0 por efecto
   administrativo**: no es deuda del cliente ni ingreso.
2. **Trabajo particular**. Un cliente paga él mismo un arreglo o un trabajo:
   **cotización → ajuste → instalación → factura → pago**, como una factura
   común. Aquí sí hay balance real. Puede nacer de una casa de rebate (el
   cliente pide algo adicional) o de un cliente que llega por su cuenta.

Nunca se mezclan: numeración, plantilla y flujo distintos.

## 2. Lo que definió el negocio (28 sep)

- **Una dirección, uno o varios programas.** Aplica a un programa si está en su
  **jurisdicción vigente**: LADWP es Los Ángeles; GoZero, varias zonas
  normalmente desfavorecidas; TECH es San Fernando este año y el próximo puede
  ser otra zona. Mission Hills, por ejemplo, entra por LADWP y probablemente por
  TECH cuando abra. Cada programa se cobra con **su propia factura**, se radica
  y se paga **por separado**, el mismo día o semanas después.
- **Condiciones propias por programa.** GoZero paga el reemplazo de gas por
  eléctrico: hay que demostrarlo (en el módulo 5 ya existen la condición "se
  retira equipo de gas" y la foto "eliminación de equipo de gas").
- **La tarifa aplicable es la vigente en la fecha de la instalación**, no la de
  radicación. Se carga cuando el programa abre.
- **Un mismo programa no se cobra dos veces por la misma instalación**, pero los
  rechazos son comunes y una corrección puede tardar uno o dos meses (daños por
  arreglar): el cobro rechazado **no vence** y admite los reintentos que hagan
  falta.
- **El proceso real antes de cobrar** (en orden): documentos (beneficio y demás)
  → cliente captado → T&C firmados → aprobación del programa → instalación
  programada → instalación → información de los técnicos → información
  recibida y confirmada por Administración → factura y papeleo → cobro, **solo
  si todo está bien**. Si algo está mal, **vuelve a la obtención de información
  de los técnicos**.
- **Permiso municipal.** El protocolo es sacarlo antes de instalar; en la
  práctica **se instala y después se saca**. Toda dirección necesita permiso,
  antes o después. Con la instalación hecha se programa la **inspección**; la
  prueba es **la firma del inspector en el permiso**, y sin eso no se cobra.
  **Excepción: TECH** pidió el año pasado solo el número de permiso, sin
  inspección, y puede que este año sea igual. Por eso la inspección es un
  requisito **por programa**, activado por defecto.
- Materiales, mano de obra y costos operativos **no** son parte de lo que paga
  el programa: los maneja Contabilidad para medir rentabilidad (fuera de este
  módulo).

## 3. Decisiones

### D6.1 — Un documento de factura compartido, dos procesos separados

La **factura** (documento numerado, con líneas y PDF) es común. Encima corren
dos procesos independientes: el **cobro de rebate** y el **trabajo particular**.
Comparten numeración segura, PDF y registro de pagos; no comparten reglas.
Descartado: una tabla con un campo `tipo` (cada regla termina en un "si es
rebate…") y extender la factura actual (arrastra dinero en `float` y una factura
por proyecto).

### D6.2 — Configuración de cobro por programa, con vigencias

De la Cadena B; **apunta** a `Program` (de José) y no lo modifica (regla del
contrato del esqueleto). Por programa:

- **Tarifa de rebate con vigencia** (`desde`/`hasta`). No se solapan dos tarifas
  del mismo programa.
- **Jurisdicciones con vigencia**, por ciudad o código postal, normalizadas.
- **Requisitos de radicación** (el checklist del cobro): lista editable por
  programa, sembrada con los pasos del proceso real (§2). Cada requisito es
  **automático** (el sistema lo comprueba con datos) o **manual** (alguien lo
  confirma, queda quién y cuándo). Los automáticos salen de un catálogo en
  código (§5).
- **Datos de la factura**: entidad que factura (Delta HVAC Service Inc. o Desert
  Alliance Properties LLC, pendiente del cliente), dirección, contacto, texto
  legal, y **días esperados de pago** (umbral de alerta, 45 por defecto).

### D6.3 — Un cobro por programa y por instalación

`RebateClaim` une instalación (proyecto y expediente) con programa. Al crearse
**congela la tarifa** vigente en la fecha de instalación y el resultado de
jurisdicción (aplica / no aplica con motivo). Único por (proyecto, programa)
salvo que el anterior se haya **retirado**.

- **Elegibilidad**: el sistema **sugiere** los programas que aplican a la
  dirección en la fecha de instalación. Si no aplica, **advierte, no bloquea**:
  se puede crear con motivo (los programas a veces aceptan casos de borde).
- **Radicar** exige todos los requisitos cumplidos (regla del cliente: "no
  enviar a cobro sin checklist completo"). Guarda fecha de radicación,
  referencia del portal y quién radicó. Cada radicación es un **intento**
  (`claim_attempts`), como la inspección del módulo 5.
- **Rechazo**: motivo obligatorio y categoría (documental, técnico, otro). El
  cobro queda "rechazado, en corrección" **sin vencimiento**. Si el motivo es
  técnico, se puede **devolver el acta al técnico** (D6.6).
- **Pago**: fecha, monto y referencia (cheque o transferencia). Si llega menos
  que lo esperado, la diferencia queda registrada y visible; no se "completa"
  sola.
- **Retirar** un cobro (con motivo) libera el programa para un cobro nuevo.
- Una factura emitida **no se edita**: si hay que corregirla se emite una nueva
  que **reemplaza** a la anterior (la anterior queda anulada, con referencia).

### D6.4 — La inspección y el permiso son requisitos del programa, no del motor

Hoy (módulo 5) entrar a "En proceso de cobro" exige inspección aprobada como
regla fija. Pasa a ser un requisito del cobro de cada programa (activado por
defecto; TECH puede desactivarlo y exigir solo el número de permiso). Para
permitir el orden real (instalar antes del permiso):

- Liberar la orden e instalar **ya no exigen** permiso.
- **Agendar la inspección exige permiso radicado.**
- Registrar la inspección aprobada **exige adjuntar el permiso firmado por el
  inspector** (categoría de evidencia nueva `permit_signed`).
- Los requisitos por defecto de cada programa incluyen **permiso aprobado** e
  **inspección aprobada**.

Esto necesita dos transiciones nuevas en el mapa de José (§9).

### D6.5 — El expediente avanza por hechos de cobro

- Crear el primer cobro de una instalación la lleva a **"En proceso de cobro"**
  (sub-estado `invoice_pending`). Guarda: acta confirmada por Administración.
- Radicar → sub-estado `submitted`. Un rechazo → `rejected_by_program`.
- Con **todos** sus cobros no retirados **pagados** → **"Pagado"** (efecto
  automático; exige `invoices.record_payment`, que tiene Contabilidad).
- "Cerrado" sigue siendo de Administración (`cases.close_admin`).
- Un cobro nuevo sobre un expediente ya pagado (un programa que abrió después)
  se permite y **no** hace retroceder la etapa.
- El trabajo particular **nunca** mueve el expediente.

Mismo mecanismo que el módulo 5: `advance_case()` y guardas asíncronas.

### D6.6 — Confirmación del acta y lazo de corrección

Paso nuevo entre la instalación y el cobro, en el acta del módulo 5:
Administración (`checklists.approve`) **confirma** la información técnica o la
**devuelve al técnico con motivo**. Devolver reabre el acta (proyecto a
`scheduled`, checklist y equipos editables). El técnico corrige y la vuelve a
cerrar; queda pendiente de confirmar de nuevo.

Un rechazo del programa por motivo técnico usa el mismo lazo, con el expediente
**en su etapa de cobro**: se reabre el acta, **no** el expediente. Esto ajusta
el módulo 5: hoy cerrar el acta exige que el expediente esté en "Listo para
instalar"; pasa a admitir también un acta reabierta para corrección. Cada
confirmación y devolución queda en un historial (`project_reviews`).

### D6.7 — Trabajo particular: cotización con versiones

`Quote` cuelga del **cliente** y, opcionalmente, de una instalación. Líneas
(servicio, material, mano de obra, permiso), estado (borrador, enviada,
aceptada, rechazada, vencida) y **versiones**: un ajuste crea la versión
siguiente y la anterior queda como historial. Aceptar crea la **factura
particular** en borrador con las mismas líneas (ajustable hasta emitirla).
Pagos parciales, balance real y vencimiento (por la fecha de la organización).

### D6.8 — Dinero y numeración

- Todo el dinero en `Decimal` / `Numeric(12,2)`. Se elimina `float` del módulo:
  hoy suma pagos con `float` y puede fallar por centavos.
- Numeración **por serie, año y organización** con una tabla de secuencias
  bloqueada al asignar (hoy cuenta filas y dos facturas simultáneas pueden
  repetir número). Series: `REB-2026-0001` (factura de rebate), `FAC-2026-0001`
  (particular), `COT-2026-0001` (cotización). Las facturas existentes conservan
  su número.
- Vencimientos con la fecha de la organización (`field_ops/clock.py`). Cierra
  **COD-10**.

### D6.9 — PDF con dos plantillas y vista previa

ReportLab, como el acta firmada del módulo 5. Plantilla **rebate** (programa,
cliente, dirección, trabajo realizado, equipos del módulo 5, rebate, balance 0,
texto legal del programa) y **particular** (líneas, subtotal, pagos, balance,
términos). Los datos de la entidad y el texto legal salen de la configuración
del programa. La vista previa renderiza el mismo PDF antes de emitir.

### D6.10 — Tablero de cobros (AR)

Calculado al leer, sin estados guardados que se desincronicen:

- **Por radicar**: acta confirmada y requisitos al día, sin cobro radicado.
  Alerta desde el día siguiente (el ciclo diario del cliente).
- **Radicados esperando pago**, con días transcurridos; alerta al pasar los
  días esperados del programa.
- **Rechazados en corrección**, con días desde el rechazo.
- **Pagado este mes** y **esperado** por programa.
- Particular: facturas vencidas y por vencer.

## 4. Tablas — migración `0015_billing_module6`

- `billing_program_profiles` (programa único por organización): entidad,
  dirección, contacto, texto legal, días esperados de pago.
- `program_rebate_rates`: programa, monto, `valid_from`, `valid_to`.
- `program_jurisdictions`: programa, tipo (`city`/`zip`), valor normalizado,
  vigencia.
- `program_claim_requirements`: programa, código, etiqueta, tipo
  (`auto`/`manual`), regla automática, orden, activo.
- `rebate_claims`: expediente, proyecto, programa, tarifa congelada, fecha de
  instalación usada, estado, jurisdicción (aplica / motivo), factura vigente,
  pago (fecha, monto, referencia), motivo de retiro.
- `rebate_claim_attempts`: radicación (fecha, referencia, quién) y resultado
  (pendiente, pagado, rechazado con motivo y categoría).
- `rebate_claim_checks`: confirmaciones de requisitos manuales (quién, cuándo,
  nota).
- `invoices` **evoluciona**: `kind` (`rebate`/`particular`), `case_id`,
  `claim_id`, `quote_id`, `replaces_invoice_id`, estado de documento
  (`draft`/`issued`/`void`) con el estado de pago derivado de los pagos;
  `project_id` pasa a opcional (particular sin instalación). Estado de enum a
  texto, como `evidence.category` en la 0014.
- `invoice_lines`: tipo, descripción, código de servicio, cantidad, precio,
  importe.
- `quotes` y `quote_lines`: cliente, instalación opcional, versión, versión
  anterior, estado, vigencia.
- `document_sequences`: organización, serie, año, último número.
- `project_reviews`: proyecto, acción (`confirmed`/`returned`), motivo, quién,
  cuándo.

`downgrade()` real. Si José integra antes otra `0015`, esta se renumera.

## 5. Requisitos automáticos (catálogo en código)

| Código | Se cumple cuando |
|---|---|
| `client_captured` | El expediente tiene cliente |
| `program_approved` | Expediente aprobado y con código de aprobación |
| `installation_scheduled` | Orden liberada (técnico y fecha) |
| `installation_done` | Acta cerrada |
| `technician_info_complete` | Checklist, fotos y equipos completos |
| `technician_info_confirmed` | Administración confirmó el acta (D6.6) |
| `permit_filed` | Hay un permiso con número |
| `permit_approved` | Todos los permisos despejados |
| `inspection_passed` | Última inspección aprobada con permiso firmado |
| `gas_to_electric` | Condición "se retira equipo de gas" con su foto (GoZero) |
| `invoice_issued` | La factura del cobro está emitida |

Manuales por defecto: documentos del beneficio y del vendedor, T&C firmados
(pasan a automáticos cuando José termine los módulos 2 y 3) y papeleo propio del
programa.

## 6. Permisos

Existentes: `invoices.*`, `billing.submit` (radicar), `dashboards.finance`,
`checklists.approve` (confirmar o devolver el acta, lo tiene Administración).
Nuevos, agregados al catálogo compartido (solo líneas nuevas):

- `billing.configure` — tarifas, jurisdicciones, requisitos y datos de factura
  por programa. Administrador y Contabilidad.
- `quotes.manage` — cotizaciones de trabajo particular. Administrador,
  Administración y Contabilidad.

## 7. API nueva (resumen)

- Configuración: `GET/PUT /billing/programs/{id}/profile`, CRUD de
  `/rates`, `/jurisdictions`, `/requirements`.
- Elegibilidad: `GET /projects/{id}/billing/eligibility`.
- Cobros: `POST /projects/{id}/claims`, `GET /claims`, `GET /claims/{id}`
  (con checklist evaluado), `POST /claims/{id}/checks/{code}`,
  `POST /claims/{id}/submit`, `/reject`, `/payment`, `/withdraw`,
  `POST /claims/{id}/invoice/reissue`.
- Acta: `POST /projects/{id}/review/confirm`, `POST /projects/{id}/review/return`.
- Particular: CRUD de `/billing/quotes` (no `/quotes`: era del CRM retirado,
  COD-01), `POST /billing/quotes/{id}/revise`, `/accept`, `/reject`, `/send`;
  borrador de factura: `PUT /invoices/{id}/lines`, `POST /invoices/{id}/issue`;
  facturas particulares sobre `/invoices` (emitir, anular, pagos).
- PDF: `GET /invoices/{id}/pdf`, `POST /invoices/preview`.
- Tablero: `GET /billing/dashboard`.

## 8. Pantallas

- Paso 7 **"Cobro"** en el acta de instalación: programas que aplican, cobros y
  su estado, crear cobro. Paso nuevo **"Confirmación"** antes de la inspección
  (confirmar o devolver al técnico).
- **Bandeja de cobros** (reemplaza la pantalla actual de facturación): por
  radicar, radicados, rechazados, pagados; con alertas por días.
- **Detalle del cobro**: checklist con los automáticos marcados solos y los
  manuales para confirmar, factura con vista previa, radicar, registrar pago o
  rechazo, intentos anteriores.
- **Cotizaciones y facturas particulares.**
- **Configuración de cobro por programa**: tarifas por año, jurisdicciones,
  requisitos y datos de factura.

Misma línea visual del acta (tarjetas, chips de estado, botones rojos).

## 9. Lo que toca fuera de la Cadena B — pedido a José

Dos transiciones nuevas en `cases/stages.py`, solo agregadas:

1. **`approved → ready_to_install`**: instalar antes de tener el permiso, como
   se trabaja en la práctica. Permiso requerido: el de liberar la orden
   (`dispatch.manage`). El camino por "Permiso en trámite" sigue igual.
2. **`installed → billing_in_progress`**: cobrar a un programa que no exige
   inspección (TECH) sin pasar por "Inspección pendiente".

Sin esos cambios el módulo funciona, pero obliga a sacar el permiso antes de
instalar y a pasar por inspección siempre.

## 10. Qué NO entra

- Costos de materiales, mano de obra y operación; rentabilidad por proyecto.
- Proveedores y cuentas por pagar; conciliación bancaria; exportación contable
  (se conserva el CSV actual).
- Envío de correos o SMS por cada evento (módulo 7; aquí solo se emiten).
- Integración con los portales de los programas: la radicación se registra a
  mano.
- Autollenado de formularios municipales de permiso.

## 11. Pendientes del cliente (no bloquean; quedan configurables)

- Entidad que factura en cada programa (Delta HVAC o Desert Alliance).
- Requisitos exactos de radicación de cada programa y si TECH vuelve a pedir
  inspección este año.
- Tarifas y jurisdicciones de cada programa cuando abran.
- Días esperados de pago por programa (umbral de alerta).

## 12. Pruebas

TDD en todo. Por cada regla, el caso que pasa, el que se bloquea y el mensaje.

- Tarifa: la vigente en la fecha de instalación; solapamiento rechazado; un
  cambio de tarifa no altera cobros existentes.
- Jurisdicción: sugiere los que aplican; el que no aplica exige motivo.
- No se crea un segundo cobro del mismo programa salvo retirado.
- Radicar con un requisito pendiente → 400 con la lista de lo que falta.
- Rechazo → corrección → nuevo intento; los intentos se conservan.
- Pago parcial deja la diferencia visible.
- Expediente: entra a cobro con el primer cobro; pasa a pagado cuando todos
  están pagados; un cobro nuevo no lo hace retroceder.
- Acta: devolver reabre; volver a cerrar en etapa de cobro funciona.
- Permiso después de instalar; inspección sin permiso radicado → 409;
  inspección aprobada sin permiso firmado → 400.
- Numeración sin repetidos por serie y año; dinero sin error de centavos.
- Cotización: versión nueva conserva la anterior; aceptar crea la factura.
- Aislamiento por organización y permisos por rol en cada ruta nueva.
- Recorrido de punta a punta contra la app real, como en el módulo 5.
