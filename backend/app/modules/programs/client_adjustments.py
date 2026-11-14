"""Ajustes del cliente al formulario del vendedor, para las organizaciones que
ya tenían sus programas (5 y 11 nov 2026).

`templates.py` ya trae estos cambios, pero `install_defaults` no toca una
organización con versiones (nunca deshace un ajuste del administrador). Aquí se
hace lo mismo que haría el administrador en «Configuración de programas»: una
versión nueva copiada de la publicada, con los cambios, y publicada. Los
expedientes que ya iban siguen con su versión.

Idempotente: se compara la versión publicada con lo pedido y solo se publica
una nueva si falta algo. Si el programa tiene un borrador abierto, no se toca
(lo está editando alguien). Los programas nuevos (LADWP y GoZero) los crea
`install_defaults` ya con todo.

5 nov 2026:
- Correo opcional; en California también la foto del documento.
- 50 A y 70 A en el amperaje del panel.
- Sin «Diagnóstico de viabilidad eléctrica» en el vendedor: lo hace el técnico.
- Sin fotos de furnace, HVAC ni pedestal; título o decal en un solo campo.
- Resultado preliminar: «Completo» o «Pendiente de algo».

11 nov 2026:
- «Multifamiliar» en vez de «Condominio».
- 1040, W-2 y talones de cheque como prueba de ingresos en California.
- Calefacción (lo que calienta la casa en invierno) en la auditoría técnica.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases.models import CaseStepSubmission, Program, ProgramVersion
from app.modules.programs import service
from app.modules.programs.models import WorkflowStepField
from app.modules.programs.templates import CA_CON_DOCUMENTO

MARCA = "Ajustes del cliente"
MOBILE = {"field": "home.residence_type", "eq": "mobile_home"}
CALIFORNIA = {"TECH_CLEAN_CA", "LADWP", "GOZERO"}
OPCIONALES = {"AZ_EFFICIENCY": {"customer.email"},
              **{code: {"customer.email", "customer.id_photo"} for code in CALIFORNIA}}
QUITAR = {"tech.electrical_viability", "docs.furnace_photo", "docs.hvac_photos", "docs.pedestal_photo",
          "docs.mobile_home_title", "docs.mobile_home_decal"}
TITULO_O_DECAL = "docs.mobile_home_title_or_decal"
CALEFACCION = "tech.heating"


def _add_options(campo, nuevas: list[dict], *, antes_de: str | None = None) -> None:
    """Agrega las opciones que falten, sin tocar las que ya existen."""
    if campo is None or campo.options is None:
        return
    valores = {o["value"] for o in campo.options}
    faltan = [o for o in nuevas if o["value"] not in valores]
    if not faltan:
        return
    opciones = list(campo.options)
    pos = next((i for i, o in enumerate(opciones) if o["value"] == antes_de), len(opciones))
    campo.options = opciones[:pos] + faltan + opciones[pos:]


def _relabel(campo, etiquetas: dict) -> None:
    if campo is not None and campo.options is not None and any(
            o["value"] in etiquetas and o["label"] != etiquetas[o["value"]] for o in campo.options):
        campo.options = [{**o, "label": etiquetas.get(o["value"], o["label"])} for o in campo.options]


async def _options(db: AsyncSession, organization_id, campos: dict) -> None:
    amperaje = campos.get("tech.panel_amperage")
    if amperaje and amperaje.options is not None and not {"50", "70"} <= {o["value"] for o in amperaje.options}:
        _add_options(amperaje, [{"value": "50", "label": "50 A"}, {"value": "70", "label": "70 A"}],
                     antes_de=amperaje.options[0]["value"])
    resultado = campos.get("internal.result")
    if resultado and resultado.options is not None:
        _relabel(resultado, {"preapproved": "Completo", "pending": "Pendiente de algo"})
        # «No califica» sale si nadie la eligió: una opción ya usada no se quita.
        if any(o["value"] == "does_not_qualify" for o in resultado.options):
            usadas = (await db.execute(select(CaseStepSubmission.answers).where(
                CaseStepSubmission.organization_id == organization_id,
                CaseStepSubmission.step_code == "internal"))).scalars().all()
            if not any((a or {}).get("internal.result") == "does_not_qualify" for a in usadas):
                resultado.options = [o for o in resultado.options if o["value"] != "does_not_qualify"]
    _relabel(campos.get("home.residence_type"), {"condominium": "Multifamiliar"})
    elegibilidad = campos.get("eligibility.programs_tech")
    _add_options(elegibilidad, [{"value": "tax_1040", "label": "Taxes (1040)"}, {"value": "w2", "label": "W-2"},
                                {"value": "pay_stubs", "label": "Talones de cheque"}], antes_de="none")
    if elegibilidad is not None and elegibilidad.label == "Programas de beneficio del hogar (TECH Clean)":
        elegibilidad.label = "Programas de beneficio del hogar (California)"


async def _adjust(db: AsyncSession, version: ProgramVersion, code: str, por_id: dict, ids: dict, *,
                  dry: bool = False) -> int:
    """Cuántos cambios pide la versión. Con `dry` solo cuenta: así una versión
    que ya está al día no recibe una copia vacía."""
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
                # Los documentos de ingresos también piden subir el documento.
                cond = c.condition or {}
                if (clave == "eligibility.benefit_document" and cond.get("field") == "eligibility.programs_tech"
                        and not set(CA_CON_DOCUMENTO) <= set(cond.get("in") or [])):
                    cambios += 1
                    if not dry:
                        c.condition = {**cond, "in": list(dict.fromkeys([*(cond.get("in") or []), *CA_CON_DOCUMENTO]))}
            claves = [por_id.get(c.field_id) for c in paso.fields]
            if hubo_titulo is not None and TITULO_O_DECAL not in claves:
                if not dry:
                    db.add(WorkflowStepField(organization_id=version.organization_id, step_id=paso.id,
                                             field_id=ids[TITULO_O_DECAL], requirement="conditional",
                                             condition=MOBILE, sort_order=hubo_titulo))
            if paso.code == "technical" and CALEFACCION not in claves:
                cambios += 1
                if not dry:
                    # Junto a la climatización existente, que es lo que más se le parece.
                    junto = next((c for c in paso.fields if por_id.get(c.field_id) == "tech.existing_hvac"), None)
                    orden = (junto.sort_order if junto else len(paso.fields)) + 1
                    for c in paso.fields:
                        if c.sort_order >= orden:
                            c.sort_order += 1
                    db.add(WorkflowStepField(organization_id=version.organization_id, step_id=paso.id,
                                             field_id=ids[CALEFACCION], requirement="required", sort_order=orden))
    await db.flush()
    return cambios


async def apply(db: AsyncSession, *, organization_id) -> list[str]:
    """Aplica los ajustes y devuelve los códigos de los programas con versión nueva."""
    # Crea los campos nuevos y los programas que falten (LADWP y GoZero).
    await service.install_defaults(db, organization_id=organization_id)
    campos = {f.key: f for f in await service.list_fields(db, organization_id=organization_id)}
    await _options(db, organization_id, campos)
    await db.flush()
    # Los ids se toman antes: un objeto vencido no se lee sin `await` en la sesión asíncrona.
    por_id = {f.id: f.key for f in campos.values()}
    ids = {k: campos[k].id for k in (TITULO_O_DECAL, CALEFACCION)}
    hechos = []
    programas = (await db.execute(select(Program).where(
        Program.organization_id == organization_id, Program.code.in_(OPCIONALES)))).scalars().all()
    for programa in programas:
        versiones = await service.list_versions(db, organization_id=organization_id, program_id=programa.id)
        if any(v.status == "draft" for v in versiones):
            continue
        base = next((v for v in reversed(versiones) if v.status == "published"), None)
        if base is None or not await _adjust(db, base, programa.code, por_id, ids, dry=True):
            continue
        hoy = datetime.now(timezone.utc)
        nueva = ProgramVersion(organization_id=organization_id, program_id=programa.id,
                               version=str(len(versiones) + 1), status="draft", terms_id=base.terms_id,
                               notes=f"{MARCA} ({hoy:%d %b %Y})")
        db.add(nueva)
        await db.flush()
        await service._copy_structure(db, base.id, nueva)
        await db.flush()
        await _adjust(db, nueva, programa.code, por_id, ids)
        problemas = await service.version_problems(db, nueva)
        if problemas:
            # No se publica a medias: la versión queda en borrador para revisarla en pantalla.
            nueva.notes = f"{nueva.notes} (borrador: {'; '.join(problemas)})"
            continue
        anterior = await db.get(ProgramVersion, base.id)
        anterior.status = "archived"
        nueva.status = "published"
        nueva.published_at = hoy
        hechos.append(programa.code)
    await db.commit()
    return hechos
