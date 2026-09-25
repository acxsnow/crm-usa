# Qué ve cada perfil en el menú

Generado desde el código, no escrito a mano: los permisos salen de
`DEFAULT_ROLE_PERMISSIONS` y los ítems de `frontend/src/config/navigation.ts`.

Reglas para leerlo:

- **La regla es una sola: cada perfil ve únicamente aquello para lo que tiene
  permiso.** Si no aparece en su lista, tampoco puede entrar escribiendo la URL.
- Lo marcado *(pendiente)* ya está permitido para ese perfil, pero la pantalla
  todavía no existe: sale en gris en el menú. Su descripción dice lo que hará.
- Esta es la matriz **inicial**. El administrador puede cambiarla desde
  *Roles y permisos* sin tocar código, y desde ese momento manda lo que él dejó.

---

## Vendedor

Toca puertas en los parques, levanta el prospecto, revisa elegibilidad y arma el expediente con la firma y los documentos del cliente.

Ojo: **no ve Pipeline**. Esa pantalla pide `opportunities.manage` y la matriz no se lo da. Si quieres que lo vea, márcaselo en Roles y permisos.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- *Operación comercial*
  - **Prospectos** — la puerta tocada que todavía no es cliente: dónde fue, con quién se habló y en qué quedó.
  - **Clientes** — la ficha del cliente: datos, contactos, dirección del inmueble e historial.
  - **Expedientes** — el caso completo: programa elegido, formulario, términos y condiciones, firma y documentos. Es lo que el vendedor manda a revisión.
  - **Documentos** *(pendiente)* — los archivos del caso: documentos, fotos y videos del cliente y del inmueble.
- *Finanzas*
  - **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- *Administración*
  - **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Pipeline, Proyectos, Monitor de técnicos, Mi agenda, Permisos e inspecciones, Facturación y cobros, Proveedores y pagos, Conciliación y rentabilidad, Reportes, Configuración de programas, Equipo, Roles y permisos, Auditoría.

---

## Administración

Revisa lo que manda el vendedor, aprueba o devuelve el expediente, saca el permiso municipal y coordina la instalación.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- *Operación comercial*
  - **Prospectos** — la puerta tocada que todavía no es cliente: dónde fue, con quién se habló y en qué quedó.
  - **Clientes** — la ficha del cliente: datos, contactos, dirección del inmueble e historial.
  - **Expedientes** — el caso completo: programa elegido, formulario, términos y condiciones, firma y documentos. Es lo que el vendedor manda a revisión.
  - **Documentos** *(pendiente)* — los archivos del caso: documentos, fotos y videos del cliente y del inmueble.
- *Operación de campo*
  - **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
  - **Monitor de técnicos** — dónde está y qué hace cada técnico en campo, en vivo.
  - **Permisos e inspecciones** *(pendiente)* — el permiso municipal y la inspección posterior a la instalación.
- *Finanzas*
  - **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
- *Administración*
  - **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
  - **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
  - **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Pipeline, Mi agenda, Gastos de campo, Proveedores y pagos, Conciliación y rentabilidad, Configuración de programas, Equipo, Roles y permisos.

---

## Técnico

Instala en sitio. Ve solo los proyectos que tiene asignados y carga sus evidencias y gastos.

Ve Clientes porque necesita el dato del cliente de su proyecto, pero **no ve Prospectos**: no hace venta.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- *Operación comercial*
  - **Clientes** — la ficha del cliente: datos, contactos, dirección del inmueble e historial.
- *Operación de campo*
  - **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
  - **Mi agenda** *(pendiente)* — las visitas asignadas al técnico que entra, ordenadas por día.
- *Finanzas*
  - **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- *Administración*
  - **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Prospectos, Expedientes, Pipeline, Documentos, Monitor de técnicos, Permisos e inspecciones, Facturación y cobros, Proveedores y pagos, Conciliación y rentabilidad, Reportes, Configuración de programas, Equipo, Roles y permisos, Auditoría.

