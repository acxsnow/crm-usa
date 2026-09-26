"""Excepciones de dominio.

La capa de servicios expresa qué salió mal en términos del negocio —"este
expediente no existe", "ese código ya está en uso"— sin saber nada de HTTP.
Los manejadores de `app/shared/error_handlers.py` son los únicos que traducen
eso a códigos de estado.

Sirve para tres cosas:

- Un service se puede probar sin levantar la API: el test afirma
  `NotFoundError`, no un 404.
- El mismo service se puede llamar desde una tarea de Celery o un script,
  donde un `HTTPException` no significaría nada.
- El mensaje que se escribe aquí es el que ve el usuario, así que se escribe
  una vez, en español, y no se repite en cada endpoint.

Ver `docs/ERRORES.md`.
"""


class DomainError(Exception):
    """Base de los errores esperables del negocio.

    `message` es para el usuario final y sale en la respuesta. `code` es
    estable y legible por máquina, para que el frontend pueda reaccionar a un
    caso concreto sin comparar textos traducibles."""

    default_code = "domain_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code


class NotFoundError(DomainError):
    """Lo que se pidió no existe, o no pertenece a esta organización.

    Se usa también cuando el recurso existe pero es de otra organización: al
    cliente se le responde igual que si no existiera, para no revelar qué
    identificadores están en uso."""

    default_code = "not_found"


class ConflictError(DomainError):
    """La operación choca con el estado actual: un código repetido, un rol en
    uso, una factura que ya fue pagada."""

    default_code = "conflict"


class InvalidInputError(DomainError):
    """Los datos llegaron bien formados pero no sirven para esta operación.

    Distinto de la validación de esquema (que Pydantic resuelve con un 422):
    esto es una regla de negocio, como "no se puede firmar sin aceptar los
    términos"."""

    default_code = "invalid_input"


class AuthenticationError(DomainError):
    """No hay sesión válida: falta el token, venció o fue revocado.

    Distinto de `ForbiddenError`: aquí no sabemos quién es el usuario; allí sí,
    pero no puede hacer esa operación."""

    default_code = "unauthenticated"


class ForbiddenError(DomainError):
    """El usuario está autenticado y tiene el permiso del módulo, pero esta
    instancia concreta no es suya.

    La autorización gruesa la resuelve `require_permission`; esta es la fina:
    "puedes ver expedientes, pero no este"."""

    default_code = "forbidden"
