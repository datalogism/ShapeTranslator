"""Convert canonical JSON model to SHACL model.

Reverse mapping of shacl_to_canonical:
- targetClass → sh:targetClass + rdf:type hasValue property
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
RDF_TYPE_IRI = IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

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
    elif prop.pattern is not None:
        pattern = prop.pattern
    elif prop.nodeRef is not None:
        node = IRI(prop.nodeRef)

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

        # Re-add rdf:type hasValue when targetClass is present
        # (shacl_to_canonical strips it; we restore it for faithful SHACL)
        if target_class:
            rdf_type_prop = PropertyShape(
                path=Path(iri=RDF_TYPE_IRI),
                has_value=target_class,
                min_count=1,
                max_count=1,
            )
            properties.append(rdf_type_prop)

        for cprop in cshape.properties:
            ps = _convert_property(cprop)
            properties.append(ps)

        shapes.append(NodeShape(
            iri=shape_iri,
            target_class=target_class,
            properties=properties,
            closed=cshape.closed,
        ))

    return SHACLSchema(shapes=shapes, prefixes=list(STANDARD_SHACL_PREFIXES))
