"""Convert ShexJESchema to ShEx model (via canonical intermediate)."""
from __future__ import annotations

from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.schema.shex import ShExSchema
from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
from shaclex_py.converter.canonical_to_shex import convert_canonical_to_shex


def convert_shexje_to_shex(schema: ShexJESchema) -> ShExSchema:
    """Convert a :class:`ShexJESchema` to a :class:`ShExSchema`.

    Uses the canonical intermediate representation as the bridge.

    Args:
        schema: Source :class:`ShexJESchema`.

    Returns:
        Equivalent :class:`ShExSchema`.
    """
    canonical = convert_shexje_to_canonical(schema)
    return convert_canonical_to_shex(canonical)
