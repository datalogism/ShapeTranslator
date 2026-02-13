"""Serialize a CanonicalSchema to a deterministic JSON string."""
from __future__ import annotations

import json

from models.json_model import CanonicalSchema


def serialize_json(schema: CanonicalSchema) -> str:
    """Serialize a canonical schema to a JSON string.

    Output is deterministic: shapes sorted by name, properties sorted by path,
    value lists sorted, and consistent indentation.

    Args:
        schema: The canonical schema to serialize.

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(schema.to_dict(), indent=2, ensure_ascii=False)
