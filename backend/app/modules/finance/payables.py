"""Proveedores y cuentas por pagar (respuestas del cliente del 8 oct en la spec).

- Aldo Martínez (permiso `payables.approve`) aprueba y programa el pago;
  Contabilidad (`payables.manage`) registra facturas y pagos.
- Bajo el umbral, una aprobación con `payables.approve`. Desde el umbral
  (10.000 USD por defecto), dos personas distintas: una con
  `payables.approve` y otra con `payables.manage`.
- La plataforma no paga: registra el pago hecho por fuera. Un pago puede
  repartirse entre varias facturas del mismo proveedor y quedar en parcial.
"""
import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.billing.money import ZERO, money_sum, to_money
from app.modules.finance.expenses import settings_of
from app.modules.finance.models import (
    COST_CATEGORIES,
    PAYMENT_METHODS,
    SUPPLIER_DOC_KINDS,
    SUPPLIER_KINDS,
    Supplier,
    SupplierDocument,
    SupplierInvoice,
    SupplierInvoiceApproval,
    SupplierInvoiceLine,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

FILE_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}
MAX_FILE_BYTES = 15 * 1024 * 1024
STATES = {"CA", "AZ", "NV"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _today(db, organization_id) -> date:
    from app.modules.field_ops.clock import org_today

    return await org_today(db, organization_id)


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

async def get_supplier(db, organization_id, supplier_id) -> Supplier:
    s = await db.get(Supplier, supplier_id)
    if s is None or s.organization_id != organization_id:
        raise NotFoundError("El proveedor no existe.", code="supplier_not_found")
    return s


def _clean_supplier(data: dict) -> dict:
    kinds = [k for k in data.get("kinds") or [] if k]
    if set(kinds) - set(SUPPLIER_KINDS):
        raise InvalidInputError("Tipo de proveedor desconocido.", code="invalid_supplier_kind")
    states = [s.upper() for s in data.get("states") or [] if s]
    if set(states) - STATES:
        raise InvalidInputError("Los estados válidos son CA, AZ y NV.", code="invalid_state")
    if data.get("payment_method") and data["payment_method"] not in PAYMENT_METHODS:
        raise InvalidInputError("Forma de pago desconocida.", code="invalid_payment_method")
    terms = int(data.get("payment_terms_days") if data.get("payment_terms_days") is not None else 30)
    if terms < 0 or terms > 180:
        raise InvalidInputError("Las condiciones de pago van de 0 (contado) a 180 días.", code="invalid_terms")
    nombre = (data.get("name") or "").strip()
    if not nombre:
        raise InvalidInputError("El proveedor necesita un nombre.", code="supplier_name_required")
    return {**data, "name": nombre, "kinds": kinds, "states": states, "payment_terms_days": terms}


async def save_supplier(db, *, organization_id, user, data: dict, supplier_id=None) -> Supplier:
    datos = _clean_supplier(data)
    stmt = select(Supplier.id).where(Supplier.organization_id == organization_id, Supplier.name == datos["name"])
    if supplier_id:
        stmt = stmt.where(Supplier.id != supplier_id)
    otro = (await db.execute(stmt)).first()
    if otro:
        raise ConflictError("Ya hay un proveedor con ese nombre.", code="supplier_duplicate")
    if supplier_id:
        s = await get_supplier(db, organization_id, supplier_id)
    else:
        s = Supplier(organization_id=organization_id)
        db.add(s)
    # Cambiar la cuenta del proveedor es el fraude clásico: solo Contabilidad
    # (`payables.manage`) lo hace, queda en la auditoría y se avisa a quien aprueba.
    banco_cambia = "bank_details" in datos and (datos["bank_details"] or None) != (s.bank_details or None)
    if banco_cambia and "payables.manage" not in get_effective_permissions(user):
        raise ForbiddenError("Solo Contabilidad puede cambiar los datos bancarios del proveedor.",
                             code="bank_details_forbidden")
    for campo in ("name", "legal_name", "tax_id", "kinds", "contact_name", "phone", "email", "address", "states",
                  "payment_terms_days", "payment_method", "bank_details", "license_number", "license_expires_on",
                  "insurance_expires_on", "w9_on_file", "notes", "active"):
        if campo in datos:
            setattr(s, campo, datos[campo])
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="suppliers.updated" if supplier_id else "suppliers.created",
                             entity_type="supplier", entity_id=str(s.id) if s.id else None,
                             after_data={"name": s.name, "bank_details_changed": banco_cambia})
    await db.commit()
    await db.refresh(s)
    if banco_cambia and supplier_id:
        domain_events.emit("supplier.bank_changed", {"supplier_id": str(s.id), "organization_id": str(organization_id),
                                                     "user_id": str(user.id)})
    return s


