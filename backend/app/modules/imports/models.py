"""Cola de lo que falta traer de un sistema externo (hoy, CompanyCam).

Cada fila es un elemento (proyecto, foto o documento) y su estado de descarga.
El expediente y sus notas se cargan de una vez; los binarios se bajan después,
por lotes (`imports/companycam/downloads.py`), para no depender de la red
durante la carga ni de que las URL de CompanyCam sigan vivas."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

IMPORT_KINDS = ("project", "photo", "document")
# pending -> downloading -> downloaded | error (reintenta) | skipped_type | gone
IMPORT_STATUSES = ("pending", "downloading", "downloaded", "error", "skipped_type", "gone")


class ImportItem(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "import_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "source", "kind", "external_id", name="uq_import_item_ref"),
        Index("ix_import_item_status_kind", "status", "kind"),
    )

    source: Mapped[str] = mapped_column(String(20), nullable=False, default="companycam")
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_file_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("case_files.id", ondelete="SET NULL"))
    remote_url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
