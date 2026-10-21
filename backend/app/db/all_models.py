"""Importa todos los modelos para que SQLAlchemy pueda resolver las relaciones
por nombre ("Program", "Case"…). La app web los carga al importar sus rutas;
los procesos que no cargan rutas (worker de Celery, scripts) importan este
módulo. Sin él, la primera consulta del worker fallaba con «failed to locate a
name ('Program')» (lo encontró el QA del 7 de octubre de 2026)."""
from app.modules.organizations import models as _organizations  # noqa: F401
from app.modules.users import models as _users  # noqa: F401
from app.modules.crm import models as _crm  # noqa: F401
from app.modules.cases import models as _cases  # noqa: F401
from app.modules.programs import models as _programs  # noqa: F401
from app.modules.field_ops import models as _field_ops  # noqa: F401
from app.modules.billing import models as _billing  # noqa: F401
from app.modules.notifications import models as _notifications  # noqa: F401
from app.modules.finance import models as _finance  # noqa: F401
from app.modules.warehouse import models as _warehouse  # noqa: F401
from app.shared import audit_models as _audit  # noqa: F401