def supplier_out(s: Supplier, user, balance: Decimal | None = None) -> dict:
    ve_banco = "payables.manage" in get_effective_permissions(user)
    return {
        "id": str(s.id), "name": s.name, "legal_name": s.legal_name, "tax_id": s.tax_id, "kinds": s.kinds or [],
        "contact_name": s.contact_name, "phone": s.phone, "email": s.email, "address": s.address,
        "states": s.states or [], "payment_terms_days": s.payment_terms_days, "payment_method": s.payment_method,
        "bank_details": s.bank_details if ve_banco else ("•••" if s.bank_details else None),
        "license_number": s.license_number,
        "license_expires_on": s.license_expires_on.isoformat() if s.license_expires_on else None,
        "insurance_expires_on": s.insurance_expires_on.isoformat() if s.insurance_expires_on else None,
        "w9_on_file": s.w9_on_file, "notes": s.notes, "active": s.active,
        "balance": str(balance) if balance is not None else None,
    }


async def import_suppliers_csv(db, *, organization_id, user, text: str) -> dict:
    """Carga proveedores desde un CSV (exportado de QuickBooks o Excel). Columnas
    reconocidas (en inglés o español): name/nombre, legal_name/razon_social,
    tax_id/ein, contact/contacto, phone/telefono, email/correo, address/direccion,
    terms/condiciones (días), kind/tipo. Los que ya existen (por nombre) se omiten."""
    lector = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    alias = {"nombre": "name", "razon_social": "legal_name", "razón social": "legal_name", "ein": "tax_id",
             "contacto": "contact_name", "contact": "contact_name", "telefono": "phone", "teléfono": "phone",
             "correo": "email", "direccion": "address", "dirección": "address", "condiciones": "payment_terms_days",
             "terms": "payment_terms_days", "tipo": "kind", "company": "name", "vendor": "name"}
    existentes = {n.lower() for n in (await db.execute(select(Supplier.name).where(
        Supplier.organization_id == organization_id))).scalars().all()}
    creados, omitidos, malos = 0, 0, []
    for i, fila in enumerate(lector, start=2):
        f = {alias.get(k.strip().lower(), k.strip().lower()): (v or "").strip() for k, v in fila.items() if k}
        nombre = f.get("name")
        if not nombre:
            malos.append(f"fila {i}: sin nombre")
            continue
        if nombre.lower() in existentes:
            omitidos += 1
            continue
        try:
            terms = int(float(f.get("payment_terms_days") or 30))
        except ValueError:
            terms = 30
        kind = f.get("kind", "").lower()
        db.add(Supplier(organization_id=organization_id, name=nombre[:255], legal_name=f.get("legal_name") or None,
                        tax_id=f.get("tax_id") or None, contact_name=f.get("contact_name") or None,
                        phone=f.get("phone") or None, email=f.get("email") or None, address=f.get("address") or None,
                        payment_terms_days=max(0, min(terms, 180)), kinds=[kind] if kind in SUPPLIER_KINDS else [],
                        states=[], w9_on_file=False, active=True))
        existentes.add(nombre.lower())
        creados += 1
        if creados > 2000:
            raise InvalidInputError("Máximo 2.000 proveedores por carga.", code="too_many_rows")
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="suppliers.imported",
                             entity_type="supplier", after_data={"created": creados, "skipped": omitidos})
    await db.commit()
    return {"created": creados, "skipped": omitidos, "invalid": malos[:20]}


