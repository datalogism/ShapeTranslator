"""Convert canonical JSON model to SHACL model.

Reverse mapping of shacl_to_canonical:
- targetClass → sh:targetClass
- classRef → sh:class
- classRefOr → sh:class [ sh:or (...) ]
- iriStem → sh:pattern (^stem/)
- cardinality min/max → sh:minCount / sh:maxCount
"""
from __future__ import annotations

from typing import Optional, Union

from shaclex_py.schema.common import IRI, UNBOUNDED, Literal, NodeKind, Path, Prefix
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.canonical import (
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)

SHACL_SHAPES_BASE = "http://shaclshapes.org/"

NODE_KIND_MAP = {
    "IRI": NodeKind.IRI,
    "BlankNode": NodeKind.BLANK_NODE,
    "Literal": NodeKind.LITERAL,
    "BlankNodeOrIRI": NodeKind.BLANK_NODE_OR_IRI,
    "BlankNodeOrLiteral": NodeKind.BLANK_NODE_OR_LITERAL,
    "IRIOrLiteral": NodeKind.IRI_OR_LITERAL,
}

# Standard SHACL prefixes
STANDARD_SHACL_PREFIXES = [
    Prefix("sh", "http://www.w3.org/ns/shacl#"),
    Prefix("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    Prefix("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    Prefix("xsd", "http://www.w3.org/2001/XMLSchema#"),
    Prefix("schema", "http://schema.org/"),
    Prefix("owl", "http://www.w3.org/2002/07/owl#"),
    Prefix("yago", "http://yago-knowledge.org/resource/"),
]


def _canonical_value_to_model(val: Union[str, dict]) -> Union[IRI, Literal]:
    """Convert a canonical JSON value back to IRI or Literal."""
    if isinstance(val, str):
        return IRI(val)
    if isinstance(val, dict):
        dt = IRI(val["datatype"]) if "datatype" in val else None
        lang = val.get("language")
        return Literal(value=val["value"], datatype=dt, language=lang)
    return IRI(str(val))


def _convert_property(prop: CanonicalProperty) -> PropertyShape:
    """Convert a CanonicalProperty to a SHACL PropertyShape."""
    alternative_paths = None
    if prop.pathAlternatives is not None:
        alternative_paths = [IRI(p) for p in prop.pathAlternatives]
        path = Path(iri=alternative_paths[0])
    else:
        path = Path(iri=IRI(prop.path))

    # Cardinality → min/maxCount
    mn = prop.cardinality.min if prop.cardinality.min > 0 else None
    mx = prop.cardinality.max if prop.cardinality.max != UNBOUNDED else None

    datatype = None
    class_ = None
    node_kind = None
    pattern = None
    has_value = None
    in_values = None
    node = None
    or_constraints = None

    if prop.datatype is not None:
        datatype = IRI(prop.datatype)
    elif prop.classRef is not None:
        class_ = IRI(prop.classRef)
    elif prop.classRefOr is not None:
        or_constraints = [IRI(c) for c in prop.classRefOr]
    elif prop.nodeKind is not None:
        node_kind = NODE_KIND_MAP.get(prop.nodeKind)
    elif prop.hasValue is not None:
        has_value = _canonical_value_to_model(prop.hasValue)
    elif prop.inValues is not None:
        in_values = [_canonical_value_to_model(v) for v in prop.inValues]
    elif prop.iriStem is not None:
        pattern = f"^{prop.iriStem}/"
    elif prop.nodeRef is not None:
        node = IRI(prop.nodeRef)

    # pattern is applied independently: it can accompany a primary constraint
    if prop.pattern is not None:
        pattern = prop.pattern

    return PropertyShape(
        path=path,
        datatype=datatype,
        class_=class_,
        node_kind=node_kind,
        min_count=mn,
        max_count=mx,
        pattern=pattern,
        has_value=has_value,
        in_values=in_values,
        node=node,
        or_constraints=or_constraints,
        alternative_paths=alternative_paths,
    )


def convert_canonical_to_shacl(canonical: CanonicalSchema) -> SHACLSchema:
    """Convert a canonical JSON schema to a SHACL schema.

    Args:
        canonical: The canonical schema to convert.

    Returns:
        Equivalent SHACL schema.
    """
    shapes: list[NodeShape] = []

    for cshape in canonical.shapes:
        shape_iri = IRI(f"{SHACL_SHAPES_BASE}{cshape.name}Shape")
        target_class = IRI(cshape.targetClass) if cshape.targetClass else None

        properties: list[PropertyShape] = []

        for cprop in cshape.properties:
            ps = _convert_property(cprop)
            properties.append(ps)

        or_datatypes = (
            [IRI(d) for d in cshape.datatypeOr]
            if cshape.datatypeOr else None
        )

        shape_node_kind = NODE_KIND_MAP.get(cshape.nodeKind) if cshape.nodeKind else None
        shape_node_datatype = IRI(cshape.datatype) if cshape.datatype else None
        shape_node_in_values = (
            [_canonical_value_to_model(v) for v in cshape.inValues]
            if cshape.inValues else None
        )

        shapes.append(NodeShape(
            iri=shape_iri,
            target_class=target_class,
            properties=properties,
            closed=cshape.closed,
            or_datatypes=or_datatypes,
            node_kind=shape_node_kind,
            node_datatype=shape_node_datatype,
            node_in_values=shape_node_in_values,
        ))

    return SHACLSchema(shapes=shapes, prefixes=list(STANDARD_SHACL_PREFIXES))
