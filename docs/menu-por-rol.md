# Qué ve cada perfil en el menú

Generado desde el menú **real** de la aplicación: un script entra con cada
rol y anota lo que aparece. No es una lectura del código, es lo que la
persona ve.

Reglas para leerlo:

- **Cada perfil ve únicamente aquello para lo que tiene permiso.** Si no
  aparece en su lista, tampoco puede entrar escribiendo la URL.
- Lo marcado *(pendiente)* ya está permitido para ese perfil, pero la pantalla
  todavía no existe: sale en gris. Su descripción dice lo que hará.
- Esta es la matriz **inicial**. El administrador puede cambiarla desde
  *Roles y permisos* sin tocar código, y desde ese momento manda lo que él dejó.

> **Ya no existen «Prospectos» ni «Pipeline».** Eran del CRM genérico anterior.
> El expediente cubre la puerta desde el primer toque, así que un prospecto y
> un expediente eran la misma cosa con dos nombres. El tablero por etapas
> reemplaza al Pipeline y vivirá dentro de Expedientes.

---

## Vendedor

Toca puertas en los parques, levanta el expediente, revisa elegibilidad y lo manda a revisión con la firma y los documentos del cliente.

**El expediente ES la puerta**: se abre al tocar, antes de que exista el cliente. Si nadie abre, se guarda como «sin contacto» y listo — nunca se pidió un cliente. Si abren y les interesa, los datos del cliente, el formulario del programa y los adjuntos se llenan dentro del mismo expediente, sin salir a otra pantalla.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- **Clientes** — la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes** — el expediente de cada puerta tocada, desde el primer toque hasta el cobro: programa, formulario, términos, firma y adjuntos.
- **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Documentos por revisar, Proyectos, Monitor de técnicos, Mi agenda, Permisos e inspecciones, Facturación y cobros, Proveedores y pagos, Conciliación y rentabilidad, Reportes, Configuración de programas, Equipo, Roles y permisos, Auditoría.

---

## Administración

Revisa lo que manda el vendedor, aprueba o devuelve el expediente, saca el permiso municipal y coordina la instalación.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- **Clientes** — la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes** — el expediente de cada puerta tocada, desde el primer toque hasta el cobro: programa, formulario, términos, firma y adjuntos.
- **Documentos por revisar** *(pendiente)* — la cola de documentos que los vendedores subieron y Administración todavía no revisa.
- **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
- **Monitor de técnicos** — dónde está y qué hace cada técnico en campo, en vivo.
- **Permisos e inspecciones** *(pendiente)* — el permiso municipal y la inspección posterior a la instalación.
- **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
- **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
- **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
- **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Mi agenda, Gastos de campo, Proveedores y pagos, Conciliación y rentabilidad, Configuración de programas, Equipo, Roles y permisos.

---

## Técnico

Instala en sitio. Ve solo los proyectos que tiene asignados y carga sus evidencias y gastos.

Ve Clientes porque necesita el dato del cliente de su proyecto, pero no ve Expedientes: no hace venta ni revisión.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- **Clientes** — la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
- **Mi agenda** *(pendiente)* — las visitas asignadas al técnico que entra, ordenadas por día.
- **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Expedientes, Documentos por revisar, Monitor de técnicos, Permisos e inspecciones, Facturación y cobros, Proveedores y pagos, Conciliación y rentabilidad, Reportes, Configuración de programas, Equipo, Roles y permisos, Auditoría.

---

## Contabilidad

Factura al programa, registra el pago, controla proveedores y cierra la rentabilidad.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- **Clientes** — la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes** — el expediente de cada puerta tocada, desde el primer toque hasta el cobro: programa, formulario, términos, firma y adjuntos.
- **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
- **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
- **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Proveedores y pagos** *(pendiente)* — los proveedores y lo que se les debe.
- **Conciliación y rentabilidad** *(pendiente)* — el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
- **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
- **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Documentos por revisar, Monitor de técnicos, Mi agenda, Permisos e inspecciones, Configuración de programas, Equipo, Roles y permisos.

---

## Gerencia

Mira. No opera: consulta todo el negocio para decidir, sin crear ni modificar.

Todo lo que ve es de lectura. Los permisos que tiene son de consulta y tableros; ningún botón de guardar le va a funcionar.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- **Clientes** — la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes** — el expediente de cada puerta tocada, desde el primer toque hasta el cobro: programa, formulario, términos, firma y adjuntos.
- **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
- **Monitor de técnicos** — dónde está y qué hace cada técnico en campo, en vivo.
- **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
- **Conciliación y rentabilidad** *(pendiente)* — el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- **Reportes** *(pendiente)* — tableros y exportes para contabilidad y gerencia.
- **Auditoría** — el registro de quién hizo qué y cuándo, con el antes y el después.
- **Notificaciones** *(pendiente)* — los avisos por correo y SMS que dispara el sistema.

**No ve:** Documentos por revisar, Mi agenda, Permisos e inspecciones, Gastos de campo, Proveedores y pagos, Configuración de programas, Equipo, Roles y permisos.

---

## Administrador

Configura el sistema: programas, formularios, flujos, usuarios y roles. Ve todo.

**Ve:**

- **Inicio** — tablero de entrada, con el resumen del día según el rol.
- **Clientes** — la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes** — el expediente de cada puerta tocada, desde el primer toque hasta el cobro: programa, formulario, términos, firma y adjuntos.
- **Documentos por revisar** *(pendiente)* — la cola de documentos que los vendedores subieron y Administración todavía no revisa.
- **Proyectos** — la instalación: equipos, checklist técnico y evidencias de obra.
- **Monitor de técnicos** — dónde está y qué hace cada técnico en campo, en vivo.
- **Mi agenda** *(pendiente)* — las visitas asignadas al técnico que entra, ordenadas por día.
- **Permisos e inspecciones** *(pendiente)* — el permiso municipal y la inspección posterior a la instalación.
- **Facturación y cobros** — el invoice al programa de incentivos y el registro del pago recibido.
- **Gastos de campo** *(pendiente)* — lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Proveedores y pagos** *(pendiente)* — los proveedores y lo que se les debe.
- **Conciliación y rentabilidad** *(pendiente)* — el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
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
del PDF, no un límite. Ojo: solo un Administrador puede otorgar el rol de
Administrador, aunque otro rol tenga permiso para administrar usuarios.