async def add_supplier_document(db, *, organization_id, user, supplier_id, kind, expires_on, data: bytes,
                                filename, mime) -> SupplierDocument:
    from app.shared.files.storage import save_bytes
    from app.shared.files.validation import check_type

    s = await get_supplier(db, organization_id, supplier_id)
    if kind not in SUPPLIER_DOC_KINDS:
        raise InvalidInputError("Tipo de documento desconocido.", code="invalid_document_kind")
    mime = check_type(data, mime, FILE_MIME)
    d = SupplierDocument(organization_id=organization_id, supplier_id=s.id, kind=kind, expires_on=expires_on,
                         mime_type=mime, original_filename=filename, uploaded_by_user_id=user.id,
                         file_path=save_bytes(organization_id=organization_id, subfolder=f"suppliers/{s.id}",
                                              filename=filename or kind, data=data))
    db.add(d)
    # El vencimiento del documento actualiza el del proveedor (alerta diaria).
    if kind == "license" and expires_on:
        s.license_expires_on = expires_on
    if kind == "insurance" and expires_on:
        s.insurance_expires_on = expires_on
    if kind == "w9":
        s.w9_on_file = True
    await db.commit()
    await db.refresh(d)
    return d


# ---------------------------------------------------------------------------
# Facturas de proveedor
# ---------------------------------------------------------------------------

def paid_amount(inv: SupplierInvoice) -> Decimal:
    return money_sum(a.amount for a in inv.allocations)


def balance(inv: SupplierInvoice) -> Decimal:
    return (to_money(inv.total) - paid_amount(inv)).quantize(Decimal("0.01"))


def _sync_status(inv: SupplierInvoice) -> None:
    if inv.status in ("void", "pending_approval"):
        return
    pagado = paid_amount(inv)
    inv.status = "paid" if pagado >= to_money(inv.total) else "partially_paid" if pagado > ZERO else "approved"


async def get_invoice(db, organization_id, invoice_id) -> SupplierInvoice:
    # populate_existing: recarga líneas, aprobaciones y pagos aunque la factura
    # ya esté en la sesión (con sesión asíncrona no se puede cargar perezosamente).
    inv = (await db.execute(select(SupplierInvoice).where(SupplierInvoice.id == invoice_id)
                            .execution_options(populate_existing=True))).scalar_one_or_none()
    if inv is None or inv.organization_id != organization_id:
        raise NotFoundError("La factura no existe.", code="supplier_invoice_not_found")
    return inv


async def _check_projects(db, organization_id, ids) -> None:
    from app.modules.field_ops.models import Project

    ids = {i for i in ids if i}
    if not ids:
        return
    validos = set((await db.execute(select(Project.id).where(
        Project.organization_id == organization_id, Project.id.in_(ids)))).scalars().all())
    if ids - validos:
        raise InvalidInputError("Uno de los proyectos no existe.", code="project_not_found")


