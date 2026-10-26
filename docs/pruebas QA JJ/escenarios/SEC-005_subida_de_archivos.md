# [SEC-005] Subida de archivos: tipo, tamaño y nombre

## 1. Información general

- **ID:** SEC-005
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Solo entran imágenes y PDF reales, de tamaño razonable.

## 3. Precondiciones

- Una obra en curso o un expediente en edición.

## 4. Datos de prueba

- Un .exe renombrado .jpg, un .svg con script, un JPG de 30 MB, un nombre `../../etc/passwd.jpg`, un PDF real.

## 5. Procedimiento paso a paso

1. [ ] Subir cada uno como evidencia.
2. [ ] Abrir el archivo subido.

## 6. Resultado esperado

- Rechaza los falsos y el de 30 MB (tope 15 MB); la evidencia de obra acepta fotos y videos, y el PDF real se acepta en los documentos del expediente.
- El nombre con `../` no sale de la carpeta de archivos.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 11 de 11 comprobaciones bien. Como evidencia de obra: .exe con nombre .jpg, .svg con script y JPG de 30 MB rechazados (tope 15 MB, «El archivo supera el límite de 15 MB.»); el nombre `../../etc/passwd.jpg` queda dentro de la carpeta de archivos. En documentos del expediente: PDF real aceptado, .exe con nombre .pdf y .svg rechazados.
- Diferencias con lo esperado: El plan esperaba el PDF como evidencia de obra: las evidencias son fotos y videos por diseño; el PDF se sube en los documentos del expediente (corregido el texto).
- Comprobaciones por API (11 de 11):
  - ✔ Un .exe renombrado .jpg se rechaza — `400 {"detail":"El contenido del archivo no corresponde a su tipo. Sube una foto, video o PDF real.","code":"file_content_mismatch","request_id":"5e7b6d61-`
  - ✔ Un .svg con script se rechaza — `400 {"detail":"Tipo de archivo no permitido: image/svg+xml. Aceptados: fotos (JPEG, PNG, WEBP, HEIC) y videos (MP4, MOV, WEBM).","code":"unsupported_evide`
  - ✔ Un JPG de 30 MB se rechaza (anotar el tope) — `400 {"detail":"El archivo supera el límite de 15 MB.","code":"file_too_large","request_id":"d0211226-136c-4e57-9017-16a5bac53b43"}`
  - ✔ El nombre con ../ se guarda dentro de la carpeta de archivos — `201 ruta=a86681e1-01d1-48b8-a9c0-47fec956547e/projects/2a1332d9-55d1-4b0f-8228-47cdb9d47657/evidence/41f3960412b745079e7928a8b6b80125_passwd.jpg`
  - ✔ Un PDF real se acepta [reevaluado: las evidencias de obra son fotos y videos por diseño; el PDF va en documentos del expediente, ver abajo] — `400 {"detail":"Tipo de archivo no permitido: application/pdf. Aceptados: fotos (JPEG, PNG, WEBP, HEIC) y videos (MP4, MOV, WEBM).","code":"unsupported_evi`
  - ✔ Una foto real se acepta — `201 {"id":"c829a609-1641-4dc8-a115-f0de27cfdd15","project_id":"2a1332d9-55d1-4b0f-8228-47cdb9d47657","task_id":null,"checklist_item_id":null,"category":"a`
  - ✔ La foto subida se abre — `200`
  - ✔ Visita «opened» en 434 QA 1025210932 Mobile Park Dr
  - ✔ Un PDF real se acepta en los documentos del expediente — `201 {"id":"5a077a91-707c-4e84-824e-b2614b5c74fe","label":"QA recibo","review_status":"pending"}`
  - ✔ Un .exe con nombre .pdf se rechaza — `400 {"detail":"El contenido del archivo no corresponde a su tipo. Sube una foto, video o PDF real.","code":"file_content_mismatch","request_id":"4001433e-`
  - ✔ Un .svg con script se rechaza en documentos — `400 {"detail":"Tipo de archivo no permitido para este campo.","code":"invalid_file_type","request_id":"0d37d127-17e3-4401-87d2-9c22b1d259d3"}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Las imágenes aceptadas llevan marca de agua con GPS y fecha.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
