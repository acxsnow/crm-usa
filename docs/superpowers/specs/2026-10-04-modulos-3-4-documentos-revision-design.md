# Módulos 3 y 4: documentos del expediente y revisión de Administración

Fecha: 4 de octubre de 2026. Cadena A, desarrollado por Mateo (cubre a José).
Parte de lo que dejó el módulo 2 (`2026-10-04-modulo-2-vendedor-design.md`):
los archivos ya se suben al formulario como `case_files`; aquí se revisan y se
decide el expediente.

## Módulo 3: documentos

### D3.1: Validación común de archivos (cierra SEG-01 y SEG-02)

`app/shared/files/validation.py` la usan los cuatro puntos de subida
(formulario del expediente, documentos adicionales, evidencias de campo y
adjuntos de factura):

- `read_limited()` lee por partes y corta apenas el archivo pasa del límite
  (antes se leía entero en memoria y después se medía).
- `check_type()` exige que el tipo declarado esté permitido **y** que el
  contenido sea de esa familia, por sus primeros bytes (JPEG, PNG, WEBP, HEIC,
  PDF, MP4/MOV, WEBM). Un ejecutable renombrado `foto.jpg` se rechaza.

### D3.2: Estado de revisión por archivo

`case_files` gana `review_status` (`pending`, `accepted`, `rejected`),
`review_notes`, `reviewed_by_user_id`, `reviewed_at` y `label` (solo para
documentos adicionales). Migración `0019`. No se borra nada: un archivo
rechazado queda; el vendedor sube otro y el nuevo entra como pendiente.

### D3.3: Documentos vigentes

De cada campo cuenta solo el archivo que tiene guardado la respuesta vigente
del paso; los reemplazados salen de la lista y de la revisión. Los adicionales
(`field_key = "__extra__"`) cuentan todos.

### D3.4: Reglas

- Rechazar exige una nota: el vendedor la ve en su expediente.
- Se revisa solo en «Pendiente de aprobación» o «En espera» (`documents.review`).
- Un documento adicional lo sube quien tenga `documents.manage` mientras el
  expediente no esté cerrado.
- El vendedor no puede reenviar con documentos rechazados vigentes.
- **Guarda nueva:** `pending_approval → approved` y `on_hold → approved` exigen
  que no haya documentos pendientes ni rechazados (`cases/documents.py`,
  registrada en `app/main.py`). Un expediente sin archivos no se bloquea.

### Rutas

| Ruta | Permiso |
|---|---|
| `GET /cases/{id}/documents` | `cases.read_own` / `cases.read_all` |
| `POST /cases/{id}/documents` (adicional) | `documents.manage` |
| `POST /case-files/{id}/review` | `documents.review` |
| `GET /documents/review-queue` | `documents.review` |

## Módulo 4: revisión de Administración

No hizo falta tocar el motor: las transiciones (`approved`, `rejected`,
`on_hold`), los sub-estados y sus permisos (`SUBSTATUS_PERMISSION`) ya estaban.
Es la pantalla `/cases/{id}/review`:

- Documentos agrupados por paso, con miniatura, GPS, fecha y aceptar o
  rechazar con nota.
- Lo que respondió el cliente (el mismo `FormRenderer`, sin editar) y la firma.
- Avance con el programa: En revisión → Listo para el programa → Sometido al
  programa → En revisión del programa.
- Decisión: aprobar (código de aprobación y número de solicitud), devolver al
  vendedor (con lo que debe corregir), poner en espera o rechazar.
- Historial del expediente desde `case_stage_events`.

El tablero de Expedientes abre esta pantalla para quien revisa
(`cases.review` o `cases.approve`) y el formulario para el vendedor. «Documentos
por revisar» (`/documents`) lista los expedientes con algo pendiente, los más
antiguos primero.

## Lo que José debe saber

- La guarda de documentos se suma a las de la Cadena B en la aprobación: si
  una prueba aprueba un expediente con archivos sin revisar, ahora falla con
  `documents_pending`.
- `form_state` devuelve `review_status` y `review_notes` en cada archivo.
- Las pruebas que limpian el registro del motor deben llamar a
  `documents._reset_for_tests()` igual que a `case_hooks._reset_for_tests()`.
