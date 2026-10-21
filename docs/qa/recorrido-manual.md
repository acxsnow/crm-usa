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
| 11. Bodega: cargar el catálogo | Administrador | cuestionario del 19 oct, punto 2 | — |
| 12. Bodega: salidas autorizadas | Técnico, Administración | cuestionario del 19 oct, punto 1 | — |
| 13. Bodega: listas predefinidas | Administración, Técnico | cuestionario del 19 oct, punto 2 | — |
| 14. Presupuesto y costo real | Administración, Gerencia | cuestionario del 19 oct, punto 3 | — |

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
  - **Por revisar › Documentos** (`/review`; `/documents` redirige) · `features/review/ReviewInboxPage.tsx` + `features/sales/DocumentsQueuePage.tsx` · API `GET /documents/review-queue`.
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
- **Cómo llega Administración:**
  - **Aviso:** al cerrar el técnico, a quien tiene `checklists.approve` le llega a la campanita «Instalación cerrada: CASE-…», con enlace directo al paso 7. El técnico que cerró no lo recibe. Necesita el worker de avisos corriendo.
  - **Bandeja:** menú **Por revisar › Actas por confirmar** (`/review?tab=actas`; `/acta-reviews` redirige · `ActaReviewQueuePage.tsx` · `GET /acta-reviews/pending`). Muestra las instalaciones cerradas sin confirmar, la más vieja primero, con expediente, técnico, fecha de cierre y días esperando. Al confirmar, el acta sale de la bandeja; si se devuelve y el técnico vuelve a cerrar, entra de nuevo. El técnico no la ve.
- **Pantalla:** paso **Confirmación de Administración** · `components/ReviewStep.tsx`. El enlace `?paso=review` lo abre y baja hasta él.
- **Qué hacer:** prueba primero **Devolver** con un motivo (el técnico corrige y vuelve a cerrar) y luego **Confirmar información técnica**.
- **API:** `POST /projects/{id}/review/return`, `POST /projects/{id}/review/confirm`.
- **Qué debe pasar:** sin esta confirmación no se puede crear el cobro.

### 4.2 Inspección

- **PDF:** §3.5, §7 etapa 9.
- **Cómo llega Administración:** **Por revisar › Inspección municipal** (`/review?tab=inspecciones` · `GET /inspection-queue`). Muestra las instalaciones cerradas sin inspección aprobada como «Sin agendar», «Agendada» (con fecha) o «Falló: reagendar», la cerrada hace más tiempo primero, con los días desde el cierre. La fila abre el proyecto en el paso Inspección (`?paso=inspection`). Al aprobarse la inspección, sale.
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
- **Programa:** el paso solo ofrece el programa del expediente; crear un cobro a otro responde 409 (`program_not_of_case`). Un proyecto sin expediente o sin programa ve todos. El programa necesita tarifa vigente el día de la instalación.
- **Cómo llega:** **Por revisar › Cobros por crear** (`/review?tab=cobros` · `GET /billing/to-create`): la misma lista «Por cobrar» de Facturación (actas confirmadas sin cobro). La fila abre el proyecto en el paso Cobro (`?paso=billing`). Contabilidad ve solo esta pestaña.
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

## Fase 11. Bodega: cargar el catálogo

> El cliente respondió el cuestionario de control de bodega el 19 de octubre. **Esta fase es solo lo primero**: tener el catálogo y las existencias dentro del sistema. Las órdenes de salida autorizadas vienen en la fase 12; las listas predefinidas, el presupuesto del proyecto y el diario de obra vienen después (ver «Lo que todavía no existe»).

**Quién hace qué:**

| Acción | Rol | Permiso |
|---|---|---|
| Ver existencias y artículos | Administrador, Administración, Contabilidad, Técnico | `warehouse.read` |
| Crear y editar artículos, cargar el Excel, mover el saldo a mano | Administrador, Administración | `warehouse.manage` |
| Registrar el conteo físico | Administrador, Administración | `warehouse.count` |

### 11.1 Importar el catálogo del Excel

