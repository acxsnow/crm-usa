# Manejo de errores — Guía de referencia

Cómo se expresan los fallos en el backend, qué ve el usuario y cómo se
diagnostica un problema reportado.

## Las dos reglas

1. **Lo interno no sale.** El traceback, la consulta SQL, la ruta del servidor
   y el mensaje de una librería van al log. La respuesta lleva un texto que una
   persona pueda entender, en español.
2. **Todo error se puede rastrear.** Cada respuesta incluye `request_id`. Si
   alguien reporta "me salió un error", se pide ese código y se busca en el log
   para encontrar el fallo exacto, con usuario, organización y traza completa.

## Formato de respuesta

Todos los errores tienen la misma forma, sin importar de dónde vengan:

```json
{
  "detail": "El prospecto no existe.",
  "code": "lead_not_found",
  "request_id": "b3f1c2e4-..."
}
```

- `detail` — para mostrarle al usuario. Siempre texto, siempre español.
- `code` — estable y legible por máquina. El frontend puede reaccionar a un
  caso concreto (`last_admin`, `plan_limit_reached`) sin comparar textos, que
  cambian.
- `request_id` — el de la petición. También va en el header `X-Request-ID`.

Los errores de validación agregan `errors`, con el detalle por campo:

```json
{
  "detail": "Hay datos inválidos en: email, password.",
  "code": "validation_error",
  "request_id": "b3f1c2e4-...",
  "errors": [
    {"field": "email", "message": "value is not a valid email address"},
    {"field": "password", "message": "Field required"}
  ]
}
```

## Cómo se lanza un error (desarrollo)

Los services y selectors lanzan **excepciones de dominio**
(`app/shared/errors.py`). No saben de HTTP:

```python
from app.shared.errors import ConflictError, NotFoundError

async def get_case_or_404(db, organization_id, case_id):
    case = ...
    if case is None:
        raise NotFoundError("El expediente no existe.", code="case_not_found")
    return case
```

Las clases y el código HTTP al que se traducen:

- `AuthenticationError` → 401. No hay sesión válida.
- `ForbiddenError` → 403. Hay sesión y permiso de módulo, pero esta instancia
  concreta no es suya ("puedes ver expedientes, pero no este").
- `NotFoundError` → 404. No existe, **o es de otra organización**: se responde
  igual en ambos casos para no revelar qué identificadores están en uso.
- `ConflictError` → 409. Choca con el estado actual: código repetido, rol en
  uso, último administrador.
- `InvalidInputError` → 400. Los datos llegaron bien formados pero no sirven
  para esta operación. Es una regla de negocio, distinta de la validación de
  esquema que resuelve Pydantic con un 422.

Ventajas de no usar `HTTPException` en la capa de negocio:

- Un service se prueba sin levantar la API: el test afirma `NotFoundError`, no
  un 404.
- El mismo service se puede llamar desde una tarea de Celery o un script,
  donde un `HTTPException` no significaría nada.
- El mensaje se escribe una sola vez, en el lugar donde se conoce la regla.

`HTTPException` sigue funcionando y devuelve el mismo formato: los módulos de
la Cadena B todavía lo usan y no hay prisa por migrarlos.

## Qué pasa con lo que no se previó

`app/shared/error_handlers.py` es el único sitio que traduce fallos a
respuestas. Además de las excepciones de dominio, atrapa:

- **`IntegrityError`** → 409. Una restricción de la base saltó, casi siempre
  por dos operaciones simultáneas creando el mismo registro. Antes esto era un
  500 con el SQL en la respuesta.
- **`SQLAlchemyError`** → 500 neutro, con el error completo en el log.
- **Cualquier otra excepción** → 500 neutro. Es la red de seguridad: el
  traceback queda en el log con ruta, método, usuario y organización; el
  usuario recibe "Ocurrió un error inesperado" y el código de referencia.

## Cómo investigar un error reportado

1. Pedirle al usuario el código de referencia (el `request_id` que salió en
   pantalla).
2. Buscarlo en el log: todas las líneas de esa petición lo llevan.
3. El evento `unhandled_error` trae `error_type`, `error`, `path`, `method`,
   `user_id`, `organization_id` y la traza completa.

Si la acción modificó datos, también quedó en `audit_events` con ese mismo
`request_id`, más la IP y el navegador. Ver `docs/PERMISOS.md`.

## Degradación de servicios

Cuando Redis no responde, el control de intentos de login y la revocación de
tokens **siguen funcionando en memoria**, por proceso. Es a propósito: es
preferible a bloquear el acceso. Pero con varios workers dejan de ser
compartidos, así que un token revocado puede seguir siendo aceptado por otro
worker hasta que expire.

Eso queda registrado como `redis.unavailable` (una sola vez, no en cada
reintento) con el impacto explicado, y como `redis.recovered` al volver. Antes
se silenciaba con `except Exception: pass` y nadie se enteraba.

## Cosas que se arreglaron al montar esto (23 de septiembre de 2026)

- No existía ningún manejador global: cualquier fallo no controlado producía un
  500 sin log estructurado y sin forma de correlacionarlo.
- `storage.py` lanzaba `ValueError` ante un intento de salir del directorio de
  la organización, lo que salía como 500. Un intento de path traversal
  respondía "error del servidor" y quedaba invisible.
- Nadie capturaba `IntegrityError`.
- El middleware enlazaba el `request_id` al contexto de logging pero **nunca lo
  limpiaba**: las líneas de una petición podían salir con el identificador de
  otra.
- `audit_events` tenía columnas para `request_id`, `ip_address` y `user_agent`
  desde el principio y solo se llenaban en una llamada de todo el proyecto.
  Ahora el middleware las deja en el contexto y la auditoría las toma sola.
- Los mensajes estaban mezclados en inglés y español, con la UI en español.
- El cliente de pruebas re-lanzaba las excepciones en vez de devolver el 500,
  así que **ningún test veía lo que ve el usuario** ante un fallo inesperado.
