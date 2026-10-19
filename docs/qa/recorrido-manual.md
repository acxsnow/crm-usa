# Recorrido manual completo: de la configuración al pago

Guía para probar a mano todo el flujo de Delta HVAC, paso por paso. En cada paso dice:

- **PDF:** la sección del documento del cliente (`docs/Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`) que se está cubriendo.
- **Quién:** el usuario con el que hay que entrar.
- **Pantalla:** dónde está en el menú, la ruta y el componente del frontend que la pinta.
- **API:** los endpoints del backend que se llaman (todos bajo `/api/v1`).
- **Qué probar** y **qué debe pasar**, incluido lo que **no** se debe poder hacer.

El hilo conductor es **un solo expediente** (la venta), que va pasando de rol en rol hasta quedar pagado.

---

## Antes de empezar

**Servicios:** `docker compose up` (API en `localhost:8000`, app en `localhost:5173`).

**Base al día:** desde el 13 de octubre (módulos de finanzas) hace falta la migración `0025`. Córrela una vez: `docker compose exec api alembic upgrade head`. Sin ella, las pantallas de Gastos, Proveedores, Conciliación y Reportes fallan y nadie tiene el permiso de aprobar facturas de proveedor (`payables.approve`). Si al hacer `git pull` desaparecieron `backend/.env` o `frontend/.env` (ya no se suben al repositorio), créalos de nuevo desde los `.env.example`.

**Usuarios** (contraseña `ChangeMe123!`):

| Rol | Usuario |
|---|---|
| Administrador | `admin@demo-org.com` |
| Vendedor | `vendedor@demo-org.com` |
| Administración | `administracion@demo-org.com` |
| Técnico | `tecnico@demo-org.com` |
| Contabilidad | `contabilidad@demo-org.com` |
| Gerencia | `gerencia@demo-org.com` |

**Varios roles a la vez:** la sesión vive en el navegador. Para tener dos roles abiertos al mismo tiempo, usa ventanas de incógnito o perfiles distintos de Chrome; en la misma ventana, al entrar con otro usuario se cierra la sesión anterior.

**Ver las APIs:** abre las herramientas del navegador (F12) → pestaña **Network** → filtra por `api/v1`. Cada acción de esta guía debe aparecer ahí con el endpoint que se indica. En desarrollo, la documentación interactiva de la API está en `http://localhost:8000/docs`.

**Si te bloquea el ingreso** por muchos intentos (sale «Invalid email or password.» aunque la clave esté bien, hallazgo QA-REG-05), espera 15 minutos o limpia los intentos:
`docker compose exec redis sh -c 'redis-cli --scan --pattern "ratelimit:*" | xargs -r redis-cli del'`

**Celular:** el técnico y el vendedor trabajan desde el teléfono. Puedes abrir la app desde un celular en la misma red con la IP del computador (`http://<ip>:5173`). El GPS del navegador solo funciona en `localhost` o con HTTPS, así que desde el celular por IP no habrá GPS.

## Mapa del recorrido

| Fase | Quién | PDF | Etapa del expediente al terminar |
|---|---|---|---|
| 0. Configurar el programa | Administrador / Administración | §2 y §3 (funcionalidades), §4.2 | — |
| 1. Venta en la puerta | Vendedor | §2 completo | Pendiente de aprobación |
| 2. Revisión y aprobación | Administración | §3.1 | Aprobado (nace el proyecto) |
| 3. Permiso, despacho e instalación | Administración y Técnico | §3.2, §3.3, §5 | Instalado |
| 4. Confirmación del acta e inspección | Administración | §3.4, §3.5 | Inspección pendiente |
| 5. Cobro y pago | Administración y Contabilidad | §3.4, §4.2, §4.3 | Pagado → Cerrado |
| 6. Lo transversal | Todos | §3 (notificaciones), §4.2, §7 | — |
| 7. Gastos de campo | Técnico, Vendedor, Contabilidad | §4.1 | — |
| 8. Proveedores y pagos | Contabilidad, Gerencia, Administrador | §4.4 | — |
| 9. Conciliación y rentabilidad | Contabilidad | §4.5 | — |
| 10. Reportes | Gerencia, Contabilidad, Administración | §7 | — |

---

## Fase 0. Configurar el programa

> Módulo 1 del plan. El programa define qué formulario llena el vendedor, qué términos firma el cliente, en qué zonas se vende y cuánto se cobra.

### 0.1 Crear el programa

- **PDF:** §2.2 («Filtro de programas»), §3 funcionalidades.
- **Quién:** Administrador (o Administración, que desde el 8 de octubre también puede).
- **Pantalla:** Administración → **Configuración de programas** (`/programs`) · `features/programs/ProgramsPage.tsx`.
- **Qué hacer:** **+ Nuevo programa** → código (por ejemplo `QA_MANUAL`) y nombre → **Crear programa**. Luego, en la sección **Identidad frente al cliente → Editar**, llena:
  - **Nombre que ve el cliente:** el que aparece al vendedor y en lo que firma el cliente.
  - **Funder:** la entidad que financia el incentivo (por ejemplo, Desert Alliance Properties LLC).
  - **Entidad que factura:** la empresa que sale en la factura del cobro; puede ser distinta del funder.
  - **Logo (URL)**, si lo tienen.
- **API:** `POST /programs`, `PATCH /programs/{id}` · lista: `GET /programs`.
- **Qué debe pasar:** aparece en la lista de la izquierda. El código no se puede repetir y **es lo único que no se cambia** después de creado; todo lo demás se edita.
- **Atajo:** si prefieres partir de una plantilla, los programas de Arizona y TECH ya vienen cargados (`POST /programs/install-defaults`).

### 0.2 Términos y condiciones

