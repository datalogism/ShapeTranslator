"""Convert a SHACLSchema to a CanonicalSchema.

Usage::

    from shaclex_py.parser.shacl_parser import parse_shacl
    from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical

    shacl = parse_shacl(ttl_text)
    canonical = convert_shacl_to_canonical(shacl)
"""
from __future__ import annotations

from shaclex_py.schema.canonical import CanonicalProperty, CanonicalSchema, CanonicalShape
from shaclex_py.schema.common import Cardinality, NodeKind, UNBOUNDED
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema


# ---------------------------------------------------------------------------
# Cardinality normalisation
# ---------------------------------------------------------------------------

def _card(min_count, max_count) -> Cardinality:
    """Normalise SHACL min/max to canonical Cardinality.

    SHACL defaults: min = 0, max = unbounded (-1).
    """
    mn = min_count if min_count is not None else 0
    mx = max_count if max_count is not None else UNBOUNDED
    return Cardinality(min=mn, max=mx)


# ---------------------------------------------------------------------------
# PropertyShape → CanonicalProperty
# ---------------------------------------------------------------------------

def _convert_property(ps: PropertyShape) -> CanonicalProperty | None:
    """Convert a SHACL PropertyShape to a CanonicalProperty.

    Returns None if the path cannot be resolved to a simple IRI string
    (e.g. complex SPARQL paths — those are not used for classification).
    """
    # Resolve path to a plain string IRI
    path_iri = None
    path = ps.path
    if hasattr(path, "iri") and hasattr(path.iri, "value"):
        path_iri = path.iri.value
    elif isinstance(path, str):
        path_iri = path
    if not path_iri:
        return None

    cardinality = _card(ps.min_count, ps.max_count)

    # Datatype
    datatype = ps.datatype.value if ps.datatype is not None else None

    # Class constraints
    class_ref = ps.class_.value if ps.class_ is not None else None
    class_ref_or: list[str] | None = None
    if ps.or_constraints:
        class_ref_or = [c.value for c in ps.or_constraints]
        class_ref = None  # or_constraints takes precedence over single class_

    # NodeKind
    node_kind: str | None = None
    if ps.node_kind is not None:
        node_kind = ps.node_kind.value if isinstance(ps.node_kind, NodeKind) else str(ps.node_kind)

    # NodeRef (sh:node — reference to another shape)
    node_ref = ps.node.value if ps.node is not None else None

    return CanonicalProperty(
        path=path_iri,
        cardinality=cardinality,
        datatype=datatype,
        classRef=class_ref,
        classRefOr=class_ref_or,
        nodeKind=node_kind,
        pattern=ps.pattern,
        nodeRef=node_ref,
    )


# ---------------------------------------------------------------------------
# NodeShape → CanonicalShape
# ---------------------------------------------------------------------------

def _convert_shape(ns: NodeShape) -> CanonicalShape:
    name = ns.iri.value if hasattr(ns.iri, "value") else str(ns.iri)
    target_class = ns.target_class.value if ns.target_class is not None else None

    properties: list[CanonicalProperty] = []
    for ps in ns.properties:
        cp = _convert_property(ps)
        if cp is not None:
            properties.append(cp)

    return CanonicalShape(name=name, targetClass=target_class, properties=properties)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def convert_shacl_to_canonical(shacl: SHACLSchema) -> CanonicalSchema:
    """Convert a parsed SHACLSchema to a CanonicalSchema."""
    shapes = [_convert_shape(ns) for ns in shacl.shapes]
    return CanonicalSchema(shapes=shapes)
