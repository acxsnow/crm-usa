"""Ajustes del cliente al formulario del vendedor (5 nov 2026), para las
organizaciones que ya tenían sus programas.

`templates.py` ya trae estos cambios, pero `install_defaults` no toca una
organización con versiones (nunca deshace un ajuste del administrador). Aquí se
hace lo mismo que haría el administrador en «Configuración de programas»: una
versión nueva copiada de la publicada, con los cambios, y publicada. Los
expedientes que ya iban siguen con su versión.

Idempotente: la versión lleva `MARCA` en las notas y no se repite. Si el
programa tiene un borrador abierto, no se toca (lo está editando alguien).

- Correo opcional; en TECH (California) también la foto del documento.
- 50 A y 70 A en el amperaje del panel.
- Sin «Diagnóstico de viabilidad eléctrica» en el vendedor: lo hace el técnico.
- Sin fotos de furnace, HVAC ni pedestal; título o decal en un solo campo.
- Resultado preliminar: «Completo» o «Pendiente de algo».
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases.models import CaseStepSubmission, Program, ProgramVersion
from app.modules.programs import service
from app.modules.programs.models import WorkflowStepField

MARCA = "Ajustes del cliente del 5 nov 2026"
MOBILE = {"field": "home.residence_type", "eq": "mobile_home"}
OPCIONALES = {"AZ_EFFICIENCY": {"customer.email"}, "TECH_CLEAN_CA": {"customer.email", "customer.id_photo"}}
QUITAR = {"tech.electrical_viability", "docs.furnace_photo", "docs.hvac_photos", "docs.pedestal_photo",
          "docs.mobile_home_title", "docs.mobile_home_decal"}
TITULO_O_DECAL = "docs.mobile_home_title_or_decal"


async def _options(db: AsyncSession, organization_id, campos: dict) -> None:
    amperaje = campos.get("tech.panel_amperage")
    if amperaje and amperaje.options is not None:
        valores = {o["value"] for o in amperaje.options}
        nuevas = [o for o in ({"value": "50", "label": "50 A"}, {"value": "70", "label": "70 A"})
                  if o["value"] not in valores]
        if nuevas:
            amperaje.options = nuevas + list(amperaje.options)
    resultado = campos.get("internal.result")
    if resultado and resultado.options is not None:
        etiquetas = {"preapproved": "Completo", "pending": "Pendiente de algo"}
        opciones = [{**o, "label": etiquetas.get(o["value"], o["label"])} for o in resultado.options]
        # «No califica» sale si nadie la eligió: una opción ya usada no se quita.
        usadas = (await db.execute(select(CaseStepSubmission.answers).where(
            CaseStepSubmission.organization_id == organization_id,
            CaseStepSubmission.step_code == "internal"))).scalars().all()
        if not any((a or {}).get("internal.result") == "does_not_qualify" for a in usadas):
            opciones = [o for o in opciones if o["value"] != "does_not_qualify"]
        resultado.options = opciones


async def _adjust(db: AsyncSession, version: ProgramVersion, code: str, por_id: dict, titulo_id, *,
                  dry: bool = False) -> int:
    """Cuántos cambios pide la versión. Con `dry` solo cuenta: así una versión
    que ya está al día (organizaciones nuevas) no recibe una copia vacía."""
    cambios = 0
    for fase in await service.phases_of(db, version.id):
        for paso in fase.steps:
            hubo_titulo = None
            for c in list(paso.fields):
                clave = por_id.get(c.field_id)
                if clave in OPCIONALES.get(code, set()) and c.requirement == "required":
                    cambios += 1
                    if not dry:
                        c.requirement = "optional"
                if clave in QUITAR:
                    cambios += 1
                    if clave in ("docs.mobile_home_title", "docs.mobile_home_decal") and hubo_titulo is None:
                        hubo_titulo = c.sort_order
                    if not dry:
                        await db.delete(c)
            ya = any(por_id.get(c.field_id) == TITULO_O_DECAL for c in paso.fields)
            if hubo_titulo is not None and not ya and not dry:
                db.add(WorkflowStepField(organization_id=version.organization_id, step_id=paso.id,
                                         field_id=titulo_id, requirement="conditional",
                                         condition=MOBILE, sort_order=hubo_titulo))
    await db.flush()
    return cambios


async def apply(db: AsyncSession, *, organization_id) -> list[str]:
    """Aplica los ajustes y devuelve los códigos de los programas con versión nueva."""
    await service.install_defaults(db, organization_id=organization_id)  # crea el campo «Título o decal»
    campos = {f.key: f for f in await service.list_fields(db, organization_id=organization_id)}
    await _options(db, organization_id, campos)
    await db.flush()
    # Los ids se toman antes: un objeto vencido no se lee sin `await` en la sesión asíncrona.
    por_id = {f.id: f.key for f in campos.values()}
    titulo_id = campos[TITULO_O_DECAL].id
    hechos = []
    programas = (await db.execute(select(Program).where(
        Program.organization_id == organization_id, Program.code.in_(OPCIONALES)))).scalars().all()
    for programa in programas:
        versiones = await service.list_versions(db, organization_id=organization_id, program_id=programa.id)
        if any(MARCA in (v.notes or "") for v in versiones) or any(v.status == "draft" for v in versiones):
            continue
        base = next((v for v in reversed(versiones) if v.status == "published"), None)
        if base is None or not await _adjust(db, base, programa.code, por_id, titulo_id, dry=True):
            continue
        nueva = ProgramVersion(organization_id=organization_id, program_id=programa.id,
                               version=str(len(versiones) + 1), status="draft", terms_id=base.terms_id,
                               notes=MARCA)
        db.add(nueva)
        await db.flush()
        await service._copy_structure(db, base.id, nueva)
        await db.flush()
        await _adjust(db, nueva, programa.code, por_id, titulo_id)
        problemas = await service.version_problems(db, nueva)
        if problemas:
            # No se publica a medias: la versión queda en borrador para revisarla en pantalla.
            nueva.notes = f"{MARCA} (borrador: {'; '.join(problemas)})"
            continue
        anterior = await db.get(ProgramVersion, base.id)
        anterior.status = "archived"
        nueva.status = "published"
        nueva.published_at = datetime.now(timezone.utc)
        hechos.append(programa.code)
    await db.commit()
    return hechos