- **PDF:** §2.5 («Aviso de privacidad», «Consentimiento del cliente»).
- **Pantalla:** el programa → sección de términos → **+ Nuevos términos** → texto, idioma, versión → **Guardar borrador** → **Publicar**.
- **API:** `POST /programs/{id}/terms`, `PATCH /program-terms/{id}`, `POST /program-terms/{id}/publish`.
- **Qué debe pasar:** una vez publicados, los términos **no se editan**: para cambiarlos se crea una versión nueva. Prueba editar uno publicado: no debe dejar.

### 0.3 Catálogo de campos

- **PDF:** §2.3, §2.4 (los datos que captura el vendedor), §6 (matriz de validación).
- **Pantalla:** pestaña **Catálogo de campos** (`/programs?tab=fields`) · `features/programs/FieldsCatalog.tsx`.
- **Qué hacer:** revisa los 51 campos. Crea uno nuevo con **Nuevo campo** (por ejemplo, de tipo selección con opciones).
- **API:** `GET /fields`, `POST /fields`, `PATCH /fields/{id}`.
- **Qué debe pasar:** la clave y el tipo no cambian después de creado; una opción ya usada no se puede quitar; para «borrar», se desactiva.

### 0.4 El formulario del programa (versión)

- **PDF:** §2 funcionalidades («Cuestionario dinámico de elegibilidad», «Checklist de auditoría técnica»), §6.
- **Pantalla:** el programa → **+ Nueva versión** → editor (`/programs/versions/{id}`) · `features/programs/VersionEditorPage.tsx`.
- **Qué hacer:**
  1. **+ Agregar paso** (por ejemplo «Cliente», «Vivienda», «Auditoría técnica», «Documentos», «Autorización»).
  2. En cada paso, **+ Agregar campo del catálogo**; marca cada uno como obligatorio, opcional o condicional.
  3. Pon una **condición**: por ejemplo, «Título de la mobile home» obligatorio solo si «Tipo de vivienda = Casa móvil».
  4. Mira la **vista previa** a la derecha y cambia respuestas para ver aparecer y desaparecer los campos condicionales.
  5. **Publicar versión**.
- **API:** `POST /programs/{id}/versions`, `POST /program-versions/{id}/phases`, `POST /workflow-phases/{id}/steps`, `POST /workflow-steps/{id}/fields`, `PATCH /workflow-step-fields/{id}`, `POST /program-versions/{id}/preview` (vista previa), `POST /program-versions/{id}/publish`.
- **Qué debe pasar:** una versión publicada queda **congelada**; los expedientes guardan con qué versión se llenaron. Una versión nueva copia la anterior.

### 0.5 Zona de venta y vendedor

- **PDF:** §2.1 («zonas asignadas»), §2 funcionalidades («asignación de zonas»).
- **Pantalla:** el programa → **+ Agregar zona** → nombre, estado, ciudad → **Guardar zona** → asignar el vendedor.
- **API:** `POST /programs/{id}/zones`, `PUT /zones/{id}/salespeople`, y lo que ve el vendedor: `GET /me/programs`.
- **Qué debe pasar:** el vendedor ve el programa en **Mi día**. Prueba asignar al técnico: debe rechazarlo (no vende). Sin zona, el vendedor igual puede elegir el programa (ve todos los publicados).

### 0.6 Configuración de cobro del programa

- **PDF:** §3 funcionalidades («Módulo de facturación y cierre de cobros»), §4.2.
- **Quién:** Contabilidad (o Administrador).
- **Pantalla:** Finanzas → **Facturación y cobros** → pestaña de configuración de programas · `features/billing/ProgramsConfigTab.tsx`.
- **Qué hacer:**
  1. **+ Nueva tarifa:** monto por instalación y vigencia desde una fecha anterior a hoy.
  2. **+ Agregar zona:** aquí «zona» es la **jurisdicción de cobro** (ciudad o ZIP). Usa el mismo ZIP de la dirección que vas a vender.
  3. Revisa los **requisitos** del checklist de radicación (por ejemplo, si el programa exige inspección).
  4. Perfil del emisor: quién factura, dirección, días de pago esperados.
- **API:** `GET/POST /billing/programs/{id}/rates`, `GET/POST /billing/programs/{id}/jurisdictions`, `GET/POST /billing/programs/{id}/requirements`, `PATCH /billing/programs/requirements/{id}`, `GET/PUT /billing/programs/{id}/profile`.
- **Ojo (hallazgo QA-REG-06):** si te saltas la tarifa o la jurisdicción, todo el flujo funciona hasta la instalación y el cobro se bloquea al final.

### 0.7 Plantilla del checklist de instalación (opcional)

- **PDF:** §5.5, §5 funcionalidades («Smart Gatekeeping»), §6.
- **Pantalla:** Operación de campo → **Checklists de instalación** (`/checklists`) · `features/field-ops/ChecklistTemplatesPage.tsx`.
- **API:** `/checklist-templates`.

---

## Fase 1. La venta en la puerta (Vendedor)

> Módulo 2. Entra como `vendedor@demo-org.com`. Si puedes, hazlo desde el celular.

### 1.1 Mi día

- **PDF:** §2.1.
- **Pantalla:** **Mi día** (`/sales`) · `features/sales/SalesHomePage.tsx`.
- **API:** `GET /me/programs`, `GET /me/program-options`.
- **Qué debe pasar:** ves tus programas y zonas, y lo pendiente.

### 1.2 Tocar una puerta

