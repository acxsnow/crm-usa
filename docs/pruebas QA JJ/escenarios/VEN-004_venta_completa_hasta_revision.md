# [VEN-004] Venta completa: abrió, formulario, autorización, firma y envío

## 1. Información general

- **ID:** VEN-004
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 35 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El camino principal del negocio: la puerta que abre termina en revisión con todo lo que el programa exige.

## 3. Precondiciones

- Sesión de Vicky en celular o a 390 px.
- Permiso de ubicación del navegador concedido.

## 4. Datos de prueba

- Puerta: dirección «201 QA Mobile Park Dr», espacio «Spc 21», Phoenix, AZ, 85006.
- Cliente «QA Venta Rivera», teléfono (602) 555-0201, correo qa.rivera@example.com.
- Programa: Eficiencia de Arizona.
- Fotos: cualquier JPG del teléfono (no PDF falsos).

## 5. Procedimiento paso a paso

1. [ ] Tocar una puerta con la dirección y resultado **Abrió y sigue**, programa Arizona.
2. [ ] En el formulario llenar cada paso con los datos del cliente; tocar **Guardar y seguir** en cada uno.
3. [ ] Subir las fotos que pide cada paso (identificación, panel, equipos…).
4. [ ] Dejar a propósito un campo obligatorio vacío y tratar de seguir: anotar el mensaje.
5. [ ] Completarlo. En el último paso leer los términos y el **aviso de tratamiento de datos**.
6. [ ] Tratar de firmar sin marcar la autorización: anotar el mensaje.
7. [ ] Marcar la autorización, escribir el nombre y firmar con el dedo; guardar.
8. [ ] Tocar **Enviar a revisión**.
9. [ ] Abrir el expediente: ya no debe dejar editar.

## 6. Resultado esperado

- Sin un obligatorio no deja avanzar y dice qué falta.
- Sin la autorización no deja firmar ni enviar.
- Al enviar pasa a «Pendiente de aprobación» con el contador de días hábiles en 0.
- El cliente queda creado en Clientes.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `data_consents` tiene una fila para este cliente con versión del aviso, IP y GPS.
- [ ] Las fotos llevan la marca de agua con GPS y fecha.
- [ ] Administración recibe el aviso en la campana.

## 10. Resultado final

- [ ] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
