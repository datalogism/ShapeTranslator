"""Serialize a ShexJESchema to a ShexJE JSON string."""
from __future__ import annotations

import json

from shaclex_py.schema.shexje import ShexJESchema


def serialize_shexje(schema: ShexJESchema, *, indent: int = 2) -> str:
    """Serialize *schema* to a deterministic ShexJE JSON string.

    Args:
        schema: The :class:`ShexJESchema` to serialize.
        indent: JSON indentation spaces (default 2).

    Returns:
        UTF-8 JSON string.
    """
    return json.dumps(schema.to_dict(), indent=indent, ensure_ascii=False)