- **PDF:** §2.1 («registro geolocalizado de visitas»).
- **Pantalla:** **+ Tocar una puerta** (`/sales/visit`) · `features/sales/VisitPage.tsx`.
- **Qué hacer:** dirección (usa el ZIP de la jurisdicción de cobro del paso 0.6), unidad, programa y resultado.
- **API:** `GET /visits/results`, `POST /visits`, historial: `GET /cases/{id}/visits`.
- **Prueba también:**
  - **«No abrió»** en otra dirección: el expediente queda en «Sin contacto» y nunca pide datos del cliente.
  - **La misma dirección escrita distinto** (minúsculas, con punto): debe **reabrir** el mismo expediente, no crear otro.

### 1.3 Elegir el programa (si no lo eligió al tocar)

- **API:** `PUT /cases/{id}/program`.
- **Qué debe pasar:** una vez guardadas respuestas, el programa ya no se cambia.

### 1.4 El formulario por pasos

- **PDF:** §2.2, §2.3, §2.4, §2.6, §6 (validaciones de ventas).
- **Pantalla:** el expediente (`/cases/{id}/form`) · `features/sales/CaseFormPage.tsx` y `features/programs/FormRenderer.tsx`.
- **Qué hacer:** llena paso por paso con **Guardar y seguir**. Sube fotos (ID, panel, furnace…) y un PDF.
- **API:** `GET /cases/{id}/form`, `PUT /cases/{id}/steps/{código}`, `POST /cases/{id}/files`, evaluación en vivo: `POST /program-versions/{id}/preview`.
- **Prueba también:**
  - **Un campo condicional:** marca «Casa móvil» y deben aparecer título y decal.
  - **Un archivo disfrazado:** renombra un `.exe` o `.txt` a `.jpg` y súbelo; debe rechazarlo.
  - **Un archivo muy grande:** debe rechazarlo con un mensaje entendible.
  - **La marca de agua:** las fotos quedan con GPS y fecha.
  - **Sin señal:** apaga el wifi a mitad de un paso; debe avisar y no perder lo escrito.

### 1.5 Términos y firma del cliente

- **PDF:** §2.5, §2 funcionalidades («Módulo de firma digital»).
- **Pantalla:** último paso del formulario: el cliente lee los términos, escribe su nombre y firma en pantalla.
- **API:** `POST /cases/{id}/terms-acceptance`, ver la firma: `GET /cases/{id}/terms-acceptance/signature`.
- **Qué debe pasar:** queda un registro inmutable con versión de términos, fecha, GPS e IP. **Repetir la firma** reemplaza la anterior antes de enviar.

### 1.6 Enviar a revisión

- **PDF:** §2.6 («Transferencia»), §7 etapa 4.
- **Pantalla:** **Enviar a revisión**.
- **API:** `POST /cases/{id}/submit`.
- **Qué debe pasar:** el expediente pasa a **Pendiente de aprobación · En revisión** y ya no se puede editar.
- **Lo que NO debe poder hacer el vendedor:**
  - Enviar con campos obligatorios vacíos.
  - Aprobar su propio expediente: no hay botón, y si se llama a la API (`POST /cases/{id}/transition` con `approved`) responde **403**.
  - Ver los expedientes de otro vendedor, ni escribiendo la dirección.
  - Entrar a Proyectos, Facturación, Programas, Equipo: escribiendo la dirección a mano debe devolverlo al **Inicio** (desde el 11 de octubre ya no sale «No tienes acceso»). Una dirección que no existe también lleva al Inicio.

---

## Fase 2. Revisión y aprobación (Administración)

> Módulos 3 y 4. Entra como `administracion@demo-org.com`.

### 2.1 Tablero y cola de documentos

- **PDF:** §3 funcionalidades («Dashboard centralizado… Kanban»), §3.1.
- **Pantallas:**
  - **Expedientes** (`/cases`) · `features/sales/CasesBoardPage.tsx` · API `GET /case-board`.
  - **Documentos por revisar** (`/documents`) · `features/sales/DocumentsQueuePage.tsx` · API `GET /documents/review-queue`.
- **Qué debe pasar:** tu expediente aparece en «Pendiente de aprobación» con el contador de días (PDF §3.1 y §7, «con contador de días»): **⏱ N días hábiles** desde que se envió a revisión, en la tarjeta del tablero, en la fila de la cola y bajo «Enviado» en la revisión. Gris mientras está a tiempo; en rojo y con «· límite L» desde el límite. La cola ordena del más antiguo al más nuevo, así que los rojos quedan arriba. Una devolución al vendedor no reinicia la cuenta.
- **El límite y la alerta:** Notificaciones → **Alertas** (Administrador y Administración). Cambia «días hábiles en Pendiente de aprobación» (por defecto 3): el color del contador cambia al recargar. La alerta a la campana («Lleva N días hábiles sin aprobar») sale en la revisión diaria de las 14:00 UTC o al tocar **Revisar ahora**, que dice cuántos avisos creó. Tocarlo otra vez el mismo día dice «No había nada nuevo para avisar»: no repite avisos. API: `POST /notifications/alerts/run`.

### 2.2 Revisar documento por documento

- **PDF:** §3.1 («Recepción de expedientes», «Preparación documental»).
- **Pantalla:** el expediente → revisión (`/cases/{id}/review`) · `features/sales/CaseReviewPage.tsx`.
- **Qué hacer:** **✓ Aceptar** cada documento o rechazarlo con una nota. Agrega un documento adicional (**+ Agregar documento**).
- **API:** `GET /cases/{id}/documents`, `POST /case-files/{id}/review`, `POST /cases/{id}/documents`.
- **Qué debe pasar:** ves las respuestas sensibles (programa de beneficio, discapacidad) y los archivos sensibles (foto del ID). Gerencia, en cambio, ve «•••».

### 2.3 Devolver al vendedor

- **Qué hacer:** **Devolver al vendedor** con un motivo. Vuelve con el vendedor (fase 1.4), corrige y reenvía (1.6).
- **API:** `POST /cases/{id}/substatus` (`returned`).
- **Qué debe pasar:** la devolución **no reinicia** el contador de días: el expediente sigue en «Pendiente de aprobación». Al vendedor le llega un aviso.

