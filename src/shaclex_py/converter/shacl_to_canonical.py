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

from shaclex_py.schema.common import IRI, UNBOUNDED, IriStem, Literal, NodeKind
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.canonical import (
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

    # Primary constraint (mutually exclusive, first match wins; nodeKind is handled separately)
    if ps.has_value is not None:
        prop.hasValue = _value_to_canonical(ps.has_value)
    elif ps.in_values is not None:
        prop.inValues = [_value_to_canonical(v) for v in ps.in_values]
    elif ps.or_constraints:
        prop.classRefOr = sorted([c.value for c in ps.or_constraints])
    elif ps.class_:
        prop.classRef = ps.class_.value
    elif ps.datatype:
        prop.datatype = ps.datatype.value
    elif ps.pattern:
        stem = _pattern_to_iri_stem(ps.pattern)
        if stem:
            prop.iriStem = stem
        else:
            prop.pattern = ps.pattern
    elif ps.node:
        # Normalise using the same logic as shape names so that nodeRef IDs
        # are consistent with the canonical shape names they point to.
        prop.nodeRef = _shape_name_from_iri(ps.node)

    # nodeKind is captured independently — it can accompany datatype, classRef, etc.
    # (e.g. DBpedia: sh:datatype xsd:string ; sh:nodeKind sh:Literal — both must round-trip)
    if ps.node_kind is not None:
        prop.nodeKind = ps.node_kind.value

    # Secondary: sh:pattern can accompany a primary type constraint (e.g. sh:datatype + sh:pattern)
    if ps.pattern is not None and prop.pattern is None and prop.iriStem is None:
        prop.pattern = ps.pattern

    # sh:alternativePath: store full list of alternative paths
    if ps.alternative_paths:
        prop.pathAlternatives = [p.value for p in ps.alternative_paths]

    return prop


def convert_shacl_to_canonical(shacl: SHACLSchema) -> CanonicalSchema:
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

        datatype_or = (
            [d.value for d in node_shape.or_datatypes]
            if node_shape.or_datatypes else None
        )

        shape_node_kind = node_shape.node_kind.value if node_shape.node_kind else None
        shape_datatype = node_shape.node_datatype.value if node_shape.node_datatype else None
        shape_in_values = (
            [_value_to_canonical(v) for v in node_shape.node_in_values]
            if node_shape.node_in_values else None
        )

        property_alternative_groups = None
        if node_shape.or_property_groups:
            # All branches of the sh:or together form one alternative group.
            # Each branch contributes its predicate(s) to a single flat list,
            # because the alternatives are mutually exclusive across ALL branches.
            all_preds = [
                ps.path.iri.value
                for group in node_shape.or_property_groups
                for ps in group
            ]
            if all_preds:
                property_alternative_groups = [all_preds]

        canonical_shapes.append(CanonicalShape(
            name=shape_name,
            targetClass=target_class,
            closed=node_shape.closed,
            properties=properties,
            datatypeOr=datatype_or,
            nodeKind=shape_node_kind,
            datatype=shape_datatype,
            inValues=shape_in_values,
            property_alternative_groups=property_alternative_groups,
        ))

    return CanonicalSchema(shapes=canonical_shapes)
