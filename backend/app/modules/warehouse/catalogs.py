"""Catálogos de la bodega.

Viven en código, no en enums de Postgres, por la misma razón que las categorías
de evidencia (`field_ops/catalogs.py`): agregar una categoría es cambiar un
diccionario, no escribir una migración con `ALTER TYPE`. La base guarda el
código; la etiqueta en español viaja en `GET /warehouse/catalogs` para que el
frontend no repita estas listas ni se desactualice.

Las categorías y las unidades son las de la hoja «Listas» del cuestionario del
19 de octubre de 2026, donde el cliente puede cambiarlas o agregar las suyas.
"""
from enum import StrEnum

# Hoja «Listas», columna Categorías.
ITEM_CATEGORIES: dict[str, str] = {
    "pipe_copper": "Tubería y cobre",
    "electrical": "Eléctrico",
    "refrigerant": "Refrigerante",
    "ducts": "Ductos",
    "supports": "Soportes y fijación",
    "consumables": "Consumibles",
    "equipment": "Equipos",
    "tools": "Herramienta",
    "other": "Otro",
}

# Hoja «Listas», columna Unidades.
ITEM_UNITS: dict[str, str] = {
    "unit": "unidades",
    "ft": "pies (ft)",
    "m": "metros",
    "roll": "rollos",
    "box": "cajas",
    "gal": "galones",
    "lb": "libras",
    "set": "juegos",
}

# Qué hace cada movimiento. El signo lo pone el servicio, no quien lo llama:
# aquí solo se declara si suma o resta a la ubicación.
class MovementType(StrEnum):
    ENTRADA = "entrada"        # compra recibida o conteo inicial
    SALIDA = "salida"          # orden de salida entregada al técnico
    DEVOLUCION = "devolucion"  # el sobrante vuelve a bodega
    TRASLADO = "traslado"      # bodega → camioneta (y viceversa)
    AJUSTE = "ajuste"          # diferencia de un conteo físico


MOVEMENT_TYPES: dict[str, str] = {
    MovementType.ENTRADA: "Entrada",
    MovementType.SALIDA: "Salida",
    MovementType.DEVOLUCION: "Devolución",
    MovementType.TRASLADO: "Traslado",
    MovementType.AJUSTE: "Ajuste",
}

# El movimiento que sube el saldo se guarda con cantidad positiva y el que lo
# baja con negativa. Así el saldo de una ubicación es la suma de sus
# movimientos, y el libro se puede auditar sin recalcular nada.
MOVEMENT_SIGN: dict[str, int] = {
    MovementType.ENTRADA: 1,
    MovementType.DEVOLUCION: 1,
    MovementType.SALIDA: -1,
    MovementType.TRASLADO: -1,
    MovementType.AJUSTE: 1,
}

# Tipos de ubicación: la bodega (hay una sola) y la camioneta de cada técnico,
# que es lo que permite «el sobrante queda en la camioneta» cuando la obra pasa
# de dos días.
class LocationKind(StrEnum):
    WAREHOUSE = "warehouse"
    TRUCK = "truck"


LOCATION_KINDS: dict[str, str] = {
    LocationKind.WAREHOUSE: "Bodega",
    LocationKind.TRUCK: "Camioneta",
}

DEFAULT_WAREHOUSE_NAME = "Bodega"

# La orden de salida (punto 1 del cuestionario): sin pasar por `autorizada` el
# material no sale. `borrador` todavía no tiene número; el número se asigna al
# mandarla a autorizar, para que un borrador que nunca se envió no consuma un
# número de la serie `SAL`.
class ReleaseStatus(StrEnum):
    BORRADOR = "borrador"
    POR_AUTORIZAR = "por_autorizar"
    AUTORIZADA = "autorizada"
    RECHAZADA = "rechazada"
    ENTREGADA = "entregada"


RELEASE_STATUSES: dict[str, str] = {
    ReleaseStatus.BORRADOR: "Borrador",
    ReleaseStatus.POR_AUTORIZAR: "Por autorizar",
    ReleaseStatus.AUTORIZADA: "Autorizada",
    ReleaseStatus.RECHAZADA: "Rechazada",
    ReleaseStatus.ENTREGADA: "Entregada",
}

# De dónde salió la línea: de la lista predefinida del tipo de trabajo (fase 2)
# o puesta a mano por quien armó la orden.
class LineOrigin(StrEnum):
    LISTA = "lista"
    MANUAL = "manual"


LINE_ORIGINS: dict[str, str] = {
    LineOrigin.LISTA: "Lista predefinida",
    LineOrigin.MANUAL: "A mano",
}

# Cuál es el siguiente estado al que se puede pasar. Se declara aquí para que la
# pantalla no tenga que adivinar qué botones mostrar.
RELEASE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    ReleaseStatus.BORRADOR: (ReleaseStatus.POR_AUTORIZAR,),
    ReleaseStatus.POR_AUTORIZAR: (ReleaseStatus.AUTORIZADA, ReleaseStatus.RECHAZADA),
    ReleaseStatus.AUTORIZADA: (ReleaseStatus.ENTREGADA,),
    ReleaseStatus.RECHAZADA: (),
    ReleaseStatus.ENTREGADA: (),
}


