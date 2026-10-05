# Módulo 2 — Fase del vendedor: visitas, formulario, T&C, firma y envío

Fecha: 4 de octubre de 2026. Cadena A, desarrollado por Mateo (cubre a José).
Base: `cronograma-cadena-a.md` (módulo 2, opción A sin offline),
`requerimientos-formularios-programas-delta-hvac.md` §3.5, §9, §13 y §18.2, y
`decisiones.md` D2, D3 y D6. Entrega planeada: 13 de noviembre de 2026.

## 1. Lo que ya existe

- Expediente (`Case`) con etapas, `create_case()` y `transition()` (José).
- Módulo 1: programas, formulario versionado, términos y el motor
  `programs/engine.py` que dice qué se ve, qué falta y qué está mal; el
  componente `FormRenderer` del frontend que dibuja cualquier paso.
- Archivos comunes con marca de agua de GPS y fecha (`shared/files`).

## 2. Decisiones

### D2.1 — Cada puerta es un expediente; cada toque, un registro (D6)

`POST /visits` recibe la dirección, el GPS y el resultado (`no_contact`,
`not_interested`, `not_eligible`, `opened`). Busca un expediente **abierto** de
esa puerta (dirección normalizada + unidad) en la organización: si existe lo
reutiliza; si no, lo crea en la etapa del resultado. Un expediente en cierre
temprano se reabre si la puerta luego responde. Si la puerta ya va más
adelante (aprobada, instalada…), la visita se registra y se avisa.

### D2.2 — Respuestas inmutables por paso (D3)

`case_step_submissions`: cada vez que el vendedor guarda un paso queda un
registro con las respuestas, la versión del formulario, quién, cuándo y GPS.
Lo vigente es el último por paso; los anteriores son historial (§13). La
visita también es un registro (`step_code = "__visit__"`).

### D2.3 — Escritura híbrida

Los campos con destino (`binding`) se copian a datos reales: nombre, teléfono y
correo al cliente (se reutiliza uno existente con el mismo teléfono) y la
dirección al expediente. El resto vive solo en las respuestas del paso.

### D2.4 — El programa y su versión se fijan al elegirlo

Mientras el expediente está en "Nuevo prospecto", el vendedor elige el
programa; se fija la **versión publicada** de ese momento y ya no cambia.

### D2.5 — Fotos, documentos y videos van al expediente

`case_files`: el archivo se sube aparte (con validación de tipo y tamaño y
marca de agua de GPS y fecha en fotos y videos) y la respuesta guarda su
identificador. Es la base del módulo 3 (documentos), no otra capa.

### D2.6 — Términos y firma, separados del vendedor (§3.5, §13)

`case_terms_acceptances`: qué versión e idioma de los términos aceptó el
cliente, su nombre, la firma dibujada, fecha y hora, GPS, IP y dispositivo,
y el vendedor autenticado que lo acompañó. Aceptar escribe además el paso de
autorización (casilla, firma y fecha) para que el motor lo dé por completo.

### D2.7 — No se envía con algo pendiente

`POST /cases/{id}/submit` evalúa todas las respuestas con el motor; si falta
algo responde 400 con la lista exacta. Si está completo, pasa a "Pendiente
aprobación" (`cases.submit`, la regla de SEG-07 sigue). Se edita en "Nuevo
prospecto" y en "Pendiente aprobación" solo si Administración lo devolvió
(sub-estado `returned`); al reenviar vuelve a `pending_review`.

### D2.8 — Sin captura sin conexión en esta versión (opción A)

La decisión A/B sigue pendiente con el cliente. Esta versión necesita señal;
guarda paso a paso, así que una caída a mitad del formulario no pierde lo ya
guardado.

## 3. API

| Ruta | Permiso |
|---|---|
| `POST /visits` | `cases.create` |
| `PUT /cases/{id}/program` | `cases.create` (dueño) |
| `GET /cases/{id}/form` | `cases.read_own` / `cases.read_all` |
| `PUT /cases/{id}/steps/{step_code}` | `cases.create` (dueño) |
| `POST /cases/{id}/files`, `GET /case-files/{id}` | `cases.create` / lectura |
| `POST /cases/{id}/terms-acceptance` | `cases.create` (dueño) |
| `POST /cases/{id}/submit` | `cases.submit` (dueño) |
| `GET /cases/board` | `cases.read_own` / `cases.read_all` |

## 4. Pantallas

- **Inicio del vendedor**: sus programas y zonas; botón grande "Tocar puerta".
- **Visita**: dirección (con GPS del teléfono) y resultado en botones grandes.
- **Formulario**: paso a paso con el `FormRenderer`, cámara para fotos, firma
  en pantalla, resumen y "Enviar a revisión" que dice qué falta.
- **Expedientes**: kanban por etapa (sin los cierres tempranos por defecto);
  reemplaza la pantalla del modelo anterior (`/applications`).

## 5. Pruebas

Visita nueva, puerta repetida (mismo expediente), reapertura de un cierre
temprano, puerta ya aprobada; programa y versión fijados; respuestas
inmutables con historial; bindings a cliente y expediente, cliente existente
por teléfono; archivo con tipo inválido y tamaño; términos y firma; envío
bloqueado con la lista de faltantes y envío correcto; devolución y reenvío;
dueño (otro vendedor recibe 404) y aislamiento por organización; tablero.