async def create_invoice(db: AsyncSession, *, organization_id, user, data: dict, file: tuple | None) -> SupplierInvoice:
    """Registra la factura. Con `paid_now` (contado o tarjeta, respuesta 1.2)
    queda aprobada y pagada en el mismo paso, solo bajo el umbral de doble aprobación."""
    from app.shared.files.storage import save_bytes
    from app.shared.files.validation import check_type

    s = await get_supplier(db, organization_id, data["supplier_id"])
    numero = (data.get("number") or "").strip()
    if not numero:
        raise InvalidInputError("Escribe el número de la factura del proveedor.", code="invoice_number_required")
    if (await db.execute(select(SupplierInvoice.id).where(
            SupplierInvoice.organization_id == organization_id, SupplierInvoice.supplier_id == s.id,
            SupplierInvoice.number == numero))).first():
        raise ConflictError(f"La factura {numero} de {s.name} ya está registrada.", code="supplier_invoice_duplicate")
    lineas = data.get("lines") or []
    if not lineas:
        if data.get("total") in (None, ""):
            raise InvalidInputError("Escribe el total o el detalle por líneas.", code="invoice_total_required")
        lineas = [{"description": data.get("description") or f"Factura {numero}",
                   "category": data.get("category") or "materials", "quantity": "1",
                   "unit_cost": str(to_money(data["total"]) - to_money(data.get("tax") or 0)
                                    - to_money(data.get("shipping") or 0)),
                   "project_id": data.get("project_id")}]
    await _check_projects(db, organization_id, [l.get("project_id") for l in lineas])
    filas = []
    for n, l in enumerate(lineas):
        if (l.get("category") or "materials") not in COST_CATEGORIES:
            raise InvalidInputError("Categoría de costo desconocida.", code="invalid_cost_category")
        cantidad, unitario = Decimal(str(l.get("quantity") or "1")), to_money(l["unit_cost"])
        if cantidad <= 0 or unitario < ZERO:
            raise InvalidInputError("Cantidad y costo deben ser positivos.", code="invalid_line")
        filas.append(SupplierInvoiceLine(sort_order=n, description=(l.get("description") or "").strip()[:255] or "Línea",
                                         category=l.get("category") or "materials", quantity=cantidad,
                                         unit_cost=unitario, amount=to_money(cantidad * unitario),
                                         project_id=l.get("project_id") or None))
    subtotal = money_sum(f.amount for f in filas)
    impuesto, envio = to_money(data.get("tax") or 0), to_money(data.get("shipping") or 0)
    total = (subtotal + impuesto + envio).quantize(Decimal("0.01"))
    if total <= ZERO:
        raise InvalidInputError("El total debe ser mayor que cero.", code="invalid_amount")
    fecha = data["invoice_date"]
    vence = data.get("due_date") or fecha + timedelta(days=s.payment_terms_days)
    if vence < fecha:
        raise InvalidInputError("El vencimiento no puede ser antes de la fecha de la factura.", code="invalid_due_date")
    inv = SupplierInvoice(organization_id=organization_id, supplier_id=s.id, number=numero, invoice_date=fecha,
                          due_date=vence, subtotal=subtotal, tax=impuesto, shipping=envio, total=total,
                          status="pending_approval", notes=data.get("notes"), created_by_user_id=user.id, lines=filas,
                          approvals=[])
    db.add(inv)
    await db.flush()
    if file:
        contenido, nombre, mime = file
        inv.file_mime = check_type(contenido, mime, FILE_MIME)
        inv.file_path = save_bytes(organization_id=organization_id, subfolder=f"supplier-invoices/{inv.id}",
                                   filename=nombre or numero, data=contenido)
    if data.get("paid_now"):
        umbral = to_money((await settings_of(db, organization_id)).two_approval_threshold)
        if total >= umbral:
            raise InvalidInputError(f"Desde {umbral} USD la factura necesita dos aprobaciones antes de pagarse; "
                                    "regístrala sin «pagada al momento».", code="paid_now_over_threshold")
        metodo = data.get("paid_method") or "card"
        if metodo not in PAYMENT_METHODS:
            raise InvalidInputError("Forma de pago desconocida.", code="invalid_payment_method")
        inv.status = "approved"
        inv.approvals.append(SupplierInvoiceApproval(organization_id=organization_id, user_id=user.id,
                                                     capacity="paid_now", approved_at=_now(),
                                                     notes="Pagada al momento de la compra"))
        pago = SupplierPayment(organization_id=organization_id, supplier_id=s.id, paid_on=fecha, amount=total,
                               method=metodo, reference=data.get("paid_reference"), recorded_by_user_id=user.id,
                               notes="Pagada al momento de la compra")
        pago.allocations.append(SupplierPaymentAllocation(invoice_id=inv.id, amount=total))
        db.add(pago)
        inv.status = "paid"
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="payables.invoice_created", entity_type="supplier_invoice", entity_id=str(inv.id),
                             after_data={"supplier": s.name, "number": numero, "total": str(total),
                                         "paid_now": bool(data.get("paid_now"))})
    await db.commit()
    inv = await get_invoice(db, organization_id, inv.id)
    if inv.status == "pending_approval":
        domain_events.emit("payable.pending_approval", {"invoice_id": str(inv.id), "organization_id": str(organization_id)})
    elif data.get("paid_now"):
        # Pagada al momento sin aprobación previa: quien aprueba pagos se entera
        # de cada una, para que no se vuelva la puerta de atrás.
        domain_events.emit("payable.paid_now", {"invoice_id": str(inv.id), "organization_id": str(organization_id),
                                                "user_id": str(user.id)})
    return inv