- **Quién:** `admin@demo-org.com`.
- **Pantalla:** Bodega → **Existencias** (`/warehouse`) · `features/warehouse/WarehouseStockPage.tsx` → botón **Importar catálogo**.
- **Qué hacer:**
  1. Sube el `.xlsx` del catálogo. Se leen las filas con nombre de artículo; la primera fila de encabezados se reconoce sola.
  2. Deja marcada la casilla «Corregir la existencia con la cantidad del archivo» la primera vez: la cantidad de cada fila queda como **conteo inicial** (un movimiento de entrada con ese motivo). Si la dejas desmarcada, los artículos entran con saldo en cero.
  3. Vuelve a subir **el mismo archivo**: no debe duplicar artículos (la llave es la referencia `SKU`), debe reportarlos como actualizados y **no** volver a sumar el saldo.
- **API:** `GET /warehouse/catalogs`, `POST /warehouse/import` (multipart), `POST /warehouse/import/rows` (mismo resultado sin archivo, para pegar filas).
- **Qué debe pasar:** el aviso dice la hoja leída, cuántas filas se leyeron, cuántos artículos se crearon, cuántos se actualizaron y cuántos quedaron con la existencia corregida. Las filas malas **no abortan la carga**: aparecen listadas con su número y el motivo (por ejemplo, una cantidad que no es número).
- **Lo que no debe poder hacer:** el técnico no ve el botón (le falta `warehouse.manage`).

### 11.2 Existencias y aviso de lo que está bajo el mínimo

- **Pantalla:** Bodega → **Existencias** (`/warehouse`).
- **Qué hacer:** deja un artículo con el mínimo en 50 y existencia en 10. Filtra por categoría y por «Solo los que están en o bajo el mínimo».
- **API:** `GET /warehouse/stock`, `GET /warehouse/stock/summary` (`low_count`), `GET /warehouse/items`, `GET /warehouse/movements`.
- **Qué debe pasar:** el artículo sale con el chip **Bajo mínimo** y la fila resaltada; el indicador **En o bajo el mínimo** cuenta los que están así. La columna **Dónde** dice cuánto hay en cada ubicación. El técnico no ve costos ni valores.

### 11.3 El artículo y sus ubicaciones

- **Pantalla:** Bodega → **Artículos** (`/warehouse/items`) · `features/warehouse/WarehouseItemsPage.tsx`.
- **Qué hacer:** crea un artículo (nombre, referencia, categoría, unidad, costo, mínimo, proveedor, si lleva serial). Crea una ubicación y registra una entrada y una salida.
- **API:** `GET/POST/PUT /warehouse/items`, `GET/POST/PUT /warehouse/locations`, `POST /warehouse/movements`.
- **Qué debe pasar:** una **entrada** sube el saldo y una **salida** lo baja; el libro de movimientos guarda ambos con su fecha y su motivo. **La salida no se registra a mano por esta vía:** sale con un 400 — la salida la autoriza el sistema por una orden (fase siguiente), no cualquiera tecleando el saldo.
- **Anulación:** volver a registrar el mismo movimiento con la misma clave no descuenta dos veces.

### 11.4 Conteo físico (fin de semana)

- **Quién:** `administracion@demo-org.com` (`warehouse.count`).
- **Qué hacer:** con la existencia del sistema en 10, registra un **conteo** de 7 en esa ubicación.
- **API:** `GET /warehouse/locations`, `POST /warehouse/counts`.
- **Qué debe pasar:** queda un movimiento de **ajuste** por −3 con el motivo «Conteo físico» y el saldo pasa a 7. Registrar el mismo conteo otra vez **no** vuelve a ajustar (lo reporta como «sin cambio»).
- **Lo que no debe poder hacer:** quien no tiene `warehouse.count` no entra a la pantalla de conteo.

---

## Fase 12. Bodega: salidas autorizadas

> Punto 1 del cuestionario del 19 de octubre: *«para el retiro de los productos de la bodega el sistema da una orden de salida autorizada electrónicamente, ya sea por él o por el supervisor»*.
>
> La regla es una sola: **el material no sale a mano**. Sale de una orden que el técnico pide, un supervisor autoriza y Bodega entrega. Sin autorización no hay movimiento de salida.

**Quién hace qué:**

