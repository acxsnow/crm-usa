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