def approvals_needed(inv: SupplierInvoice, umbral: Decimal) -> list[str]:
    """Lo que le falta a la factura: lista de capacidades pendientes."""
    hechas = {a.capacity for a in inv.approvals}
    if "paid_now" in hechas:
        return []
    faltan = []
    if "approve" not in hechas:
        faltan.append("approve")
    if to_money(inv.total) >= umbral and "accounting" not in hechas:
        faltan.append("accounting")
    return faltan


async def approve_invoice(db, *, organization_id, user, invoice_id, notes=None) -> SupplierInvoice:
    inv = await get_invoice(db, organization_id, invoice_id)
    if inv.status != "pending_approval":
        raise ConflictError("Esa factura no está por aprobar.", code="invoice_not_pending")
    if any(a.user_id == user.id for a in inv.approvals):
        raise ConflictError("Ya aprobaste esta factura; la segunda aprobación es de otra persona.",
                            code="already_approved_by_user")
    umbral = to_money((await settings_of(db, organization_id)).two_approval_threshold)
    faltan = approvals_needed(inv, umbral)
    permisos = get_effective_permissions(user)
    # Primero la capacidad de Aldo (aprueba); si ya está, la de Contabilidad.
    capacidad = next((c for c in faltan if (c == "approve" and "payables.approve" in permisos)
                      or (c == "accounting" and "payables.manage" in permisos)), None)
    if capacidad is None:
        raise ForbiddenError("No te corresponde esta aprobación." + (
            " Desde el umbral la aprueban Contabilidad y quien autoriza pagos." if len(faltan) > 1 else ""),
            code="approval_not_allowed")
    inv.approvals.append(SupplierInvoiceApproval(organization_id=organization_id, user_id=user.id, capacity=capacidad,
                                                 approved_at=_now(), notes=(notes or "").strip() or None))
    await db.flush()
    if not approvals_needed(inv, umbral):
        inv.status = "approved"
        _sync_status(inv)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="payables.invoice_approved",
                             entity_type="supplier_invoice", entity_id=str(inv.id),
                             after_data={"capacity": capacidad, "status": inv.status})
    await db.commit()
    return await get_invoice(db, organization_id, inv.id)


async def schedule_invoice(db, *, organization_id, user, invoice_id, scheduled: date | None) -> SupplierInvoice:
    inv = await get_invoice(db, organization_id, invoice_id)
    if inv.status not in ("approved", "partially_paid"):
        raise ConflictError("Solo se programa el pago de una factura aprobada con saldo.", code="invoice_not_payable")
    inv.scheduled_payment_date = scheduled
    await db.commit()
    return await get_invoice(db, organization_id, inv.id)


