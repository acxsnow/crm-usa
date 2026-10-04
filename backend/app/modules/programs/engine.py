"""El motor del formulario: con la definición de una versión y unas
respuestas, dice qué se ve, qué falta y qué está mal (spec D1.4).

Es código puro, sin base de datos: lo usan la vista previa del administrador
(módulo 1) y la pantalla del vendedor (módulo 2), y los dos tienen que decir
exactamente lo mismo.

Formato de la definición (lo arma `service.version_definition`):

    {"steps": [{"code", "title", "phase", "fields": [
        {"key", "label", "help", "type", "options", "validation",
         "requirement", "condition", "internal", "sensitive"}, ...]}, ...]}

Condiciones (sin lenguaje de expresiones, D3):

    {"field": "home.gas_type", "eq": "natural_gas"}
    {"field": "eligibility.programs", "in": ["other_government_nonprofit"]}
    {"field": "home.has_disability_or_chronic_condition", "not_empty": true}
"""
import re
from datetime import date, time
from decimal import Decimal, InvalidOperation

EMPTY = (None, "", [], {})

_FORMATS = {
    "email": (re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"), "No es un correo válido."),
    "phone": (re.compile(r"^\+?[\d\s().-]{7,20}$"), "No es un teléfono válido."),
    "zip": (re.compile(r"^\d{5}(-\d{4})?$"), "El ZIP debe tener 5 dígitos."),
}


def condition_fields(condition: dict | None) -> list[str]:
    """Los campos que menciona una condición (para validarla al publicar)."""
    if not condition:
        return []
    return [condition["field"]] if "field" in condition else []


def check_condition(condition: dict) -> str | None:
    """Error de forma de una condición, o None si está bien."""
    if not isinstance(condition, dict) or not condition.get("field"):
        return "La condición necesita el campo del que depende."
    operadores = [k for k in ("eq", "in", "not_empty") if k in condition]
    if len(operadores) != 1:
        return "La condición usa exactamente uno de: es igual a, es alguno de, tiene respuesta."
    if "in" in condition and not isinstance(condition["in"], list):
        return "«Es alguno de» necesita una lista de valores."
    return None


def condition_met(condition: dict | None, answers: dict) -> bool:
    if not condition:
        return True
    valor = answers.get(condition.get("field"))
    if "eq" in condition:
        objetivo = condition["eq"]
        return objetivo in valor if isinstance(valor, list) else valor == objetivo
    if "in" in condition:
        opciones = set(condition["in"])
        return bool(opciones & set(valor)) if isinstance(valor, list) else valor in opciones
    if "not_empty" in condition:
        return (valor not in EMPTY) == bool(condition["not_empty"])
    return True


def validate_value(field: dict, value) -> str | None:
    """Error de formato del valor, o None. No mira obligatoriedad."""
    if value in EMPTY:
        return None
    tipo = field["type"]
    reglas = field.get("validation") or {}
    opciones = {o["value"] for o in (field.get("options") or [])}

    if tipo in ("integer", "decimal"):
        try:
            numero = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return "Debe ser un número."
        if tipo == "integer" and numero != numero.to_integral_value():
            return "Debe ser un número entero."
        if reglas.get("min") is not None and numero < Decimal(str(reglas["min"])):
            return f"Debe ser al menos {reglas['min']}."
        if reglas.get("max") is not None and numero > Decimal(str(reglas["max"])):
            return f"Debe ser como máximo {reglas['max']}."
    elif tipo == "single_select":
        if value not in opciones:
            return "Elige una de las opciones."
    elif tipo == "multi_select":
        if not isinstance(value, list) or not set(value) <= opciones:
            return "Elige entre las opciones."
        excluyentes = set(reglas.get("exclusive") or [])
        if excluyentes & set(value) and len(value) > 1:
            nombres = {o["value"]: o["label"] for o in field.get("options") or []}
            etiqueta = ", ".join(nombres.get(v, v) for v in excluyentes & set(value))
            return f"«{etiqueta}» no se combina con otras opciones."
    elif tipo == "yes_no":
        if value not in (True, False, "yes", "no"):
            return "Responde sí o no."
    elif tipo == "date":
        try:
            date.fromisoformat(str(value))
        except ValueError:
            return "No es una fecha válida."
    elif tipo == "time":
        try:
            time.fromisoformat(str(value))
        except ValueError:
            return "No es una hora válida."
    elif tipo == "terms_checkbox":
        if value is not True:
            return "Hay que aceptar la autorización y los términos."
    elif tipo in ("text", "textarea", "email", "phone"):
        texto = str(value).strip()
        if reglas.get("min_length") and len(texto) < reglas["min_length"]:
            return f"Escribe al menos {reglas['min_length']} caracteres."
        if reglas.get("max_length") and len(texto) > reglas["max_length"]:
            return f"Máximo {reglas['max_length']} caracteres."
        formato = reglas.get("format") or (tipo if tipo in ("email", "phone") else None)
        if formato in _FORMATS:
            patron, mensaje = _FORMATS[formato]
            if not patron.match(texto):
                return mensaje
    return None


def evaluate(definition: dict, answers: dict, *, include_internal: bool = True) -> dict:
    """Recorre los pasos y devuelve, por paso, los campos visibles con su
    error, más la lista de lo que falta para poder enviar.

    - Un campo condicional solo se ve (y solo se exige) si su condición se
      cumple. `required` y `conditional` visibles bloquean el envío vacíos.
    - `include_internal=False` esconde los de uso interno (lo que ve el
      cliente o se le muestra al vendedor frente al cliente)."""
    from app.modules.programs.models import SYSTEM_TYPES

    pasos, faltan, errores = [], [], {}
    for paso in definition.get("steps", []):
        visibles = []
        for campo in paso["fields"]:
            if campo.get("internal") and not include_internal:
                continue
            if not condition_met(campo.get("condition"), answers):
                continue
            valor = answers.get(campo["key"])
            error = validate_value(campo, valor)
            exigido = campo["requirement"] in ("required", "conditional") and campo["type"] not in SYSTEM_TYPES
            vacio = valor in EMPTY or (campo["type"] == "terms_checkbox" and valor is not True)
            if error:
                errores[campo["key"]] = error
            if exigido and vacio:
                faltan.append({"step": paso["code"], "key": campo["key"], "label": campo["label"]})
            visibles.append({**campo, "error": error, "missing": exigido and vacio})
        pasos.append({"code": paso["code"], "title": paso["title"], "phase": paso.get("phase"),
                      "fields": visibles, "complete": not any(f["missing"] or f["error"] for f in visibles)})
    return {"steps": pasos, "missing": faltan, "errors": errores,
            "can_submit": not faltan and not errores}
