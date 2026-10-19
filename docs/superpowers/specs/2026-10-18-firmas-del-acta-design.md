# Firmas del acta como paso propio — Diseño

**Fecha:** 18 de octubre de 2026 · **Pidió:** José Javier (recorrido manual como técnico)

## Problema

1. Las firmas del acta (técnico y cliente) están en «Anexos», mezcladas con evidencias y tareas, y no se entiende en qué momento van.
2. Para ver que el cliente ya firmó por el enlace hay que recargar la página.
3. Muchos clientes, en zonas rurales y de bajos recursos, no tienen correo ni internet. Hoy la pantalla solo ofrece «Enviar enlace de firma».
4. Al guardar los equipos, nada invita a seguir con las firmas.

## Lo que ya existe

- `POST /projects/{id}/attestation/technician-sign`, `.../customer-signature-request` (enlace por correo), `.../customer-sign` (firma en el dispositivo del técnico, con nombre) y la página pública del enlace. El PDF del acta se genera cuando firman los dos.
- La firma no bloquea el cierre ni el cobro. **Esto no cambia** en este diseño; si debe bloquear se decide con Mariana.
- Al completar un paso, el acta abre sola el siguiente (`ActaSteps`).

## Huecos que se cierran

- **Aislamiento por técnico:** firmar, pedir el enlace y ver el acta solo filtran por organización. Un técnico puede firmar una orden que no es suya. Pasan a usar `get_visible_project`, igual que el resto de `field_ops`.
- **Firma reescribible:** volver a firmar reemplaza la firma anterior. Ahora responde 409 si ya hay firma.

## Diseño

### API

- `AttestationResponse` agrega `customer_link_sent_to` y `customer_link_expires_at`, del enlace pendiente (sin firmar, sin revocar y sin vencer). Así la pantalla sabe, después de recargar, que el enlace ya se envió.
- `customer-sign` (en el celular del técnico) deja `{"method": "in_person"}` en la auditoría, para distinguirla de la del enlace.
- Firmar dos veces devuelve 409 (`already_signed`).
- Las cuatro rutas del acta pasan por `get_visible_project`.

### Pantalla

- **Nuevo paso 5, «Firmas del acta»**, entre «Equipos instalados» y «Cierre de la instalación». Sale de Anexos, que quedan con evidencias y tareas.
  - Se completa cuando firman los dos. Su resumen dice qué falta: «Falta la firma del cliente», «Firmada por los dos».
  - No bloquea el cierre: es el paso actual mientras falte, pero el cierre sigue disponible.
- **Técnico:** recuadro de firma, como hoy.
- **Cliente:** dos caminos.
  1. «Enviar enlace por correo». Si ya se envió, muestra a quién y hasta cuándo, con el botón **«Consultar si ya firmó»**, que vuelve a pedir el acta y dice «Todavía no ha firmado» o muestra la firma.
  2. «El cliente no tiene correo o internet: firmar en este celular». Abre el nombre (precargado con el del cliente) y el recuadro de firma.
- **Invitación:** al guardar los equipos, el aviso dice «Equipos instalados guardados. Sigue con las firmas del acta.». El paso de firmas se abre solo y la pantalla baja hasta él.

## Fuera de alcance

- Exigir las firmas para cerrar o cobrar.
- Avisos en tiempo real (sockets).

## Paquetes de Mateo

`field_ops` (servicio, router, esquemas y pantallas del acta). Hay que avisarle.