async def void_invoice(db, *, organization_id, user, invoice_id, reason: str) -> SupplierInvoice:
    inv = await get_invoice(db, organization_id, invoice_id)
    if inv.allocations:
        raise ConflictError("Una factura con pagos no se anula.", code="invoice_has_payments")
    if not (reason or "").strip():
        raise InvalidInputError("Escribe el motivo de la anulación.", code="reason_required")
    inv.status, inv.void_reason = "void", reason.strip()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="payables.invoice_voided",
                             entity_type="supplier_invoice", entity_id=str(inv.id), after_data={"reason": reason})
    await db.commit()
    return await get_invoice(db, organization_id, inv.id)


async def record_payment(db, *, organization_id, user, data: dict, file: tuple | None = None) -> SupplierPayment:
    from app.shared.files.storage import save_bytes
    from app.shared.files.validation import check_type

    s = await get_supplier(db, organization_id, data["supplier_id"])
    if data["method"] not in PAYMENT_METHODS:
        raise InvalidInputError("Forma de pago desconocida.", code="invalid_payment_method")
    monto = to_money(data["amount"])
    if monto <= ZERO:
        raise InvalidInputError("El monto debe ser mayor que cero.", code="invalid_amount")
    if data["paid_on"] > await _today(db, organization_id):
        raise InvalidInputError("La fecha del pago no puede ser futura.", code="payment_future_date")
    repartos = data.get("allocations") or []
    if not repartos:
        raise InvalidInputError("Indica a qué facturas se aplica el pago.", code="allocations_required")
    if money_sum(r["amount"] for r in repartos) != monto:
        raise InvalidInputError("La suma repartida entre facturas debe ser igual al monto del pago.",
                                code="allocation_mismatch")
    pago = SupplierPayment(organization_id=organization_id, supplier_id=s.id, paid_on=data["paid_on"], amount=monto,
                           method=data["method"], reference=(data.get("reference") or "").strip() or None,
                           bank_account=(data.get("bank_account") or "").strip() or None, notes=data.get("notes"),
                           recorded_by_user_id=user.id)
    tocadas = []
    vistos = set()
    for r in repartos:
        inv = await get_invoice(db, organization_id, uuid.UUID(str(r["invoice_id"])))
        if inv.id in vistos:
            raise InvalidInputError("Una factura aparece dos veces en el pago.", code="allocation_duplicate")
        vistos.add(inv.id)
        if inv.supplier_id != s.id:
            raise InvalidInputError(f"La factura {inv.number} es de otro proveedor.", code="invoice_other_supplier")
        if inv.status not in ("approved", "partially_paid"):
            raise ConflictError(f"La factura {inv.number} no está aprobada para pago.", code="invoice_not_payable")
        parte = to_money(r["amount"])
        if parte <= ZERO or parte > balance(inv):
            raise InvalidInputError(f"A la factura {inv.number} le quedan {balance(inv)} USD por pagar.",
                                    code="allocation_over_balance")
        pago.allocations.append(SupplierPaymentAllocation(invoice_id=inv.id, amount=parte))
        tocadas.append(inv.id)
    db.add(pago)
    await db.flush()
    if file:
        contenido, nombre, mime = file
        pago.file_mime = check_type(contenido, mime, FILE_MIME)
        pago.file_path = save_bytes(organization_id=organization_id, subfolder=f"supplier-payments/{pago.id}",
                                    filename=nombre or "comprobante", data=contenido)
    for iid in tocadas:
        _sync_status(await get_invoice(db, organization_id, iid))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="payables.payment_recorded",
                             entity_type="supplier_payment", entity_id=str(pago.id),
                             after_data={"supplier": s.name, "amount": str(monto), "invoices": len(tocadas)})
    await db.commit()
    await db.refresh(pago)
    return pago


