"""SHACL → ShexJE converter (public API).

ShexJE is the canonical intermediate format of shaclex-py.  Internally the
conversion passes through the normalized canonical representation, which is an
implementation detail not exposed in the public interface.
"""
from __future__ import annotations

from shaclex_py.schema.shacl import SHACLSchema
from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje


def convert_shacl_to_shexje(shacl: SHACLSchema) -> ShexJESchema:
    """Convert a SHACL schema to ShexJE format.

    Args:
        shacl: Parsed SHACL schema (from :func:`parse_shacl_file`).

    Returns:
        Equivalent ShexJE schema.
    """
    return convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
