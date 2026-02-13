"""Convert SHACL model to canonical JSON model.

Normalization rules:
- Cardinality: SHACL default {0,*} → explicit min=0, max=-1
- rdf:type + sh:hasValue when targetClass present → skip (absorbed into targetClass)
- sh:class → classRef (single class IRI)
- sh:or class list → classRefOr (sorted list of class IRIs)
- sh:pattern matching URL prefix → iriStem
- Properties sorted by path IRI; shapes sorted by name
"""
from __future__ import annotations

import re
from typing import Optional, Union

from models.common import IRI, UNBOUNDED, IriStem, Literal, NodeKind
from models.shacl_model import NodeShape, PropertyShape, SHACLSchema
from models.json_model import (
    CanonicalCardinality,
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _shape_name_from_iri(iri: IRI) -> str:
    """Extract short name from SHACL shape IRI, removing 'Shape' suffix."""
    value = iri.value
    if value.endswith("Shape"):
        name = value.rsplit("/", 1)[-1]
        return name[:-5]
    return value.rsplit("/", 1)[-1]


def _pattern_to_iri_stem(pattern: str) -> Optional[str]:
    """Convert sh:pattern to an IRI stem string if it matches a URL prefix."""
    m = re.match(r'^\^(https?://[^$]*?)/?$', pattern)
    if m:
        return m.group(1)
    return None


def _value_to_canonical(val: Union[IRI, Literal]) -> Union[str, dict]:
    """Convert an IRI or Literal to a canonical JSON-serialisable value."""
    if isinstance(val, IRI):
        return val.value
    if isinstance(val, Literal):
        d: dict = {"value": val.value}
        if val.datatype:
            d["datatype"] = val.datatype.value
        if val.language:
            d["language"] = val.language
        return d
    return str(val)


def _convert_property(ps: PropertyShape) -> Optional[CanonicalProperty]:
    """Convert a SHACL PropertyShape to a CanonicalProperty."""
    path = ps.path.iri.value

    # Cardinality: SHACL default is {0,*}
    mn = ps.min_count if ps.min_count is not None else 0
    mx = ps.max_count if ps.max_count is not None else UNBOUNDED
    cardinality = CanonicalCardinality(min=mn, max=mx)

    prop = CanonicalProperty(path=path, cardinality=cardinality)

    # Constraint mapping (mutually exclusive, first match wins)
    if ps.has_value is not None:
        prop.hasValue = _value_to_canonical(ps.has_value)
    elif ps.in_values is not None:
        prop.inValues = [_value_to_canonical(v) for v in ps.in_values]
    elif ps.or_constraints:
        prop.classRefOr = sorted([c.value for c in ps.or_constraints])
    elif ps.class_:
        prop.classRef = ps.class_.value
    elif ps.node_kind:
        prop.nodeKind = ps.node_kind.value
    elif ps.datatype:
        prop.datatype = ps.datatype.value
    elif ps.pattern:
        stem = _pattern_to_iri_stem(ps.pattern)
        if stem:
            prop.iriStem = stem
        else:
            prop.pattern = ps.pattern
    elif ps.node:
        prop.nodeRef = ps.node.value

    return prop


def convert_shacl_to_json(shacl: SHACLSchema) -> CanonicalSchema:
    """Convert a SHACL schema to a canonical JSON schema.

    Args:
        shacl: The SHACL schema to convert.

    Returns:
        Canonical JSON schema with normalised shapes.
    """
    canonical_shapes: list[CanonicalShape] = []

    for node_shape in shacl.shapes:
        shape_name = _shape_name_from_iri(node_shape.iri)

        target_class = (
            node_shape.target_class.value if node_shape.target_class else None
        )

        properties: list[CanonicalProperty] = []
        for ps in node_shape.properties:
            # Skip rdf:type + hasValue when targetClass is present
            if (ps.path.iri.value == RDF_TYPE
                    and target_class is not None
                    and ps.has_value is not None):
                continue

            prop = _convert_property(ps)
            if prop is not None:
                properties.append(prop)

        canonical_shapes.append(CanonicalShape(
            name=shape_name,
            targetClass=target_class,
            closed=node_shape.closed,
            properties=properties,
        ))

    return CanonicalSchema(shapes=canonical_shapes)