async def invoice_out(db, invs: list[SupplierInvoice], organization_id) -> list[dict]:
    from app.modules.field_ops.models import Project
    from app.modules.finance.expenses import names

    umbral = to_money((await settings_of(db, organization_id)).two_approval_threshold)
    proveedores = {s.id: s.name for s in (await db.execute(select(Supplier).where(
        Supplier.id.in_({i.supplier_id for i in invs})))).scalars().all()} if invs else {}
    personas = await names(db, {a.user_id for i in invs for a in i.approvals})
    pids = {l.project_id for i in invs for l in i.lines if l.project_id}
    proyectos = {p.id: p.title for p in (await db.execute(select(Project).where(Project.id.in_(pids)))).scalars().all()} \
        if pids else {}
    hoy = await _today(db, organization_id)
    salida = []
    for i in invs:
        saldo = balance(i)
        salida.append({
            "id": str(i.id), "supplier_id": str(i.supplier_id), "supplier_name": proveedores.get(i.supplier_id),
            "number": i.number, "invoice_date": i.invoice_date.isoformat(), "due_date": i.due_date.isoformat(),
            "subtotal": str(to_money(i.subtotal)), "tax": str(to_money(i.tax)), "shipping": str(to_money(i.shipping)),
            "total": str(to_money(i.total)), "paid": str(paid_amount(i)), "balance": str(saldo), "status": i.status,
            "overdue_days": (hoy - i.due_date).days if saldo > ZERO and i.status not in ("void",) and hoy > i.due_date else 0,
            "scheduled_payment_date": i.scheduled_payment_date.isoformat() if i.scheduled_payment_date else None,
            "notes": i.notes, "void_reason": i.void_reason, "has_file": bool(i.file_path),
            "approvals": [{"user_name": personas.get(a.user_id), "capacity": a.capacity,
                           "approved_at": a.approved_at.isoformat()} for a in i.approvals],
            "approvals_missing": approvals_needed(i, umbral) if i.status == "pending_approval" else [],
            "lines": [{"description": l.description, "category": l.category, "quantity": str(l.quantity),
                       "unit_cost": str(to_money(l.unit_cost)), "amount": str(to_money(l.amount)),
                       "project_id": str(l.project_id) if l.project_id else None,
                       "project_title": proyectos.get(l.project_id)} for l in i.lines],
        })
    return salida


def invoices_stmt(organization_id, *, status=None, supplier_id=None, due_before=None, overdue=False, today=None,
                  project_id=None):
    stmt = select(SupplierInvoice).where(SupplierInvoice.organization_id == organization_id)
    if status == "open":
        stmt = stmt.where(SupplierInvoice.status.in_(("pending_approval", "approved", "partially_paid")))
    elif status:
        stmt = stmt.where(SupplierInvoice.status == status)
    if supplier_id:
        stmt = stmt.where(SupplierInvoice.supplier_id == supplier_id)
    if due_before:
        stmt = stmt.where(SupplierInvoice.due_date <= due_before)
    if overdue and today:
        stmt = stmt.where(SupplierInvoice.due_date < today,
                          SupplierInvoice.status.in_(("approved", "partially_paid", "pending_approval")))
    if project_id:
        stmt = stmt.where(SupplierInvoice.id.in_(select(SupplierInvoiceLine.invoice_id).where(
            SupplierInvoiceLine.project_id == project_id)))
    return stmt.order_by(SupplierInvoice.due_date, SupplierInvoice.created_at)


# ---------------------------------------------------------------------------
# Antigüedad y exportación
# ---------------------------------------------------------------------------

BUCKETS = (("current", "Al día"), ("d1_30", "1 a 30 días"), ("d31_60", "31 a 60 días"), ("d61_90", "61 a 90 días"),
           ("d90_plus", "Más de 90 días"))