| Acción | Rol | Permiso |
|---|---|---|
| Pedir la salida y ver las órdenes | Técnico, Administrador, Administración | `warehouse.request_release` (pedir) · `warehouse.read` (ver) |
| Autorizar o rechazar la salida | Administrador, Administración (supervisor) | `warehouse.approve_release` |
| Entregar el material | Administrador, Administración | `warehouse.deliver` |

### 12.1 El técnico pide la salida

- **Quién:** `tecnico@demo-org.com`.
- **Pantalla:** Bodega → **Salidas** (`/warehouse/releases`) · `features/warehouse/WarehouseReleasesPage.tsx` → botón **Nueva salida**.
- **Qué hacer:**
  1. Elige la obra (para que el material quede cargado al proyecto), la fecha en que se necesita y una nota para quien entrega.
  2. Agrega los renglones: artículo, cantidad, medida o calibre y notas del renglón. Puedes agregar o quitar renglones; las cantidades, el calibre y las notas se escriben a mano.
  3. Guarda. Queda como **borrador sin número** y **no mueve ninguna existencia**.
  4. Cuando esté completa, toca **Enviar a autorizar**: ahí sí se asigna el número (`SAL-2026-0001`) y pasa a **Por autorizar**.
- **API:** `GET /warehouse/catalogs`, `GET /warehouse/items`, `GET /projects`, `POST /warehouse/releases`, `POST /warehouse/releases/{id}/submit`.
- **Qué debe pasar:** antes de enviarla el número está vacío y el saldo del artículo **no** cambia. Al enviarla aparece el número y la orden salta a la bandeja del supervisor.

### 12.2 El supervisor autoriza (o rechaza con motivo)

- **Quién:** `admin@demo-org.com` o `administracion@demo-org.com`.
- **Pantalla:** Bodega → **Salidas** → pestaña **Salidas por autorizar** (con el contador de pendientes encima).
- **Qué hacer:**
  1. Abre la orden y revisa los renglones (el desplegable «N renglones» muestra artículo, cantidad, calibre y lo entregado).
  2. **Autorizar** la deja lista para entregar. **Rechazar** exige un motivo escrito: ese texto le queda al técnico.
- **API:** `GET /warehouse/releases/pending`, `POST /warehouse/releases/{id}/approve`, `POST /warehouse/releases/{id}/reject`.
- **Qué debe pasar:** autorizar no mueve todavía el saldo. Una orden **rechazada** no se puede entregar (responde 400) y el motivo queda guardado en la orden.
- **Lo que no debe poder hacer:** el técnico que pidió la salida **no** puede autorizarla (responde 403): el sistema separa pedir de autorizar.

### 12.3 Bodega entrega y el saldo baja

- **Quién:** quien entrega el material (`warehouse.deliver`).
- **Qué hacer:** con la orden **autorizada**, toca **Entregar**.
- **API:** `POST /warehouse/releases/{id}/deliver`.
- **Qué debe pasar:**
  - El saldo baja en la ubicación de entrega y queda un movimiento de **salida** en el libro con el número de la orden como referencia (`GET /warehouse/movements`, pantalla Bodega → **Movimientos**).
  - Si hay obra, el material entregado aparece en «Lo que la orden necesita» del proyecto, con la nota «De bodega · SAL-…»: se ve de qué orden salió cada cosa.
  - **Sin existencia no se bloquea:** la orden queda **entregada** y el aviso dice qué faltó («No había existencia en bodega.» o «Solo había 3.00 de 10.00.»); ese texto queda guardado en la orden.
  - **Entregar dos veces no descuenta dos veces:** la orden solo se entrega desde el estado **autorizada**, así que el segundo intento responde 400 y el saldo queda igual.
- **Lo que no debe poder hacer:** otra organización no ve ni puede autorizar/entregar la orden (404). La salida a mano por `POST /warehouse/movements` sigue rechazada con 400.

---

## Fase 13. Bodega: listas predefinidas por tipo de trabajo

> Punto 2 del cuestionario del 19 de octubre: *«esas órdenes tengan una lista ya predefinida de acuerdo al tipo de trabajo; las aires y pedestales siempre llevan el mismo material, a veces cambian algunas cantidades o calibres»*.
>
> La regla es una sola: **la lista es una plantilla, no un documento**. Al aplicarla, sus renglones se **copian** a la orden: cambiar la lista después no toca nada de lo que ya se pidió.

