"""Convert ShexJESchema to SHACL model (via canonical intermediate)."""
from __future__ import annotations

from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.schema.shacl import SHACLSchema
from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
from shaclex_py.converter.canonical_to_shacl import convert_canonical_to_shacl


def convert_shexje_to_shacl(schema: ShexJESchema) -> SHACLSchema:
    """Convert a :class:`ShexJESchema` to a :class:`SHACLSchema`.

    Uses the canonical intermediate representation as the bridge.

    Args:
        schema: Source :class:`ShexJESchema`.

    Returns:
        Equivalent :class:`SHACLSchema`.
    """
    canonical = convert_shexje_to_canonical(schema)
    return convert_canonical_to_shacl(canonical)