def bucket_of(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "d1_30"
    if days_overdue <= 60:
        return "d31_60"
    if days_overdue <= 90:
        return "d61_90"
    return "d90_plus"


async def aging(db, *, organization_id) -> dict:
    hoy = await _today(db, organization_id)
    abiertas = (await db.execute(select(SupplierInvoice).where(
        SupplierInvoice.organization_id == organization_id,
        SupplierInvoice.status.in_(("pending_approval", "approved", "partially_paid"))))).scalars().all()
    proveedores = {s.id: s.name for s in (await db.execute(select(Supplier).where(
        Supplier.organization_id == organization_id))).scalars().all()}
    por_prov: dict = {}
    totales = {k: ZERO for k, _ in BUCKETS}
    for i in abiertas:
        saldo = balance(i)
        if saldo <= ZERO:
            continue
        b = bucket_of((hoy - i.due_date).days)
        fila = por_prov.setdefault(i.supplier_id, {"supplier_id": str(i.supplier_id),
                                                   "supplier_name": proveedores.get(i.supplier_id),
                                                   **{k: ZERO for k, _ in BUCKETS}, "total": ZERO, "invoices": 0})
        fila[b] += saldo
        fila["total"] += saldo
        fila["invoices"] += 1
        totales[b] += saldo
    filas = sorted(por_prov.values(), key=lambda f: f["total"], reverse=True)
    conv = lambda d: {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}
    return {"buckets": [{"key": k, "label": l} for k, l in BUCKETS], "rows": [conv(f) for f in filas],
            "totals": conv({**totales, "total": money_sum(totales.values())}), "as_of": hoy.isoformat()}


async def export_csv(db, *, organization_id, kind: str, date_from=None, date_to=None) -> str:
    """CSV para el contador o QuickBooks: facturas o pagos de proveedores."""
    proveedores = {s.id: s for s in (await db.execute(select(Supplier).where(
        Supplier.organization_id == organization_id))).scalars().all()}
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "payments":
        stmt = select(SupplierPayment).where(SupplierPayment.organization_id == organization_id)
        if date_from:
            stmt = stmt.where(SupplierPayment.paid_on >= date_from)
        if date_to:
            stmt = stmt.where(SupplierPayment.paid_on <= date_to)
        w.writerow(["Fecha", "Proveedor", "Monto", "Forma de pago", "Referencia", "Cuenta", "Facturas"])
        for p in (await db.execute(stmt.order_by(SupplierPayment.paid_on))).scalars().all():
            numeros = []
            for a in p.allocations:
                inv = await db.get(SupplierInvoice, a.invoice_id)
                numeros.append(f"{inv.number}:{to_money(a.amount)}")
            w.writerow([p.paid_on.isoformat(), proveedores[p.supplier_id].name, str(to_money(p.amount)),
                        PAYMENT_METHODS.get(p.method, p.method), p.reference or "", p.bank_account or "",
                        " | ".join(numeros)])
    else:
        stmt = select(SupplierInvoice).where(SupplierInvoice.organization_id == organization_id)
        if date_from:
            stmt = stmt.where(SupplierInvoice.invoice_date >= date_from)
        if date_to:
            stmt = stmt.where(SupplierInvoice.invoice_date <= date_to)
        w.writerow(["Proveedor", "Factura", "Fecha", "Vence", "Subtotal", "Impuestos", "Envío", "Total", "Pagado",
                    "Saldo", "Estado"])
        for i in (await db.execute(stmt.order_by(SupplierInvoice.invoice_date))).scalars().all():
            w.writerow([proveedores[i.supplier_id].name, i.number, i.invoice_date.isoformat(), i.due_date.isoformat(),
                        str(to_money(i.subtotal)), str(to_money(i.tax)), str(to_money(i.shipping)),
                        str(to_money(i.total)), str(paid_amount(i)), str(balance(i)), i.status])
    return buf.getvalue()


async def supplier_balances(db, organization_id) -> dict:
    abiertas = (await db.execute(select(SupplierInvoice).where(
        SupplierInvoice.organization_id == organization_id,
        SupplierInvoice.status.in_(("pending_approval", "approved", "partially_paid"))))).scalars().all()
    saldos: dict = {}
    for i in abiertas:
        saldos[i.supplier_id] = saldos.get(i.supplier_id, ZERO) + balance(i)
    return saldos
