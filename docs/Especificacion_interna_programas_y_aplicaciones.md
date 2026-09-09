# Especificación interna — Aplicaciones por programa

## Objetivo

Convertir el alta del cliente en una aplicación controlada. El vendedor
captura y firma con el cliente; administración revisa, corrige y somete; el
proyecto técnico solo se habilita cuando la aplicación queda aprobada.

## Estados de la aplicación

`Borrador` → `Pendiente de revisión` → `Corrección solicitada` → `Lista para
someter` → `Sometida` → `Aprobada` / `Rechazada`.

Una aplicación aprobada puede crear o activar un proyecto. Una aplicación
rechazada no debe crear trabajo técnico automáticamente.

## Checklist general del vendedor

- Datos del cliente completos.
- Datos de la vivienda completos.
- Programa seleccionado.
- Preguntas obligatorias respondidas.
- Documentos obligatorios cargados.
- Fotografías obligatorias cargadas.
- Términos y Condiciones aceptados.
- Firma del cliente capturada.
- Firma del vendedor capturada.

El sistema debe impedir el envío a revisión si falta un requisito obligatorio y
debe indicar exactamente qué falta.

## Perfil de cada programa

Cada programa se configura con:

- Código y nombre.
- Versión vigente del formulario.
- Campos, tipo de campo y obligatoriedad.
- Opciones de respuesta.
- Documentos y fotografías requeridos.
- Reglas de validación.
- Estados administrativos permitidos.
- Texto de T&C y versión legal.
- Tipo de invoice asociado.

## Invoice templates

Se soportarán como mínimo dos plantillas base:

### Reembolso o incentivo

Cliente, dirección, programa, conceptos elegibles, monto total, rebate,
balance, documentos de soporte y datos del financiador.

### Instalación o servicio

Job, invoice, fechas, términos de pago, empresa, cliente, técnicos, contacto,
alcance de trabajo, materiales, mano de obra, permisos, requisitos técnicos y
balance.

Cada programa podrá extender una plantilla base sin perder los campos comunes.

## Seguridad y auditoría

Los documentos, fotos, firmas y T&C pertenecen a la aplicación y deben estar
protegidos por organización y rol. Toda edición, revisión, solicitud de
corrección, cambio de estado y sometimiento debe quedar en auditoría.

Los datos regulatorios definitivos solo se activan después de validar el
formulario vigente entregado por el programa correspondiente.
