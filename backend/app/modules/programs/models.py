"""Programa configurable: catálogo de campos, flujo versionado, T&C y zonas
de venta (módulo 1, spec `2026-10-04-modulo-1-programas-design.md`).

`Program`, `ProgramVersion` y `ProgramZone` siguen en `cases/models.py` (D1.1);
aquí van las tablas que cuelgan de ellos.

    Program ─┬─ ProgramTerms (versión × idioma)
             ├─ ProgramVersion ── WorkflowPhase ── WorkflowStep ── WorkflowStepField ──▶ FieldDefinition
             └─ ProgramZone ── ZoneAssignment (vendedor)
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

# Los 18 tipos de §2.3, con la etiqueta que ve el administrador.
FIELD_TYPES: dict[str, str] = {
    "text": "Texto corto",
    "textarea": "Texto largo",
    "integer": "Número entero",
    "decimal": "Número decimal",
    "phone": "Teléfono",
    "email": "Correo electrónico",
    "date": "Fecha",
    "time": "Hora",
    "yes_no": "Sí / No",
    "single_select": "Selección única",
    "multi_select": "Selección múltiple",
    "address": "Dirección dividida",
    "document": "Documento",
    "photo": "Foto",
    "video": "Video",
    "signature": "Firma",
    "info": "Calculado o informativo",
    "terms_checkbox": "Aceptación de T&C",
    # Los que llena el sistema, no el vendedor (§2.5: `signed_at`, `salesperson`).
    "system_datetime": "Fecha y hora del sistema",
    "system_user": "Usuario del sistema",
}

# Tipos cuyo valor sale de una lista de opciones.
SELECT_TYPES = {"single_select", "multi_select"}
# Tipos que el vendedor no responde.
SYSTEM_TYPES = {"info", "system_datetime", "system_user"}

# A dónde puede ir una respuesta como dato real (D3: "binding"). Lo demás vive
# en los datos del paso (`step_submissions`, módulo 2).
BINDINGS: dict[str, str] = {
    "customer.legal_name": "Cliente · nombre",
    "customer.main_phone": "Cliente · teléfono",
    "customer.email": "Cliente · correo",
    "case.address_street": "Expediente · dirección",
    "case.address_unit": "Expediente · unidad o espacio",
    "case.address_city": "Expediente · ciudad",
    "case.address_state": "Expediente · estado",
    "case.address_zip": "Expediente · ZIP",
}

REQUIREMENT_LEVELS = {"required": "Obligatorio", "optional": "Opcional", "conditional": "Condicional"}

# Roles que pueden ser responsables de una fase (D3).
PHASE_ROLES = {
    "salesperson": "Vendedor",
    "admin_staff": "Administración",
    "field_technician": "Técnico",
    "accounting": "Contabilidad",
}


class FieldDefinition(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Una pregunta del catálogo (§2.4–§2.5). Existe una sola vez por
    organización; cada programa decide en su flujo si la usa y cómo."""

    __tablename__ = "field_definitions"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_field_definition_key"),)

    # Clave estable: no cambia aunque cambie la etiqueta o el idioma. Reportes,
    # reglas, documentos e invoices se apoyan en ella.
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    help_text: Mapped[str | None] = mapped_column(Text)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Sección sugerida (Cliente, Vivienda…); el flujo la puede ordenar distinto.
    section: Mapped[str | None] = mapped_column(String(120))
    # [{"value": "natural_gas", "label": "Gas natural"}, …] para selecciones.
    options: Mapped[list | None] = mapped_column(JSON)
    # {"min": 1, "max": 20, "min_length": 3, "max_length": 255,
    #  "format": "zip" | "phone" | "email", "exclusive": ["none"]}
    validation: Mapped[dict | None] = mapped_column(JSON)
    binding: Mapped[str | None] = mapped_column(String(60))
    # Uso interno (§3.6): nunca lo ve el cliente.
    internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Dato sensible (§17.3): verlo exige `fields.view_sensitive`.
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProgramTerms(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Texto de T&C de un programa, por versión e idioma (§3.5). Publicado no
    se edita: el expediente tiene que poder decir qué texto aceptó el cliente."""

    __tablename__ = "program_terms"
    __table_args__ = (UniqueConstraint("program_id", "version", "language", name="uq_program_terms_version_lang"),)

    program_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="es")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowPhase(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Una fase del flujo, con el rol que la llena (D3). La primera versión de
    cada programa trae la fase Vendedor."""

    __tablename__ = "workflow_phases"

    version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("program_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_code: Mapped[str] = mapped_column(String(40), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep", back_populates="phase", cascade="all, delete-orphan",
        order_by="WorkflowStep.sort_order", lazy="selectin",
    )


class WorkflowStep(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un paso de la fase: lo que el vendedor ve en una pantalla."""

    __tablename__ = "workflow_steps"

    phase_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workflow_phases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    phase: Mapped["WorkflowPhase"] = relationship("WorkflowPhase", back_populates="steps")
    fields: Mapped[list["WorkflowStepField"]] = relationship(
        "WorkflowStepField", back_populates="step", cascade="all, delete-orphan",
        order_by="WorkflowStepField.sort_order", lazy="selectin",
    )


class WorkflowStepField(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un campo del catálogo dentro de un paso, con cómo se comporta en este
    programa (§2.4): obligatoriedad, condición, etiqueta y ayuda propias."""

    __tablename__ = "workflow_step_fields"
    __table_args__ = (UniqueConstraint("step_id", "field_id", name="uq_workflow_step_field"),)

    step_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("field_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requirement: Mapped[str] = mapped_column(String(20), nullable=False, default="optional")
    # {"field": "home.gas_type", "eq": "natural_gas"} — ver `engine.py`.
    condition: Mapped[dict | None] = mapped_column(JSON)
    label_override: Mapped[str | None] = mapped_column(String(255))
    help_override: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    step: Mapped["WorkflowStep"] = relationship("WorkflowStep", back_populates="fields")
    field: Mapped["FieldDefinition"] = relationship("FieldDefinition", lazy="selectin")


class ZoneAssignment(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Vendedor asignado a una zona de venta (D5)."""

    __tablename__ = "zone_assignments"
    __table_args__ = (UniqueConstraint("zone_id", "user_id", name="uq_zone_assignment"),)

    zone_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("program_zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Estados y ciudades: datos de referencia del sistema (no por organización).
# ---------------------------------------------------------------------------
# Los carga la migración 0024 con el censo de EE. UU. (Gazetteer 2023: ciudades,
# pueblos y comunidades no incorporadas, CDP). Sirven para validar el estado y
# sugerir la ciudad; las direcciones de expedientes y zonas se siguen guardando
# como texto, tal como se capturaron.


class GeoState(Base):
    __tablename__ = "geo_states"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    # Para respetar el horario del cliente (Arizona no cambia de hora en verano).
    timezone: Mapped[str] = mapped_column(String(60), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class GeoCity(Base):
    __tablename__ = "geo_cities"
    __table_args__ = (UniqueConstraint("state_code", "name", name="uq_geo_city_state_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_code: Mapped[str] = mapped_column(String(2), ForeignKey("geo_states.code"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
