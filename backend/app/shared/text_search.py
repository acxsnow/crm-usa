"""Patrón de búsqueda «contiene» para `ilike`, con el texto tal cual.

Sin escapar, `%` y `_` funcionan como comodines: buscar «%» trae todo (D-004).
Se usa siempre con `escape=LIKE_ESCAPE`:

    columna.ilike(contains_pattern(q), escape=LIKE_ESCAPE)
"""
LIKE_ESCAPE = "\\"


def contains_pattern(q: str) -> str:
    """El byte nulo se quita: Postgres lo rechaza con un 500 (hallazgo M8 del
    ataque del 24 oct)."""
    texto = q.replace("\x00", "").strip()
    return "%" + texto.replace("\\", "\\\\").replace("%", "\%").replace("_", "\_") + "%"