**Quién hace qué:**

| Acción | Rol | Permiso |
|---|---|---|
| Ver las listas | Técnico, Administrador, Administración | `warehouse.read` |
| Crear, editar y borrar listas | Administrador, Administración | `warehouse.kits_manage` |
| Aplicar una lista a una orden | quien pide la salida | `warehouse.request_release` |

### 13.1 Armar la lista

- **Quién:** `admin@demo-org.com` o `administracion@demo-org.com`.
- **Pantalla:** Bodega → **Listas** (`/warehouse/kits`) · `features/warehouse/WarehouseKitsPage.tsx` → botón **Nueva lista**.
- **Qué hacer:**
  1. Ponle el nombre (`Instalación de aire — estándar`), el tipo de trabajo (`hvac_install`) y para qué sirve.
  2. Agrega los renglones: artículo, cantidad sugerida, medida o calibre (`3/8`, `1/4`, `12.000 BTU`), sección (`Líneas`, `Unidad exterior`) y notas. El desplegable de artículos solo muestra los activos del catálogo.
  3. El interruptor de cada renglón lo deja **opcional** (lo que se lleva solo cuando el trabajo lo pide); por defecto es obligatorio.
  4. Guarda. La lista aparece en el listado con el desplegable «N renglones».
- **API:** `GET /warehouse/catalogs`, `GET /warehouse/items`, `GET /warehouse/kits`, `POST /warehouse/kits`, `PUT /warehouse/kits/{id}`, `DELETE /warehouse/kits/{id}`.
- **Qué debe pasar:** la lista se ve con su material. **Ninguna cantidad con cero** (`invalid_kit_quantity`, 400) y **ninguna lista sin renglones**.
- **Lo que no debe poder hacer:** el técnico **no** crea ni edita listas (403); otra organización no ve ni usa la lista ajena (404).

### 13.2 Aplicar la lista al pedir la salida

- **Quién:** `tecnico@demo-org.com`.
- **Pantalla:** Bodega → **Salidas** → **Nueva salida**.
- **Qué hacer:**
  1. Elige la obra, la fecha y la nota; arriba de los renglones aparece el selector **«Aplicar una lista predefinida»** (solo con las listas activas).
  2. Elige la lista (por ejemplo «Instalación de aire — estándar»): sus renglones caen en el formulario con su cantidad y su calibre, y un texto recuerda cuál se aplicó. Nada se guarda todavía.
  3. Ajusta lo que el trabajo pida (**35** en vez de 20, calibre **1/2** en vez de 3/8), agrega un extra a mano y deja las notas de la línea.
  4. Guarda el borrador y luego **Enviar a autorizar**.
- **API:** `GET /warehouse/kits?active=true`, `POST /warehouse/releases`.
- **Qué debe pasar:** el borrador queda con los renglones de la lista más los extras. Si aplicas la misma lista dos veces en la misma orden, **no repite** el material (compara artículo + calibre); lo que ya estaba se queda quieto.
- **Lo que no debe poder hacer:** aplicar una lista de otra organización (404). Una lista sin material guardado no se aplica (`empty_kit`, 400).

### 13.3 La copia es de la orden, no de la lista

- **Quién:** quien pide la salida, con un borrador abierto.
- **Qué hacer:** edita las cantidades, los calibres y las notas de **su** orden, o borra renglones. El formulario de la orden también permite aplicar la lista desde arriba de los renglones.
- **API:** `PUT /warehouse/releases/{id}`.
- **Qué debe pasar:** **la plantilla no se toca**. Se puede cambiar la lista a 30 y calibre 1/2 y la orden ya armada sigue con lo suyo. Las líneas que vinieron de una lista quedan marcadas con origen **lista** y las escritas a mano con **manual**, para saber qué se siguió y qué se salió del guion.
- **Lo que no debe poder hacer:** editar una orden que ya salió de borrador (`release_not_editable`, 400): hay que rechazarla y hacer otra.

---

## Fase 14. Bodega: presupuesto del proyecto y costo real

