"""Convert SHACL model to ShEx model via ShexJE (canonical intermediate).

Pipeline: SHACL → ShexJE → ShEx

The old direct converter has been replaced by this two-step chain so that
there is a single authoritative SHACL→ShexJE mapping and a single
authoritative ShexJE→ShEx mapping, with no duplicated rule logic.
"""
from __future__ import annotations

from typing import Optional

from shaclex_py.schema.shacl import SHACLSchema
from shaclex_py.schema.shex import ShExSchema
from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex


def convert_shacl_to_shex(
    shacl: SHACLSchema,
    label_map: Optional[dict[str, str]] = None,
) -> ShExSchema:
    """Convert a SHACL schema to a ShEx schema via ShexJE.

    Pipeline: SHACL → ShexJE → ShEx

    Args:
        shacl:     The SHACL schema to convert.
        label_map: Optional Wikidata IRI → English label mapping forwarded to
                   the serialiser for label-aware ShExC output (comments,
                   shape names).  Not consumed during conversion itself.

    Returns:
        Equivalent ShEx schema.
    """
    shexje = convert_shacl_to_shexje(shacl)
    return convert_shexje_to_shex(shexje)