---

## Contabilidad

Factura al programa, registra el pago, controla proveedores y cierra la rentabilidad.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- *Operación comercial*
  - **Clientes** — la ficha del cliente: datos, contactos, dirección del inmueble e historial.
  - **Expedientes** — el caso completo: programa elegido, formulario, términos y condiciones, firma y documentos. Es lo que el vendedor manda a revisión.
- *Operación de campo*
  - **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
- *Finanzas*
  - **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
  - **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
  - **Proveedores y pagos** *(pendiente)* — los proveedores y lo que se les debe.
  - **Conciliación y rentabilidad** *(pendiente)* — el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- *Administración*
  - **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
  - **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
  - **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Prospectos, Pipeline, Documentos, Monitor de técnicos, Mi agenda, Permisos e inspecciones, Configuración de programas, Equipo, Roles y permisos.

---

## Gerencia

Mira. No opera: consulta todo el negocio para decidir, sin crear ni modificar.

Todo lo que ve es de lectura. Los permisos que tiene son de consulta y tableros; ningún botón de guardar le va a funcionar.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- *Operación comercial*
  - **Clientes** — la ficha del cliente: datos, contactos, dirección del inmueble e historial.
  - **Expedientes** — el caso completo: programa elegido, formulario, términos y condiciones, firma y documentos. Es lo que el vendedor manda a revisión.
- *Operación de campo*
  - **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
  - **Monitor de técnicos** — dónde está y qué hace cada técnico en campo, en vivo.
- *Finanzas*
  - **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
  - **Conciliación y rentabilidad** *(pendiente)* — el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- *Administración*
  - **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
  - **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
  - **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Prospectos, Pipeline, Documentos, Mi agenda, Permisos e inspecciones, Gastos de campo, Proveedores y pagos, Configuración de programas, Equipo, Roles y permisos.

---

## Administrador

Configura el sistema: programas, formularios, flujos, usuarios y roles. Ve todo.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- *Operación comercial*
  - **Prospectos** — la puerta tocada que todavía no es cliente: dónde fue, con quién se habló y en qué quedó.
  - **Clientes** — la ficha del cliente: datos, contactos, dirección del inmueble e historial.
  - **Expedientes** — el caso completo: programa elegido, formulario, términos y condiciones, firma y documentos. Es lo que el vendedor manda a revisión.
  - **Pipeline** — los expedientes vistos por etapa del embudo, para saber qué está atascado y dónde.
  - **Documentos** *(pendiente)* — los archivos del caso: documentos, fotos y videos del cliente y del inmueble.
- *Operación de campo*
  - **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
  - **Monitor de técnicos** — dónde está y qué hace cada técnico en campo, en vivo.
  - **Mi agenda** *(pendiente)* — las visitas asignadas al técnico que entra, ordenadas por día.
  - **Permisos e inspecciones** *(pendiente)* — el permiso municipal y la inspección posterior a la instalación.
- *Finanzas*
  - **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
  - **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
  - **Proveedores y pagos** *(pendiente)* — los proveedores y lo que se les debe.
  - **Conciliación y rentabilidad** *(pendiente)* — el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- *Administración*
  - **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
  - **Configuración de programas** *(pendiente)* — el catálogo de programas de incentivos y sus reglas: campos del formulario, flujo de estados y zonas.
  - **Equipo** — los usuarios: invitar, activar, desactivar y asignarles rol.
  - **Roles y permisos** — crear roles y marcar qué puede hacer cada uno. Es lo que gobierna todo este archivo.
  - **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
  - **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** nada — tiene acceso completo.

---

## Cómo cambiar esto

En *Roles y permisos*: se abre el rol, se marcan o desmarcan permisos y se
guarda. El menú de quien tenga ese rol cambia en su siguiente ingreso. No hace
falta tocar código ni migrar nada, y queda registrado en auditoría.

También se pueden crear roles nuevos desde cero — los seis de arriba son los
del PDF, no un límite.