### 2.4 Avance con el programa

- **PDF:** §3.1 («Radicación en plataformas de programa», «Seguimiento de tiempos»).
- **Qué hacer:** marca «Listo para el programa» → «Sometido al programa» → «En revisión del programa».
- **API:** `POST /cases/{id}/substatus`.

### 2.5 Decidir: aprobar, poner en espera o rechazar

- **PDF:** §7 etapa 5.
- **Qué hacer:** **Aprobar** con el **código de aprobación** del programa y el número de solicitud.
- **API:** `POST /cases/{id}/transition` (`approved`).
- **Qué debe pasar:** el expediente pasa a **Aprobado** y **nace el proyecto de instalación** (lo ves en el expediente, «Instalación · CASE-…», y en **Proyectos**).
- **Prueba también** (con otro expediente): **Poner en espera del programa**, **Rechazar** con motivo, y que un rechazado se pueda corregir y reenviar. **Cerrar expediente…** con motivo obligatorio.

---

## Fase 3. Permiso, despacho e instalación

> Módulo 5. El acta de instalación es una sola pantalla con pasos: `features/field-ops/ProjectDetailPage.tsx` y `components/InstallationRecord.tsx`. El expediente avanza solo, por los hechos que se registran aquí.

### 3.1 Permiso municipal (Administración)

- **PDF:** §3.2.
- **Pantalla:** **Proyectos** → el proyecto → paso **Permiso municipal** · `components/PermitsPanel.tsx`.
- **Qué hacer:** **Registrar el permiso** (ciudad o condado, número, tipo y fecha de radicado). Cada permiso queda como una tarjeta con sus pasos (Radicado → Aprobado por la ciudad). Cuando la ciudad responda: **La ciudad lo aprobó** (fecha de aprobación y, opcional, de vencimiento) o **La ciudad lo rechazó** (motivo; luego «Volver a radicar»). También existe «No requerido» con motivo.
- **API:** `POST /projects/{id}/permits`, `PATCH /permits/{id}`.
- **Qué debe pasar:** el expediente pasa a **Permiso en trámite** y, al aprobarse, a **Listo para instalar**.
- **Instalar con el permiso solo radicado** (variable `PERMIT_FILED_ALLOWS_INSTALL` en `backend/.env`, desde el 16 oct): en `false` (por defecto) hace falta la aprobación de la ciudad, como arriba. En `true` el expediente pasa a **Listo para instalar** apenas se radica, y la tarjeta dice «Radicado. Ya se puede instalar; registra la aprobación cuando la ciudad responda». En los dos casos un permiso rechazado o vencido bloquea, y el **cobro al programa sigue pidiendo el permiso aprobado**. Para probarlo: cambiar la variable, reiniciar (`docker compose restart api`) y registrar un permiso radicado en otro proyecto.

### 3.2 Liberar la orden: técnico y fecha (Administración)

- **PDF:** §3.3, §5.1, §7 etapa 7.
- **Pantalla:** paso **Orden liberada**: elegir técnico y fecha.
- **API:** `GET /dispatch/technicians` (solo quienes pueden instalar), `PATCH /projects/{id}/schedule`.
- **Qué debe pasar:** sub-estado **Instalación agendada**. Aparece en la **Agenda** del técnico (`/my-schedule` · `features/field-ops/AgendaPage.tsx`) y en el **Monitor de técnicos** (`/technician-monitor`).
- **La agenda** (desde el 16 oct) abre en **Pendientes**: arriba las **Atrasadas** (fecha pasada y sin cerrar, en rojo con los días de atraso, salen siempre), luego **Hoy** y los días siguientes hasta «Ver hasta» (por defecto dos semanas). Lo cerrado o cancelado está en **Historial**, con Desde/Hasta y páginas de a 30. Administración ve a todos y filtra por técnico; el técnico, solo lo suyo. API: `GET /dispatch/agenda?view=pending|history`.

### 3.3 La instalación (Técnico)

- **PDF:** §5.1 a §5.5, §6 (validaciones de técnicos).
- **Quién:** `tecnico@demo-org.com`, idealmente en el celular.
- **Pantalla:** **Agenda** → la orden → el acta.
- **Qué hacer, por pasos:**
  1. **Condiciones** de la obra (por ejemplo, «se retira furnace a gas»), que abren o cierran requisitos · `components/ConditionsPanel.tsx` · `PATCH /projects/{id}/conditions`.
  2. **Checklist técnico:** fachada, distribución, equipos viejos, proceso de gas, conductos, panel, equipos nuevos y etiquetas. Cada ítem con su foto; los condicionales admiten «No aplica» con motivo · `components/ChecklistPanel.tsx` · `GET /projects/{id}/checklist`, `PATCH /checklist-items/{id}`, `POST /projects/{id}/evidence`.
  3. **Equipos instalados** con marca, modelo y serial · `components/EquipmentPanel.tsx` · `POST /projects/{id}/equipment`. Agregar el primero **no** completa el paso: queda «En curso» con «N registrados, falta guardar la lista» hasta tocar **Guardar equipos instalados** (`POST /projects/{id}/equipment/confirm`). Agregar o quitar uno después vuelve a pedir guardar, y el cierre pide «Guardar la lista de equipos instalados».
  - **Avisos de guardado:** cada acción que guarda muestra abajo un aviso corto («Cambios guardados.», «Equipo agregado…», «Equipos instalados guardados.»), que se cierra solo o al tocarlo. Marcar avisos como leídos no lo muestra.
  4. **Materiales** usados · `components/MaterialsPanel.tsx`.
  5. **Firmas del acta** (paso propio del acta, ya no en «Anexos») · `components/SignaturesPanel.tsx`. Al tocar «Guardar equipos instalados» el acta abre este paso y baja hasta él. El técnico firma en el recuadro · `POST /projects/{id}/attestation/technician-sign`. El cliente firma de dos maneras:
     - **Enlace por correo** · `.../customer-signature-request`, página pública `/customer-signature`. Tras enviarlo, la pantalla muestra a quién y hasta cuándo (también después de recargar) y el botón **Consultar si ya firmó**, que actualiza sin recargar.
     - **En el celular del técnico**, para quien no tiene correo ni internet: «Que firme aquí, en este celular» → nombre y firma · `.../customer-sign`. En la auditoría queda como firma en persona, y el enlace pendiente deja de servir.
     - Una firma no se puede rehacer (409), y un técnico no ve ni firma el acta de una orden que no es suya (404). Las firmas **no** bloquean el cierre: es una decisión pendiente con Mariana.
  6. **Cerrar instalación** · `components/InstallationPanel.tsx` · `GET /projects/{id}/installation/gaps`, `POST /projects/{id}/installation/close`.
