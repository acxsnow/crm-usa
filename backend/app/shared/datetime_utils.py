"""SQLite (used by the test suite) doesn't enforce timezone-aware storage
the way PostgreSQL does, so a `DateTime(timezone=True)` column can come back
naive on read even though it was written as UTC-aware. Comparing that naive
value against `datetime.now(timezone.utc)` raises TypeError. This helper
normalizes either shape to an aware UTC datetime before comparison, so
expiry checks (password reset tokens, invitations) behave the same against
SQLite and PostgreSQL."""
from datetime import datetime, timezone


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