> Punto 3 del cuestionario del 19 de octubre: *«en cada proyecto se pueda hacer un presupuesto o un estimado y comparar con los gastos reales»*.
>
> La regla es una sola: **lo que entra a bodega es inventario, no costo de la obra** (D-BOD-2). El material se vuelve costo cuando **sale** para la obra. Por eso el mismo material nunca se cuenta dos veces: ni en la factura de compra ni en la entrega de bodega.

**De dónde sale el costo real:** tres cosas, y ninguna es «lo que se compró».

| Origen | Qué cuenta |
|---|---|
| Salidas de bodega | lo entregado a la obra, valorado a **costo del catálogo** (no al precio de venta) |
| Gastos de campo aprobados | nafta, peajes, viáticos: lo que se gasta y no se presupuesta |
| Compras directas a la obra | material o equipo facturado a la obra que **nunca pasó por bodega** |

**Quién hace qué:**

| Acción | Rol | Permiso |
|---|---|---|
| Ver el presupuesto y la comparación | Administrador, Administración, Gerencia | `warehouse.read`, `budgets.manage` o `budgets.approve` |
| Armar, editar y borrar el borrador | Administrador, Administración | `budgets.manage` |
| Aprobar el presupuesto | Administrador, Administración | `budgets.approve` |

### 14.1 Armar el presupuesto de la obra

- **Quién:** `admin@demo-org.com` o `administracion@demo-org.com`.
- **Pantalla:** Proyectos → abre la obra → anexo **Presupuesto** · `features/warehouse/ProjectBudgetPanel.tsx` → botón **Armar presupuesto**.
- **Qué hacer:**
  1. Cada renglón es una **categoría** (Material, Equipo, Mano de obra, Contratista, Permiso, Servicios, Otro), una **cantidad** y un **costo unitario**. El monto se calcula solo.
  2. Si eliges un artículo del catálogo, el sistema trae su nombre, su unidad y su costo; si es algo que no es del catálogo (una cuadrilla, un permiso), escribes la descripción a mano.
  3. El atajo **Cargar la lista** copia de golpe una lista predefinida por tipo de trabajo (punto 2): el material entra como **Material** y lo que el catálogo marca como equipo entra como **Equipo**. Aplicarla dos veces no repite el material.
  4. Guarda el borrador. Todavía no cuenta para nada.
- **API:** `GET /warehouse/catalogs`, `GET /warehouse/items`, `GET /warehouse/kits?active=true`, `POST /warehouse/budgets`, `PUT /warehouse/budgets/{id}`, `POST /warehouse/budgets/{id}/apply-kit`.
- **Qué debe pasar:** el borrador queda con sus renglones y su total. Nada de la obra cambia hasta aprobarlo.
- **Lo que no debe poder hacer:** una cantidad en cero o negativa se rechaza (`invalid_budget_quantity`, 400); una categoría que no está en el catálogo se rechaza (`invalid_budget_category`, 400); el técnico **no** arma presupuesto (403); otra organización no ve ni toca el presupuesto ajeno (404).

### 14.2 Aprobar (y qué pasa con el anterior)

- **Quién:** quien tenga `budgets.approve`.
- **Pantalla:** la misma sección → botón **Aprobar presupuesto**.
- **Qué hacer:** con el borrador listo, apruébalo (también puedes seguir editándolo antes).
- **API:** `POST /warehouse/budgets/{id}/approve`.
- **Qué debe pasar:**
  - El presupuesto queda **Aprobado** con la fecha y quién lo aprobó. **Ese** es el que usa la comparación.
  - Si apruebas **otro** presupuesto de la misma obra, el anterior **no se borra**: queda como **Reemplazado**. Así el histórico se conserva y `GET /warehouse/budgets?status=aprobado` devuelve siempre uno solo por obra.
  - Un presupuesto **aprobado no se edita ni se borra** (`budget_not_editable`, 400): para cambiarlo hay que armar otro borrador y aprobarlo.
  - Aprobar sin renglones responde `empty_budget` (400).

### 14.3 Ver el estimado contra el real