- **Qué debe pasar:** el expediente pasa a **Instalado**.
- **Lo que debe bloquear** (PDF §5.5, «Bloqueo de finalización»): intenta cerrar sin la foto de fachada o sin las etiquetas del equipo nuevo; no debe dejar, y debe decir qué falta.
- **Lo que no debe poder hacer el técnico:** ver proyectos que no tiene asignados, ver Expedientes, agendar inspecciones.

---

## Fase 4. Confirmación del acta e inspección (Administración)

### 4.1 Confirmar o devolver el acta

- **PDF:** §3.4 («Recopilación de evidencias», «Consolidación del expediente de pago»).
- **Pantalla:** paso **Confirmación de Administración** · `components/ReviewStep.tsx`.
- **Qué hacer:** prueba primero **Devolver** con un motivo (el técnico corrige y vuelve a cerrar) y luego **Confirmar información técnica**.
- **API:** `POST /projects/{id}/review/return`, `POST /projects/{id}/review/confirm`.
- **Qué debe pasar:** sin esta confirmación no se puede crear el cobro.

### 4.2 Inspección

- **PDF:** §3.5, §7 etapa 9.
- **Pantalla:** paso **Inspección** · `components/InspectionsPanel.tsx`.
- **Qué hacer:** **Agendar inspección** (exige permiso radicado) → registrar resultado **fallido** con observaciones → el expediente vuelve a **Listo para instalar** para el re-trabajo → el técnico cierra de nuevo → reagendar → **Aprobada** (exige el permiso firmado por el inspector).
- **API:** `POST /projects/{id}/inspections`, `POST /inspections/{id}/result`, `POST /inspections/{id}/signed-permit`.
- **Qué debe pasar:** **Inspección pendiente** → sub-estado **Inspección aprobada**. Cada intento queda guardado.
- **Nota:** si el programa no exige inspección (requisito desactivado en 0.6, como TECH), del acta confirmada se pasa directo a cobro.

### 4.3 Vista general de permisos e inspecciones

- **PDF:** §3.2 («Seguimiento de permisos»), §3.5.
- **Quién:** Administración (y quien ve todos los proyectos).
- **Pantalla:** Operación de campo → **Permisos e inspecciones** (`/permits`) · `features/finance/PermitsPage.tsx`.
- **API:** `GET /permits`, `GET /inspections`.
- **Qué debe pasar:** ves el permiso y las inspecciones del proyecto de los pasos 3.1 y 4.2, con estado y vencimiento, y los filtros funcionan. Es solo consulta: lo que se registra sigue estando dentro de cada proyecto. El técnico y el vendedor no deben poder entrar.

---

## Fase 5. Cobro y pago

> Módulo 6.

### 5.1 Crear el cobro al programa (Administración o Contabilidad)

- **PDF:** §3.4 («Radicación de cobro»), §4.3, §6 («No enviar a cobro sin checklist completo»).
- **Pantalla:** en el acta, paso **Cobro** · `components/BillingStep.tsx` → **Crear cobro**.
- **API:** `GET /projects/{id}/billing/eligibility`, `POST /projects/{id}/claims`.
- **Qué debe pasar:** el monto sale de la **tarifa vigente el día de la instalación**. El expediente pasa a **En cobro**. Crear un segundo cobro del mismo programa debe bloquearse.

### 5.2 Checklist y radicación

- **Pantalla:** **Facturación y cobros** (`/invoices`) · `features/billing/ClaimsInbox.tsx` → el cobro (`/invoices/claims/{id}`) · `features/billing/ClaimDetailPage.tsx`.
- **Qué hacer:** marca los requisitos manuales → **Radicar ante el programa** → **Ver PDF** de la factura.
- **API:** `POST /claims/{id}/checks/{código}`, `POST /claims/{id}/submit`.
- **Qué debe pasar:** no deja radicar con requisitos pendientes. Sub-estado **Radicado al programa**.

### 5.3 Rechazo y reintento

- **PDF:** §4.3 («Gestión de correcciones», «refacturación»).
- **Qué hacer:** **El programa lo rechazó…** → **Registrar rechazo** con motivo → **Refacturar** → radicar de nuevo.
- **API:** `POST /claims/{id}/reject`, `POST /claims/{id}/submit`.
- **Qué debe pasar:** sub-estado **Rechazado por el programa**; el rechazo no vence el cobro. A Contabilidad le llega un aviso.

### 5.4 Registrar el pago (Contabilidad)

