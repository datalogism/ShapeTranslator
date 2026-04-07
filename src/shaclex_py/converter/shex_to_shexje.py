"""Convert ShEx model to ShexJESchema (via canonical intermediate)."""
from __future__ import annotations

from shaclex_py.schema.shex import ShExSchema
from shaclex_py.schema.shexje import ShexJESchema
from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def convert_shex_to_shexje(
    shex: ShExSchema,
    type_predicate: str = _RDF_TYPE,
) -> ShexJESchema:
    """Convert a :class:`ShExSchema` to a :class:`ShexJESchema`.

    Uses the canonical intermediate representation as the bridge.

    Args:
        shex: Source :class:`ShExSchema`.
        type_predicate: IRI of the predicate used for class membership in
            generated value shapes (default: ``rdf:type``).

    Returns:
        Equivalent :class:`ShexJESchema`.
    """
    canonical = convert_shex_to_canonical(shex)
    return convert_canonical_to_shexje(canonical, type_predicate=type_predicate)
