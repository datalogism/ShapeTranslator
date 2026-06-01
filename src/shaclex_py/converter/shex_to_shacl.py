"""Convert ShEx model to SHACL model via ShexJE (canonical intermediate).

Pipeline: ShEx → ShexJE → SHACL

The old direct converter has been replaced by this two-step chain so that
there is a single authoritative ShEx→ShexJE mapping and a single
authoritative ShexJE→SHACL mapping, with no duplicated rule logic.
"""
from __future__ import annotations

from shaclex_py.schema.shex import ShExSchema
from shaclex_py.schema.shacl import SHACLSchema
from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl


def convert_shex_to_shacl(shex: ShExSchema) -> SHACLSchema:
    """Convert a ShEx schema to a SHACL schema via ShexJE.

    Pipeline: ShEx → ShexJE → SHACL

    Args:
        shex: The ShEx schema to convert.

    Returns:
        Equivalent SHACL schema.
    """
    shexje = convert_shex_to_shexje(shex)
    return convert_shexje_to_shacl(shexje)
