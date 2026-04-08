"""ShexJE → SHACL converter (public API).

ShexJE is the canonical intermediate format of shaclex-py.  Internally the
conversion passes through the normalized canonical representation, which is an
implementation detail not exposed in the public interface.
"""
from __future__ import annotations

from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.schema.shacl import SHACLSchema
from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
from shaclex_py.converter.canonical_to_shacl import convert_canonical_to_shacl


def convert_shexje_to_shacl(shexje: ShexJESchema) -> SHACLSchema:
    """Convert a ShexJE schema to SHACL format.

    Args:
        shexje: Parsed ShexJE schema (from :func:`parse_shexje_file`).

    Returns:
        Equivalent SHACL schema.
    """
    return convert_canonical_to_shacl(convert_shexje_to_canonical(shexje))
