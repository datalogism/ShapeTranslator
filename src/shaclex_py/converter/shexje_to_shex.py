"""ShexJE → ShEx converter (public API).

ShexJE is the canonical intermediate format of shaclex-py.  Internally the
conversion passes through the normalized canonical representation, which is an
implementation detail not exposed in the public interface.
"""
from __future__ import annotations

from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.schema.shex import ShExSchema
from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
from shaclex_py.converter.canonical_to_shex import convert_canonical_to_shex


def convert_shexje_to_shex(shexje: ShexJESchema) -> ShExSchema:
    """Convert a ShexJE schema to ShEx format.

    Args:
        shexje: Parsed ShexJE schema (from :func:`parse_shexje_file`).

    Returns:
        Equivalent ShEx schema.
    """
    return convert_canonical_to_shex(convert_shexje_to_canonical(shexje))
