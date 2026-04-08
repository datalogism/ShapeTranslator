"""ShEx → ShexJE converter (public API).

ShexJE is the canonical intermediate format of shaclex-py.  Internally the
conversion passes through the normalized canonical representation, which is an
implementation detail not exposed in the public interface.
"""
from __future__ import annotations

from shaclex_py.schema.shex import ShExSchema
from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje


def convert_shex_to_shexje(shex: ShExSchema) -> ShexJESchema:
    """Convert a ShEx schema to ShexJE format.

    Args:
        shex: Parsed ShEx schema (from :func:`parse_shex_file`).

    Returns:
        Equivalent ShexJE schema.
    """
    return convert_canonical_to_shexje(convert_shex_to_canonical(shex))