- **PDF:** §4.3, §7 etapa 11.
- **Quién:** `contabilidad@demo-org.com`. Prueba antes con Administración: **no** debe poder registrar el pago.
- **Qué hacer:** **Registrar pago** con monto, fecha y referencia. Prueba un monto distinto al cobrado: debe mostrar la diferencia.
- **API:** `POST /claims/{id}/payment`.
- **Qué debe pasar:** el expediente pasa a **Pagado**.

### 5.5 Cerrar el expediente

- **Pantalla:** revisión del expediente → **Cerrar expediente…** con motivo.
- **API:** `POST /cases/{id}/transition` (`closed`).
- **Qué debe pasar:** el expediente queda **Cerrado** y no se reabre. Revisa el **Historial** completo en la revisión: cada paso con su fecha y quién lo hizo.

---

## Fase 6. Lo transversal

| Qué | Quién | Pantalla | API | PDF |
|---|---|---|---|---|
| Notificaciones (campana y centro de avisos) | Todos | campana arriba · **Notificaciones** (`/notifications`) · `features/notifications/NotificationsPage.tsx` | `GET /notifications`, `POST /notifications/{id}/read`, `PUT /notifications/preferences` | §3 («Centro de notificaciones y alertas») |
| Actividad reciente del Inicio | Todos menos el técnico | **Inicio** (`/`) · `app/DashboardHome.tsx` | `GET /cases/activity` | §7 («visibilidad en tiempo real») |
| Monitor de técnicos | Administración, Gerencia | `/technician-monitor` | `dashboards.operations` | §5.1 |
| Trabajo particular: cotización → factura → pagos | Contabilidad | **Facturación y cobros** → cotizaciones · `QuotesTab.tsx`, `QuoteDetailPage.tsx`, `InvoicesTab.tsx` | `POST /billing/quotes`, `.../send`, `.../accept`, `POST /invoices/{id}/issue`, `POST /invoices/{id}/payments` | §4.2 («clientes particulares») |
| Campañas por SMS y correo | Administración | **Campañas** (`/campaigns`) · `CampaignsPage.tsx` | `/campaigns/...` | — (agregado) |
| Gerencia solo consulta | Gerencia | todo lo que ve | intenta guardar algo: ningún botón debe funcionar | §1 |
| Auditoría | Administrador, Administración, Contabilidad, Gerencia | **Auditoría** (`/audit-log`) | `GET /audit-events` | — |
| Equipo, roles y permisos | Administrador | **Equipo** (`/users`), **Roles y permisos** (`/roles`) | `/users`, `/roles`, `/permissions` | — |
| Avisos de finanzas | Contabilidad, quien registró el gasto | campana | alertas diarias | §4.1, §4.4 |

Avisos nuevos desde el 13 de octubre: **gasto por revisar** (a quien aprueba), **gasto revisado** (a quien lo registró), **factura de proveedor por vencer** (5 días antes) y **licencia o seguro del proveedor por vencer**.

---

## Fase 7. Gastos de campo

> Paquete `finance` (Cadena B, 13 oct). Spec: `docs/superpowers/specs/2026-10-13-modulos-gastos-proveedores-finanzas-design.md`.

### 7.1 Registrar un gasto (Técnico o Vendedor)

- **PDF:** §4.1 («Registro de gastos de campo»).
- **Quién:** `tecnico@demo-org.com`, idealmente desde el celular. Repite con `vendedor@demo-org.com`.
- **Pantalla:** Finanzas → **Gastos de campo** (`/expenses`) · `features/finance/ExpensesPage.tsx`.
- **Qué hacer:** registra un gasto con categoría (gasolina, viáticos, hotel, comida, peajes y parqueo, material menor, herramienta, otro), monto, fecha, forma de pago, **foto del recibo** y, si aplica, el proyecto de la fase 3.
- **API:** `GET /expenses/catalogs`, `POST /expenses`, mis gastos: `GET /expenses/mine`, recibo: `GET /expenses/{id}/receipt`.
- **Prueba también:**
  - **Sin recibo:** no debe dejar guardar; la foto es obligatoria.
  - **Un recibo disfrazado** (un `.txt` renombrado a `.jpg`) o de más de 10 MB: debe rechazarlo, como toda subida.
  - **Más del tope** (5.000 USD por defecto): debe rechazarlo con un mensaje claro.
  - **Editar o borrar** el gasto mientras está pendiente: `PUT /expenses/{id}`, `DELETE /expenses/{id}`. Ya revisado, no debe dejar.
- **Qué debe pasar:** el gasto queda **por revisar** y a Contabilidad le llega el aviso. El técnico solo ve sus propios gastos.

### 7.2 Revisar el gasto (Contabilidad)

- **Quién:** `contabilidad@demo-org.com`.
- **Qué hacer:** aprueba uno y rechaza otro con motivo.
- **API:** `GET /expenses`, `POST /expenses/{id}/review`.
- **Qué debe pasar:** a quien lo registró le llega el aviso con el resultado. **Nadie aprueba lo propio:** con el Administrador (que también registra gastos) registra uno y trata de aprobarlo; no debe dejar.
- **Lo que no debe poder hacer:** el técnico y el vendedor no ven los gastos de los demás ni pueden aprobar.

### 7.3 Reembolso

- **Qué hacer:** a un gasto aprobado y pagado con dinero propio, **marcar reembolsado**.
- **API:** `POST /expenses/{id}/reimburse`.
- **Qué debe pasar:** queda reembolsado y, si el gasto tiene proyecto, suma a los costos de ese proyecto en la rentabilidad (fase 9.1).

---

## Fase 8. Proveedores y pagos

> El cliente respondió el cuestionario de proveedores el 8 de octubre: lo que se compra se paga al momento o con tarjeta, quieren dejar QuickBooks y Housecall, y facturas desde 10.000 USD llevan dos aprobaciones. **La plataforma no paga:** registra el pago hecho por fuera.

