"""Autorización de tratamiento de datos personales (aviso al momento de la captura).

El cliente autoriza —y queda constancia de— que se guarden su nombre, teléfono,
correo y dirección. El texto va versionado y se guarda completo en cada fila
(`DataConsent.document_text`): la constancia tiene que ser la misma que el
cliente vio, aunque después cambie el texto.

Está redactado con lo que exigen las zonas donde trabaja la empresa:

- **California (CCPA/CPRA):** «aviso al momento de la recolección» — categorías
  de datos, para qué se usan, con quién se comparten, cuánto se conservan y los
  derechos del consumidor (conocer, corregir, borrar, oponerse a la venta), sin
  discriminación por ejercerlos.
- **Nevada (SB 220 y SB 370):** posibilidad de oponerse a la venta de datos y
  consentimiento previo y expreso para los datos de salud del consumidor.
- **Arizona:** no tiene ley integral de privacidad; aplica la notificación de
  brechas (A.R.S. § 18-552), así que se ofrecen los mismos derechos.
- **TCPA (federal), para las zonas con código de área de EE. UU.:** el
  consentimiento para llamadas o mensajes de texto **de publicidad** no puede
  ser condición para contratar, por eso se advierte aparte y no se pide aquí.
"""

from datetime import datetime, timezone

from app.modules.crm.models import DataConsent
from app.shared.errors import InvalidInputError

# De dónde salió la autorización (`data_consents.source`).
SOURCE_CUSTOMER_CREATE = "customer_create"      # alta de cliente
SOURCE_CUSTOMER_UPDATE = "customer_update"      # edición de datos de contacto
SOURCE_CASE_INTAKE = "case_intake"              # expediente de venta
SOURCE_PUBLIC_SIGNATURE = "public_signature"    # firma del cliente por enlace

DOCUMENT_VERSION = "2026.1"
DOCUMENT_LANGUAGE = "es"

DOCUMENT_TITLE = "Autorización de tratamiento de datos personales"

# La etiqueta del aviso cuando lo marca el vendedor frente al cliente. La
# página pública de firma usa otra, en primera persona.
DOCUMENT_LABEL = "El cliente autorizó el tratamiento de sus datos personales"

DOCUMENT_BODY = """Autorizo a la empresa que me presta este servicio a recolectar, usar, guardar y compartir mis datos personales para atender mi solicitud, verificar si califico y ejecutar el trabajo.

1. Datos que se recolectan. Nombre completo, teléfono, correo electrónico, dirección del servicio (calle, unidad, ciudad, estado y código postal), la ubicación del domicilio, fotografías de la propiedad y del documento de identidad que entrego, y los datos técnicos del hogar que se registren en la visita.

2. Para qué se usan. (a) Verificar si califico y radicar mi solicitud ante el programa o la entidad que financia la obra; (b) coordinar la visita técnica, la instalación y el servicio posterior; (c) cumplir obligaciones legales, contables, de garantía y de auditoría del programa; y (d) atender reclamos.

3. Con quién se comparten. Con el programa, su administrador o la entidad que paga la obra; con los contratistas e instaladores que ejecutan el trabajo; y con los proveedores de tecnología que custodian la información. Mis datos no se venden ni se comparten con fines publicitarios.

4. Cuánto tiempo se conservan. Mientras dure la relación de servicio y hasta siete (7) años después, para atender auditorías, contabilidad y garantías. Los datos de elegibilidad se conservan el mismo plazo y solo se usan para verificar el beneficio.

5. Mis derechos. Puedo pedir acceso, una copia, corrección o eliminación de mis datos, y pedir que no se compartan, en la oficina donde solicité el servicio o con quien me atendió. No se me negará el servicio ni se me cobrará distinto por ejercer estos derechos, que aplican si vivo en California, Arizona o Nevada.

6. Lo que esta autorización no cubre. No me obliga a recibir llamadas ni mensajes de texto de publicidad: la empresa no envía mensajes automáticos ni promocionales sin un consentimiento aparte, y puedo retirar esta autorización en cualquier momento.

7. Constancia. Se guarda una copia de este texto con su versión, la fecha y hora, la dirección IP, el equipo desde el que se firmó y la firma de quien autoriza."""


def notice() -> dict[str, str]:
    """El aviso vigente, tal como se muestra y como se guarda."""
    return {
        "version": DOCUMENT_VERSION,
        "language": DOCUMENT_LANGUAGE,
        "title": DOCUMENT_TITLE,
        "label": DOCUMENT_LABEL,
        "body": DOCUMENT_BODY,
    }


def require_consent(accepted: bool) -> None:
    """Sin autorización no se guardan datos personales del cliente."""
    if not accepted:
        raise InvalidInputError(
            "Falta la autorización de tratamiento de datos personales del cliente: márcala antes de guardar.",
            code="consent_required",
        )


def contact_snapshot(**datos) -> dict:
    """Lo que se capturó en ese momento, sin campos vacíos."""
    return {clave: valor for clave, valor in datos.items() if valor not in (None, "")}


def address_line(*partes) -> str | None:
    """«1200 W Sunrise Dr, Spc 14, San Fernando, CA 91340» o lo que haya."""
    return ", ".join(str(p).strip() for p in partes if p not in (None, "")) or None


async def record_consent(
    db, *, organization_id, source: str, snapshot: dict | None = None, customer_name: str | None = None,
    customer_id=None, case_id=None, captured_by_user_id=None, ip_address: str | None = None,
    user_agent: str | None = None, latitude: float | None = None, longitude: float | None = None,
) -> DataConsent:
    """Deja la constancia. Es una fila nueva cada vez: el historial no se
    reescribe (así se puede probar quién autorizó, qué texto vio y cuándo)."""
    fila = DataConsent(
        organization_id=organization_id,
        source=source,
        customer_id=customer_id,
        case_id=case_id,
        customer_name=(customer_name or "").strip() or None,
        contact_snapshot=snapshot or None,
        document_version=DOCUMENT_VERSION,
        document_language=DOCUMENT_LANGUAGE,
        document_text=DOCUMENT_BODY,
        accepted_at=datetime.now(timezone.utc),
        captured_by_user_id=captured_by_user_id,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(fila)
    return fila
