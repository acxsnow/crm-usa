# [VEN-004] Venta completa: abrió, formulario, autorización, firma y envío

## 1. Información general

- **ID:** VEN-004
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 35 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 12 de 12 comprobaciones bien.
- Diferencias con lo esperado: Falta la parte del celular (390 px), ver la marca de agua en las fotos y el aviso de la campana en pantalla.
- Comprobaciones por API (12 de 12):
  - ✔ Visita «opened» en 121 QA 1025164900 Mobile Park Dr
  - ✔ Enviar incompleto se rechaza
  - ✔ Formulario lleno, salvo la firma (10 archivos con GPS) — `[]`
  - ✔ Cliente acepta términos y firma
  - ✔ Puede enviarse — `[]`
  - ✔ Enviar a revisión
  - ✔ Queda en Pendiente aprobación · en revisión — `('pending_approval', 'pending_review')`
  - ✔ Editar después de enviar se bloquea
  - ✔ El cliente quedó creado — `ac9f2701-74fe-4d57-9567-6d12e09593da`
  - ✔ data_consents tiene la autorización con versión e IP — `1|2026.1|True`
  - ✔ Los archivos del formulario quedaron con GPS (total|con GPS) — `10|10`
  - ✔ Administración recibe el aviso del expediente enviado — `1`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
