"""El expediente y su historial.

`Case` es **la puerta**, no la venta: nace cuando el vendedor toca, no cuando
alguien dice que sí. Por eso `customer_id` es nulo hasta que abren y dan sus
datos, y las tres primeras etapas (`no_contact`, `not_interested`,
`not_eligible`) existen sin que haya cliente.

Todo el flujo del PDF cuelga de aquí: los módulos 2 y 3 lo llenan, el 4 lo
revisa, el 5 lo instala, el 6 lo cobra.

Lo que NO vive en `Case` y dónde está, para no duplicarlo:

- Respuestas del formulario → `step_submissions` (módulo 2).
- T&C y firma del cliente → `case_terms_acceptances` (módulo 2).
- Documentos y fotos → `case_documents` (módulo 3).
- Evidencias de instalación, permiso, equipos → módulo 5.
- Invoices → `invoices.case_id` (módulo 6).
- Técnico asignado → `Project` (módulo 5). Tenerlo también aquí crearía dos
  verdades que se desincronizan en cada reasignación.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID
from app.modules.crm.models import PropertyAddressMixin


class Program(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Programa de incentivos (Eficiencia de Arizona, TECH Clean California…).

    Mínimo a propósito: el catálogo completo, sus campos y sus reglas los llena
    el módulo 1. Aquí solo lo indispensable para que un `Case` pueda apuntar a
    uno y para que Mateo enganche `ChecklistTemplate` e `InvoiceTemplate`."""

    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_program_org_code"),)

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Plantilla compartida entre organizaciones, como los roles del sistema.
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProgramVersion(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Versión del formulario y del flujo de un programa.

    Nace vacía: la llena el módulo 1. Existe desde ahora porque `Case` guarda
    con qué versión nació, y ese dato no se puede reconstruir después."""

    __tablename__ = "program_versions"
    __table_args__ = (
        UniqueConstraint("program_id", "version", name="uq_program_version"),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProgramZone(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Zona geográfica donde aplica un programa (decisión D5).

    Nace vacía; la llena el módulo 1."""

    __tablename__ = "program_zones"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_program_zone_org_code"),
    )

    program_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="SET NULL"), index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)


class Case(UUIDPKMixin, TimestampMixin, OrgScopedMixin, PropertyAddressMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "case_number", name="uq_case_org_number"),
        # Para reconocer la puerta repetida (decisión D6). NO es unique: una
        # propiedad puede tener un expediente cerrado y otro abierto años
        # después. La regla "un solo expediente abierto por propiedad" vive en
        # el service, que sí conoce las etapas.
        Index("ix_case_org_property", "organization_id", "normalized_address", "address_unit"),
        Index("ix_case_org_stage", "organization_id", "stage_code"),
    )

    # Legible para la gente: CASE-2026-0001. Lo genera el service al crear y no
    # se edita nunca; es lo que el vendedor le dice por teléfono a Administración.
    case_number: Mapped[str] = mapped_column(String(30), nullable=False)
    # visit = puerta tocada · import = CSV · manual = lo creó Administración
    # migration = venía del modelo anterior
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="visit")

    # Nulos mientras la puerta no responde: sin cliente no hay programa que elegir.
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="SET NULL"), index=True
    )
    # La versión del flujo con la que nació. Se fija al pasar a `new_prospect` y
    # no cambia: si el programa publica otra versión, este expediente sigue con
    # la suya y las reglas con las que se firmó siguen valiendo.
    program_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("program_versions.id", ondelete="SET NULL"), index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("program_zones.id", ondelete="SET NULL"), index=True
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    assigned_salesperson_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)

    # Calculada con `shared/normalize.py` al guardar, para que "123 Main St." y
    # "123 main street" sean la misma puerta.
    normalized_address: Mapped[str | None] = mapped_column(String(500), index=True)

    stage_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    substatus_code: Mapped[str | None] = mapped_column(String(40))
    # Motivo del último cambio, copiado del último `case_stage_events`. Está
    # duplicado a propósito: el tablero lo muestra en cada tarjeta y no vale la
    # pena una consulta al historial por fila.
    stage_reason: Mapped[str | None] = mapped_column(Text)

    # Los llena Administración (módulo 4).
    application_number: Mapped[str | None] = mapped_column(String(100))
    approval_code: Mapped[str | None] = mapped_column(String(100))
    # Código plano, no FK: `funder_statuses` queda como catálogo de etiquetas.
    # Un join menos en cada consulta y comparable entre organizaciones.
    funder_status_code: Mapped[str | None] = mapped_column(String(50), index=True)

    # Fechas hito. Denormalizadas para no recorrer el historial en cada consulta.
    # **Solo las escribe `transition()`**: si un endpoint las tocara directo, se
    # desincronizarían de `case_stage_events` y los reportes de tiempos del
    # PDF §7 dirían una cosa y el historial otra.
    first_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # La fija el módulo 5 como dato de agenda, no como consecuencia de una etapa.
    scheduled_install_date: Mapped[date | None] = mapped_column(Date)


    @property
    def stage_label(self) -> str:
        """La etiqueta en español de la etapa actual.

        Viaja en la respuesta para que el frontend no repita el diccionario de
        etapas ni se desactualice cuando cambie."""
        from app.modules.cases.stages import STAGE_LABELS

        return STAGE_LABELS.get(self.stage_code, self.stage_code)


class CaseStageEvent(UUIDPKMixin, OrgScopedMixin, Base):
    """Historial inmutable: una fila por cada cambio de etapa o sub-estado.

    De aquí salen los días en cada etapa, el tiempo hasta aprobación, la tasa de
    rechazo y la productividad por zona (PDF §7). **Es la pieza que no se puede
    reconstruir después**: si no se guarda desde el primer día, esos reportes
    quedan sin datos para siempre.

    Sin `TimestampMixin` a propósito: un evento no se actualiza nunca, así que
    `updated_at` sería una mentira. Lleva su propio `occurred_at`."""

    __tablename__ = "case_stage_events"
    __table_args__ = (Index("ix_case_stage_event_case_time", "case_id", "occurred_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage_code: Mapped[str | None] = mapped_column(String(40))
    to_stage_code: Mapped[str] = mapped_column(String(40), nullable=False)
    from_substatus_code: Mapped[str | None] = mapped_column(String(40))
    to_substatus_code: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    # Nulo si lo hizo el sistema (una migración, una tarea programada).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