- **Quién:** cualquiera de los tres roles de arriba.
- **Pantalla:** la sección **Presupuesto** de la obra → tabla **Estimado contra real**.
- **Qué hacer:** lee la tabla por categoría: **Estimado**, **Real**, **Desviación** y **%**. La desviación es `real − estimado`: **positiva** quiere decir que se gastó **más** de lo presupuestado.
- **API:** `GET /warehouse/projects/{id}/budget`, `GET /warehouse/projects/{id}/budget-vs-actual`.
- **Qué debe pasar:**
  - **Sin doble conteo:** compra de tubo facturada a la obra **y** ese tubo entra a bodega → **no** aparece como costo. Sale a la obra (orden de salida entregada) → **ahí sí** aparece, valorado a costo del catálogo. La prueba manual: factura de 20 pies por $100 cargada a la obra y 8 pies entregados a $5 → Material real = **$40**, no $100.
  - **Compra directa sí cuenta:** un equipo facturado a la obra que nunca pasó por bodega es costo desde el primer día.
  - **Los gastos de campo aprobados suman** en su propia fila (**Gastos de campo**), que no tiene estimado porque no se presupuesta. Nadie aprueba su propio gasto (`own_expense`, 403): quien sube el gasto no puede aprobarlo.
  - La obra **sin presupuesto** muestra la comparación en cero y el aviso «Esta obra todavía no tiene presupuesto».

### 14.4 Compras sugeridas del fin de semana

- **Quién:** Administración (o Gerencia, que solo mira).
- **Pantalla:** Bodega → **Compras sugeridas** (`/warehouse/purchasing`) · `features/warehouse/WarehousePurchasingPage.tsx`.
- **Qué hacer:** mira la tabla por artículo: **Presupuestado**, **En bodega**, **Por comprar**, costo unitario y **costo estimado** de lo que falta. Arriba de todo va el total a comprar.
- **API:** `GET /warehouse/purchasing`.
- **Qué debe pasar:** «presupuestado por venir» son los presupuestos **aprobados** de obras que **todavía no terminaron**; lo de una obra ya terminada **no** se vuelve a comprar y un borrador **sin aprobar tampoco cuenta**. La columna **Por comprar** nunca es negativa: **sobrar no es comprar**. Si el artículo está en o bajo su mínimo, lo dice.
- **Lo que no debe poder hacer:** otra organización no ve nada de esta obra (lista vacía).

---

## Lo que todavía no existe (no lo busques)

El autollenado de formularios municipales (§3.2), la sincronización con Microsoft Forms (§3), pagar desde la plataforma (conexión bancaria), la sincronización automática con QuickBooks, los 1099, las órdenes de compra y la lista de precios por proveedor. La comisión del vendedor tampoco entra todavía en la rentabilidad.

De bodega ya están **el catálogo, las existencias** (fase 11), **las salidas con autorización electrónica** (fase 12), **las listas predefinidas por tipo de trabajo** (fase 13) y **el presupuesto del proyecto contra el costo real, con las compras sugeridas** (fase 14). Todavía **no** existe el diario de obra día por día (punto 4).

Falta cargar las listas reales del cliente: mientras no llegue su listado por tipo de trabajo, las listas se arman a mano en la pantalla.

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
| 18 oct | Las firmas confundían en «Anexos», había que recargar para ver la del cliente y no había opción sin correo | Paso «Firmas del acta», «Consultar si ya firmó» y firma en el celular del técnico; el técnico ya no firma órdenes ajenas (`31fc27a`, `f25924d`) |
| 18 oct | El técnico no podía descargar el acta que firmó (403) | La descarga quien ve el proyecto (`63ddc0e`) |
| 18 oct | El PDF del acta decía «CRM Field Ops» y las firmas salían solas en otra hoja | Título del documento, expediente y equipos; firmas junto al texto en una hoja |
| 19 oct | Administración no sabía dónde confirmar el acta; «Crear proyecto» confundía | Aviso al cerrar, bandeja «Actas por confirmar»; sale «Crear proyecto» (el proyecto nace al aprobar el expediente) |
| 19 oct | El trabajo de Administración estaba repartido; no había lista de inspecciones por agendar | Bandeja «Por revisar» con Documentos, Actas por confirmar, Inspección municipal y Cobros por crear |
| 19 oct | Inicio daba 403 a Administración (tablero de finanzas) | La tarjeta pide el dato solo con `dashboards.finance` |
| 19 oct | El paso de cobro ofrecía todos los programas, no el del expediente | Solo el programa del expediente; la API rechaza otro (`program_not_of_case`) |
|  |  |  |