**Quién hace qué:**

| Acción | Rol | Permiso |
|---|---|---|
| Proveedores, facturas y registrar pagos | Contabilidad, Administrador | `suppliers.manage`, `payables.manage` |
| Aprobar y programar el pago | Gerencia y Administrador (donde está Aldo Martínez) | `payables.approve` |
| Desde el umbral: segunda aprobación | otra persona, con `payables.manage` | — |

### 8.1 El proveedor

- **PDF:** §4.4 («Gestión de proveedores»), §3.2 del cuestionario.
- **Quién:** `contabilidad@demo-org.com`.
- **Pantalla:** Finanzas → **Proveedores y pagos** (`/payables`) · `features/finance/PayablesPage.tsx` → pestaña **Proveedores**.
- **Qué hacer:**
  1. Crea un proveedor (tipo: equipos, material eléctrico, contratistas, servicios u otro), con condiciones de pago en días.
  2. Súbele documentos: W-9, licencia, seguro y contrato, con fecha de vencimiento. Pon uno que venza en menos de 30 días.
  3. **Importar CSV:** carga varios proveedores de una vez (columnas reconocidas en inglés o español: `name/nombre`, `razon_social`, `ein`, `contacto`, `telefono`, `email`, `terms`, `tipo`…). Mete uno repetido: no debe duplicarlo.
- **API:** `GET/POST /payables/suppliers`, `GET/PUT /payables/suppliers/{id}`, `POST /payables/suppliers/import`, `POST /payables/suppliers/{id}/documents`, `GET /payables/supplier-documents/{id}/file`.
- **Qué debe pasar:** los datos bancarios del proveedor solo los ve quien tiene `payables.manage`. Gerencia los ve ocultos. El documento por vencer genera el aviso diario.

### 8.2 Registrar una factura de proveedor

- **PDF:** §4.4 («Registro de facturas»).
- **Pantalla:** pestaña **Facturas**.
- **Qué hacer:** registra una factura con número del proveedor, fechas (el vencimiento sale de las condiciones de pago), líneas o total, impuestos, envío y el archivo. **Asigna una línea al proyecto de la fase 3** (es lo que alimenta la rentabilidad).
- **API:** `GET/POST /payables/invoices`, `GET /payables/invoices/{id}`, `GET /payables/invoices/{id}/file`, `GET /payables/catalogs`.
- **Prueba también:**
  - **El mismo número de factura del mismo proveedor:** debe rechazarlo.
  - **Factura ya pagada** (contado o tarjeta, bajo el umbral): queda aprobada y pagada en el mismo paso.
- **Qué debe pasar:** la factura queda **por aprobar**.

### 8.3 Aprobar (una o dos aprobaciones)

- **PDF:** §4.4 («Aprobación de pagos»).
- **Bajo el umbral** (10.000 USD por defecto): entra como `gerencia@demo-org.com` → la factura → **Aprobar** → **Programar el pago** con fecha.
- **Desde el umbral:** registra otra factura de 10.000 USD o más. Apruébala con Gerencia: queda esperando la segunda aprobación. Apruébala luego con Contabilidad. Con la **misma persona** dos veces no debe dejar.
- **API:** `POST /payables/invoices/{id}/approve`, `POST /payables/invoices/{id}/schedule`.
- **Lo que no debe poder hacer:** Contabilidad sola no aprueba una factura bajo el umbral (no tiene `payables.approve`). El técnico y el vendedor no entran a esta pantalla.
- **Anular:** una factura con motivo → `POST /payables/invoices/{id}/void`. Anulada, no se paga.

### 8.4 Registrar el pago

- **Quién:** `contabilidad@demo-org.com`.
- **Pantalla:** pestaña **Pagos**.
- **Qué hacer:** registra un pago con fecha, monto, forma, referencia, cuenta y comprobante, y repártelo entre facturas aprobadas del mismo proveedor. Haz primero un pago **parcial**.
- **API:** `GET/POST /payables/payments`, `GET /payables/payments/{id}/file`.
- **Qué debe pasar:** la factura pasa a **pagada parcialmente** y luego a **pagada**. No debe dejar pagar más que el saldo, ni pagar una factura sin aprobar.

### 8.5 Antigüedad y exportación

- **Pantalla:** pestaña **Antigüedad** (al día, 1–30, 31–60, 61–90, más de 90 días) y el botón de exportar.
- **API:** `GET /payables/aging`, `GET /payables/export.csv` (exige `accounting.export`).
- **Qué debe pasar:** el CSV trae facturas y pagos y se abre bien en Excel.

### 8.6 Ajustes (umbral y avisos)

- **Quién:** quien tiene `payables.approve` (Gerencia o Administrador). Contabilidad no ve esta pestaña.
- **Pantalla:** pestaña **Ajustes**: umbral de doble aprobación, días de aviso de vencimiento y de documentos, tope de gasto de campo.
- **API:** `GET/PUT /finance/settings`.
- **Prueba:** baja el tope de gasto a 100 y registra un gasto de 150 en la fase 7: debe rechazarlo. Déjalo como estaba.

---

## Fase 9. Conciliación y rentabilidad

> Pantalla: Finanzas → **Conciliación y rentabilidad** (`/finance-close`) · `features/finance/FinanceClosePage.tsx`.

### 9.1 Rentabilidad por proyecto

- **PDF:** §4.5 («Rentabilidad por proyecto»).
- **Quién:** Contabilidad, Gerencia o Administrador (`profitability.read`).
- **Pantalla:** pestaña **Rentabilidad**.
- **API:** `GET /finance/profitability`.
- **Qué debe pasar:** el proyecto de la fase 3 muestra lo esperado, lo cobrado (fase 5.4), los costos por tipo (la línea de la factura de proveedor de 8.2 y el gasto aprobado de 7.2) y el margen en dinero y en %. Los filtros por fechas y por programa cambian los totales. La comisión del vendedor todavía no entra.

