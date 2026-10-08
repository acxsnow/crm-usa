# Qué ve cada perfil en el menú

Generado desde el menú **real** de la aplicación: un script entra con cada
rol y anota lo que aparece. No es una lectura del código, es lo que la
persona ve. Última verificación: 8 de octubre de 2026.

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
> reemplaza al Pipeline y vive dentro de Expedientes.

## Qué cambió desde la primera versión

| Entrada | Cambio | Permiso que la enciende |
|---|---|---|
| **Mi día** | Nueva: el inicio del vendedor, con sus programas, zonas y lo pendiente | `cases.create` |
| **Campañas** | Nueva: campañas de productos por SMS y correo | `notifications.manage` |
| **Checklists de instalación** | Nueva: plantillas del checklist técnico por programa | `checklists.manage` |
| **Agenda** | Antes «Mi agenda» y pendiente. Ya existe; Administración ve la de todos | `dispatch.read_own` o `dispatch.manage` |
| **Documentos por revisar** | Ya existe | `documents.review` |
| **Notificaciones** | Ya existe | `notifications.read_own` o `notifications.manage` |
| **Configuración de programas** | Ya existe, y desde el 8 de octubre también la ve Administración (migración 0023) | `programs.manage` |

---

## Vendedor

Toca puertas en los parques, levanta el expediente, revisa elegibilidad y lo manda a revisión con la firma y los documentos del cliente.

**El expediente ES la puerta**: se abre al tocar, antes de que exista el cliente. Si nadie abre, se guarda como «sin contacto» y listo; nunca se pidió un cliente. Si abren y les interesa, los datos del cliente, el formulario del programa y los adjuntos se llenan dentro del mismo expediente, sin salir a otra pantalla.

**Ve:**

- **Inicio**: tablero de entrada, con el resumen del día según el rol.
- **Clientes**: la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Mi día**: su inicio de trabajo: tocar una puerta, sus programas y zonas, y lo que tiene pendiente.
- **Expedientes**: los suyos, desde el primer toque hasta el cobro: programa, formulario, términos, firma y adjuntos.
- **Gastos de campo** *(pendiente)*: lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Notificaciones**: sus avisos dentro de la aplicación y sus preferencias de correo y SMS.

**No ve:** Campañas, Documentos por revisar, Proyectos, Monitor de técnicos, Agenda, Checklists de instalación, Permisos e inspecciones, Facturación y cobros, Proveedores y pagos, Conciliación y rentabilidad, Reportes, Configuración de programas, Equipo, Roles y permisos, Auditoría.

---

## Administración

Revisa lo que manda el vendedor, aprueba o devuelve el expediente, saca el permiso municipal y coordina la instalación. Desde el 8 de octubre también configura los programas.

**Ve:**

- **Inicio**: tablero de entrada, con el resumen del día según el rol.
- **Clientes**: la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Campañas**: campañas de productos por SMS y correo a clientes y contactos con permiso de mercadeo.
- **Expedientes**: todos, con el tablero por etapa. Ve también las respuestas sensibles del formulario para revisar la elegibilidad.
- **Documentos por revisar**: la cola de documentos que los vendedores subieron y todavía nadie revisa.
- **Proyectos**: la instalación: permiso, orden, checklist técnico, equipos, evidencias y confirmación del acta.
- **Monitor de técnicos**: dónde está y qué hace cada técnico en campo, en vivo.
- **Agenda**: las órdenes de instalación de todos los técnicos, por día.
- **Checklists de instalación**: las plantillas del checklist técnico por programa.
- **Permisos e inspecciones** *(pendiente)*: hoy se manejan dentro de cada proyecto; esta será la vista de todos.
- **Facturación y cobros**: los cobros a los programas, la radicación y las cotizaciones de trabajo particular.
- **Reportes** *(pendiente)*: tableros y exportes para contabilidad y gerencia.
- **Configuración de programas**: programas y sus términos, catálogo de campos, formulario de cada versión (incluido publicarla) y zonas de venta con sus vendedores.
- **Auditoría**: el registro de quién hizo qué y cuándo, con el antes y el después.
- **Notificaciones**: los avisos, sus plantillas y la configuración de envío.

Ve la lista de usuarios (`users.read`) para asignar vendedores a las zonas y filtrar por persona, pero **no administra usuarios**: no invita, no desactiva ni cambia roles.

**No ve:** Mi día, Gastos de campo, Proveedores y pagos, Conciliación y rentabilidad, Equipo, Roles y permisos.

---

## Técnico

Instala en sitio. Ve solo los proyectos que tiene asignados y carga sus evidencias y gastos.

Ve Clientes porque necesita el dato del cliente de su proyecto, pero no ve Expedientes: no hace venta ni revisión.

**Ve:**

- **Inicio**: tablero de entrada, con el resumen del día según el rol.
- **Clientes**: la ficha del cliente: datos, contactos, dirección e historial.
- **Proyectos**: solo los suyos: checklist técnico, equipos instalados, evidencias y cierre del acta.
- **Agenda**: sus órdenes de instalación, ordenadas por día.
- **Gastos de campo** *(pendiente)*: lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Notificaciones**: sus avisos dentro de la aplicación y sus preferencias.

