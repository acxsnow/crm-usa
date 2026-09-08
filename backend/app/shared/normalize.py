"""Normalization helpers used for duplicate detection (spec 7.2)."""
import re


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def normalize_phone(phone: str | None) -> str | None:
    """Keeps digits only, drops a leading US country code, so '(714) 805-2898',
    '7148052898' and '+1 714-805-2898' all normalize the same way."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def normalize_address(street: str | None, unit: str | None, city: str | None, zip_code: str | None) -> str | None:
    parts = [p.strip().lower() for p in [street, unit, city, zip_code] if p and p.strip()]
    if not parts:
        return None
    normalized = " ".join(parts)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None