# El presupuesto del proyecto (punto 3). Los códigos son los mismos que ya usa
# el costo real (`finance/models.py::COST_CATEGORIES`) más `labor`: comparar
# estimado contra real por categoría exige que la categoría del presupuesto y la
# del gasto sean el mismo texto, o el reporte queda con dos filas para lo mismo.
class BudgetCategory(StrEnum):
    MATERIALS = "materials"
    EQUIPMENT = "equipment"
    LABOR = "labor"
    CONTRACTOR = "contractor"
    PERMIT = "permit"
    SERVICES = "services"
    OTHER = "other"
    SALES_REP = "sales_rep"
    CONSUMABLES = "consumables"


BUDGET_CATEGORIES: dict[str, str] = {
    BudgetCategory.MATERIALS: "Material",
    BudgetCategory.EQUIPMENT: "Equipo",
    BudgetCategory.LABOR: "Mano de obra",
    BudgetCategory.CONTRACTOR: "Contratista",
    BudgetCategory.PERMIT: "Permiso",
    BudgetCategory.SERVICES: "Servicios",
    BudgetCategory.OTHER: "Otro",
    BudgetCategory.SALES_REP: "Representante",
    BudgetCategory.CONSUMABLES: "Consumibles",
}

# Costo del trabajo (spec 2026-10-22): los conceptos con los que Aldo lee un
# trabajo, en su orden. Cada categoría del presupuesto o del costo real cae en
# uno; la ganancia no es concepto: es lo que sobra del precio.
JOB_CONCEPTS: dict[str, str] = {
    "sales_rep": "Representante",
    "permits": "Permisos",
    "materials": "Materiales",
    "labor": "Mano de obra",
    "other": "Otros",
}
CONCEPT_OF_CATEGORY: dict[str, str] = {
    BudgetCategory.SALES_REP: "sales_rep",
    BudgetCategory.PERMIT: "permits",
    BudgetCategory.MATERIALS: "materials",
    BudgetCategory.EQUIPMENT: "materials",
    BudgetCategory.CONSUMABLES: "materials",
    BudgetCategory.LABOR: "labor",
    BudgetCategory.CONTRACTOR: "labor",
    BudgetCategory.SERVICES: "other",
    BudgetCategory.OTHER: "other",
    "field_expenses": "other",
}

# Plantillas de costo: un renglón vale un % del precio o un monto fijo.
# `target_profit` solo existe en la plantilla (la ganancia objetivo); nunca se
# copia al presupuesto, porque la ganancia no es un costo.
TEMPLATE_MODES: dict[str, str] = {"percent": "Porcentaje del precio", "amount": "Monto fijo"}
TARGET_PROFIT = "target_profit"
TEMPLATE_CATEGORIES: dict[str, str] = {**BUDGET_CATEGORIES, TARGET_PROFIT: "Ganancia objetivo"}
TEMPLATE_APPLIES_TO: dict[str, str] = {"rebate": "Rebate", "particular": "Particular", "both": "Ambos"}

# Costos reales que se anotan a mano (lo que en Housecall Pro es «Labor»).
COST_ENTRY_CATEGORIES: tuple[str, ...] = (
    BudgetCategory.LABOR, BudgetCategory.CONTRACTOR, BudgetCategory.SALES_REP,
    BudgetCategory.PERMIT, BudgetCategory.CONSUMABLES, BudgetCategory.OTHER,
)

# Cobro adicional al dueño de casa (breaker, más cable…): fuera de la factura al
# programa; casi siempre en efectivo, que el técnico entrega a Aldo.
EXTRA_CHARGE_METHODS: dict[str, str] = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia",
                                        "check": "Cheque", "other": "Otro"}

# `borrador` se edita; `aprobado` es el que cuenta para la comparación;
# `reemplazado` es el que quedó atrás cuando se aprobó otro: el historial no se
# borra, pero solo un presupuesto por proyecto está vigente.
class BudgetStatus(StrEnum):
    BORRADOR = "borrador"
    APROBADO = "aprobado"
    REEMPLAZADO = "reemplazado"


BUDGET_STATUSES: dict[str, str] = {
    BudgetStatus.BORRADOR: "Borrador",
    BudgetStatus.APROBADO: "Aprobado",
    BudgetStatus.REEMPLAZADO: "Reemplazado",
}


def code_of(label: str | None, catalog: dict[str, str], fallback: str) -> tuple[str, bool]:
    """Código del catálogo a partir de la etiqueta que trae el Excel.

    Devuelve `(código, reconocido)`. El cliente puede escribir el nombre con
    otra capitalización o dejar la celda vacía; cuando no se reconoce se usa el
    comodín (`other` / `unit`) y quien importa lo reporta fila por fila en vez
    de abortar la carga entera."""
    if label is None or not str(label).strip():
        return fallback, True
    buscado = str(label).strip().casefold()
    for code, nombre in catalog.items():
        if nombre.casefold() == buscado or code.casefold() == buscado:
            return code, True
    return fallback, False