**No ve:** Mi día, Campañas, Expedientes, Documentos por revisar, Monitor de técnicos, Checklists de instalación, Permisos e inspecciones, Facturación y cobros, Proveedores y pagos, Conciliación y rentabilidad, Reportes, Configuración de programas, Equipo, Roles y permisos, Auditoría.

---

## Contabilidad

Cobra a los programas, registra el pago, factura el trabajo particular, controla proveedores y cierra la rentabilidad.

**Ve:**

- **Inicio**: tablero de entrada, con el resumen del día según el rol.
- **Clientes**: la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes**: todos, de consulta.
- **Proyectos**: todos, de consulta, para saber qué está instalado y listo para cobrar.
- **Facturación y cobros**: cobros a los programas (radicación, rechazo, reintento y pago), facturas, cotizaciones y la configuración de cobro de cada programa (tarifas, jurisdicciones y requisitos).
- **Gastos de campo** *(pendiente)*: lo que el vendedor o el técnico gasta en calle, con su soporte, para aprobación.
- **Proveedores y pagos** *(pendiente)*: los proveedores y lo que se les debe.
- **Conciliación y rentabilidad** *(pendiente)*: el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- **Reportes** *(pendiente)*: tableros y exportes para contabilidad y gerencia.
- **Auditoría**: el registro de quién hizo qué y cuándo, con el antes y el después.
- **Notificaciones**: sus avisos dentro de la aplicación y sus preferencias.

**No ve:** Mi día, Campañas, Documentos por revisar, Monitor de técnicos, Agenda, Checklists de instalación, Permisos e inspecciones, Configuración de programas, Equipo, Roles y permisos.

---

## Gerencia

Mira. No opera: consulta todo el negocio para decidir, sin crear ni modificar.

Todo lo que ve es de lectura. Los permisos que tiene son de consulta y tableros; ningún botón de guardar le va a funcionar.

**Ve:**

- **Inicio**: tablero de entrada, con el resumen del día según el rol.
- **Clientes**: la ficha del cliente: datos, contactos, dirección e historial. Al entrar se ven todos sus expedientes.
- **Expedientes**: todos, de consulta.
- **Proyectos**: todos, de consulta.
- **Monitor de técnicos**: dónde está y qué hace cada técnico en campo, en vivo.
- **Facturación y cobros**: los cobros a los programas y el tablero financiero, de consulta.
- **Conciliación y rentabilidad** *(pendiente)*: el cierre: cuadrar lo cobrado contra lo gastado y ver el margen por proyecto.
- **Reportes** *(pendiente)*: tableros y exportes para contabilidad y gerencia.
- **Auditoría**: el registro de quién hizo qué y cuándo, con el antes y el después.
- **Notificaciones**: sus avisos dentro de la aplicación y sus preferencias.

**No ve:** Mi día, Campañas, Documentos por revisar, Agenda, Checklists de instalación, Permisos e inspecciones, Gastos de campo, Proveedores y pagos, Configuración de programas, Equipo, Roles y permisos.

---

## Administrador

Configura el sistema: programas, formularios, flujos, usuarios y roles. Ve todo.

**Ve:**

- **Inicio**, **Clientes**, **Mi día**, **Campañas**, **Expedientes**, **Documentos por revisar**.
- **Proyectos**, **Monitor de técnicos**, **Agenda**, **Checklists de instalación**, **Permisos e inspecciones** *(pendiente)*.
- **Facturación y cobros**, **Gastos de campo** *(pendiente)*, **Proveedores y pagos** *(pendiente)*, **Conciliación y rentabilidad** *(pendiente)*.
- **Reportes** *(pendiente)*, **Configuración de programas**.
- **Equipo**: los usuarios: invitar, activar, desactivar y asignarles rol.
- **Roles y permisos**: crear roles y marcar qué puede hacer cada uno. Es lo que gobierna todo este archivo.
- **Auditoría**, **Notificaciones**.

**No ve:** nada; tiene acceso completo.

---

## Cómo cambiar esto

En *Roles y permisos*: se abre el rol, se marcan o desmarcan permisos y se
guarda. El menú de quien tenga ese rol cambia en su siguiente ingreso. No hace
falta tocar código ni migrar nada, y queda registrado en auditoría.

También se pueden crear roles nuevos desde cero; los seis de arriba son los
del PDF, no un límite. Ojo: solo un Administrador puede otorgar el rol de
Administrador, aunque otro rol tenga permiso para administrar usuarios.

Un permiso **nuevo** (que no existía en el catálogo) sí necesita código y una
migración: sin ella no aparece en *Roles y permisos* para marcarlo. Ver
`docs/PERMISOS.md`.

## Usuarios de prueba

Los crea `python -m scripts.seed --demo-org --demo-users`. Todos con la
contraseña `ChangeMe123!` (solo en desarrollo).

| Rol | Usuario |
|---|---|
| Administrador | `admin@demo-org.com` |
| Vendedor | `vendedor@demo-org.com` |
| Administración | `administracion@demo-org.com` |
| Técnico | `tecnico@demo-org.com` |
| Contabilidad | `contabilidad@demo-org.com` |
| Gerencia | `gerencia@demo-org.com` |
