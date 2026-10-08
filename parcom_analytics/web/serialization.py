"""Strict conversion of explicitly constructed DTOs, never arbitrary backend objects."""

from datetime import date, datetime
import math


def json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("DTO timestamps require a timezone")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("DTO map keys must be strings")
        return {key: json_value(item) for key, item in value.items()}
    raise TypeError(f"Unsupported DTO type: {type(value).__name__}")