### 9.2 Conciliación bancaria

- **PDF:** §4.5 («Conciliación»).
- **Quién:** Contabilidad o Administrador (`reconciliation.manage`).
- **Pantalla:** pestaña **Conciliación**.
- **Qué hacer:** importa un extracto CSV del banco con columnas de fecha, descripción y monto (o débito y crédito separados; en inglés o español). Pon:
  - una entrada con el monto del pago de la fase 5.4 y fecha cercana (±5 días);
  - una salida con el monto del pago al proveedor de la fase 8.4;
  - una salida con el reembolso de la fase 7.3;
  - un movimiento que no corresponda a nada.
- **API:** `POST /reconciliation/statements`, `GET /reconciliation/statements`, `GET /reconciliation/lines`, `GET /reconciliation/summary`, `GET /reconciliation/lines/{id}/candidates`, `POST /reconciliation/lines/{id}/match`, `.../ignore`, `.../unmatch`.
- **Qué debe pasar:** los movimientos con un solo candidato se concilian solos. El que no corresponde queda pendiente: márcalo como **otro** con una nota. Deshaz una conciliación y vuélvela a hacer a mano. Un CSV sin columnas de fecha y monto debe dar un mensaje claro.

---

## Fase 10. Reportes

- **PDF:** §7 («indicadores», «visibilidad en tiempo real»).
- **Quién:** Gerencia, Contabilidad, Administrador y Administración (`reports.view`). Exportar a CSV exige `reports.export` (Administración no lo tiene).
- **Pantalla:** Administración → **Reportes** (`/reports`) · `features/finance/ReportsPage.tsx`, con tres pestañas:
  - **Comercial:** visitas por resultado, expedientes por etapa, conversión, días hábiles hasta la aprobación, rechazos y devoluciones, por vendedor.
  - **Operación:** instalaciones por semana y por técnico, inspecciones aprobadas y fallidas, días de aprobación a instalación.
  - **Finanzas:** cobrado por mes, por cobrar, por pagar con antigüedad, gastos por categoría.
- **API:** `GET /reports/{commercial|operations|finance}`, `GET /reports/{tipo}/csv`, con `date_from` y `date_to`.
- **Qué debe pasar:** el expediente que recorriste aparece en los números (visita, aprobación, instalación, cobro, gasto, factura). Los tiempos salen del historial de etapas. Cambia el rango de fechas y revisa que los totales cambien. El técnico y el vendedor no entran.

---

## Lo que todavía no existe (no lo busques)

El autollenado de formularios municipales (§3.2), la sincronización con Microsoft Forms (§3), pagar desde la plataforma (conexión bancaria), la sincronización automática con QuickBooks, los 1099, el inventario de bodega, las órdenes de compra y la lista de precios por proveedor. La comisión del vendedor tampoco entra todavía en la rentabilidad.

---

## Bitácora de lo que encuentres

Anota aquí cada cosa rara, aunque no estés seguro de que sea un error: la fecha, qué pasó y qué se hizo.

| Fecha | Qué pasó | Qué hicimos |
|---|---|---|
| 11 oct | Campañas, Documentos por revisar y Envíos no tenían botones de página | Se agregaron (`fe0f21e`) |
| 11 oct | Una dirección sin permiso mostraba «No tienes acceso» | Ahora lleva al Inicio (`d9e98f0`) |
| 11 oct | La firma salía como texto, sin recuadro para firmar | No deja publicar una versión con firma sin aceptación de términos (`3afa0b4`) |
| 11 oct | «Volver a programas» iba al primer programa | Vuelve al programa en el que estabas (`23fac57`) |
| 11 oct | La firma dibujada no se guardaba | Se guarda con «Guardar y seguir» (`7e2708a`) |
| 11 oct | Un expediente aprobado no salía en la columna «Aprobado» | El tablero refresca sus tarjetas al volver (`0573ed4`) |
| 12 oct | Decía que faltaban datos aunque el formulario se veía completo | El paso ya no salta solo sin guardar (`d7bdff5`) |
| 12 oct | Los números aceptaban «e», «+» y valores sobre el máximo | Solo dígitos y hasta el máximo del catálogo (`d6fb855`) |
| 14 oct | No se veía el contador de días ni salía la alerta | Contador «⏱ N días hábiles» y botón «Revisar ahora» (`607043e`) |
| 15 oct | Un PDF no abría (era falso, del script de QA) | La subida rechaza PDF falsos o cortados (`7a6ef81`) |
| 15 oct | «Mis avisos» no tenía páginas | Páginas de a 30 (`448a851`) |
| 15 oct | El ícono de avisos era un rombo | Campana (`403d727`) |
| 17 oct | El técnico veía «Agregar cliente» y «Editar cliente» y recibía un 403 | Solo los ve quien tiene el permiso (`ed5f578`) |
| 17 oct | La orden atrasada en la agenda salía en rojo y sin el enlace | Arreglado el choque de estilos (`397840d`) |
| 17 oct | El CI de main fallaba por cobertura (68,5 %) | Coverage sigue los greenlets de SQLAlchemy: 89 % (`397840d`) |
| 18 oct | «Equipos instalados» quedaba completo con el primer equipo; casi nada avisaba al guardar | Botón «Guardar equipos instalados» y avisos de guardado en toda la app (`1edaf0f`) |
| 18 oct | Las firmas confundían en «Anexos», había que recargar para ver la del cliente y no había opción sin correo | Paso «Firmas del acta», «Consultar si ya firmó» y firma en el celular del técnico; el técnico ya no firma órdenes ajenas |
|  |  |  |
