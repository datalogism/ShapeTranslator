"""Convert SHACL model to ShEx model.

Mapping rules based on the Validating RDF Book Ch. 13 and weso/shaclex.
"""
from __future__ import annotations

import re
from typing import Optional, Union

from shaclex_py.schema.common import (
    IRI,
    UNBOUNDED,
    Cardinality,
    IriStem,
    Literal,
    NodeKind,
    Prefix,
)
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.shex import (
    EachOf,
    NodeConstraint,
    Shape,
    ShapeRef,
    ShExSchema,
    TripleConstraint,
    ValueSetValue,
)

RDF_TYPE = IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

# Standard prefixes used in YAGO ShEx files
STANDARD_SHEX_PREFIXES = [
    Prefix("geo", "http://www.opengis.net/ont/geosparql#"),
    Prefix("owl", "http://www.w3.org/2002/07/owl#"),
    Prefix("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    Prefix("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    Prefix("schema", "http://schema.org/"),
    Prefix("skos", "http://www.w3.org/2004/02/skos/core#"),
    Prefix("wd", "http://www.wikidata.org/entity/"),
    Prefix("wdt", "http://www.wikidata.org/prop/direct/"),
    Prefix("xsd", "http://www.w3.org/2001/XMLSchema#"),
    Prefix("yago", "http://yago-knowledge.org/resource/"),
]


def _shape_name_from_iri(iri: IRI) -> str:
    """Extract a short shape name from a SHACL shape IRI.

    E.g., 'http://shaclshapes.org/LanguageShape' → 'Language'
    """
    value = iri.value
    # Common pattern: .../<Name>Shape
    if value.endswith("Shape"):
        name = value.rsplit("/", 1)[-1]
        return name[:-5]  # Remove 'Shape' suffix
    return value.rsplit("/", 1)[-1]


def _class_to_shape_name(class_iri: IRI) -> str:
    """Convert a class IRI to a shape name.

    E.g., 'http://schema.org/Person' → 'Person'
         'http://yago-knowledge.org/resource/Award' → 'Award'
    """
    return class_iri.value.rsplit("/", 1)[-1]


def _convert_cardinality(ps: PropertyShape) -> Cardinality:
    """Convert SHACL cardinality to ShEx cardinality.

    SHACL default is {0,*}, ShEx default is {1,1}.
    We always emit explicit cardinality.
    """
    mn = ps.min_count if ps.min_count is not None else 0
    mx = ps.max_count if ps.max_count is not None else UNBOUNDED
    return Cardinality(min=mn, max=mx)


def _pattern_to_iri_stem(pattern: str) -> Optional[IriStem]:
    """Convert a SHACL sh:pattern to a ShEx IRI stem if possible.

    E.g., '^http://www.wikidata.org/entity/' → IriStem('http://www.wikidata.org/entity')
    """
    # Match patterns like '^http://..../': remove ^ prefix and trailing /
    m = re.match(r'^\^(https?://[^$]*?)/?$', pattern)
    if m:
        return IriStem(stem=m.group(1))
    return None


def _convert_property_to_triple_constraint(
    ps: PropertyShape,
    auxiliary_shapes: dict[str, Shape],
) -> TripleConstraint:
    """Convert a SHACL PropertyShape to a ShEx TripleConstraint."""
    predicate = ps.path.iri
    card = _convert_cardinality(ps)

    constraint: Optional[Union[NodeConstraint, ShapeRef]] = None

    # sh:hasValue → value set with one element
    if ps.has_value is not None:
        if isinstance(ps.has_value, IRI):
            constraint = NodeConstraint(
                values=[ValueSetValue(value=ps.has_value)]
            )
        elif isinstance(ps.has_value, Literal):
            constraint = NodeConstraint(
                values=[ValueSetValue(value=ps.has_value)]
            )

    # sh:in → value set
    elif ps.in_values is not None:
        values = []
        for v in ps.in_values:
            values.append(ValueSetValue(value=v))
        constraint = NodeConstraint(values=values)

    # sh:class with sh:or → auxiliary shape with value set for rdf:type
    elif ps.or_constraints:
        shape_name = _make_or_shape_name(ps, auxiliary_shapes)
        _create_auxiliary_or_shape(shape_name, ps.or_constraints, auxiliary_shapes)
        constraint = ShapeRef(name=IRI(shape_name))

    # sh:class → shape reference
    elif ps.class_:
        shape_name = _class_to_shape_name(ps.class_)
        _ensure_auxiliary_class_shape(shape_name, ps.class_, auxiliary_shapes)
        constraint = ShapeRef(name=IRI(shape_name))

    # sh:nodeKind
    elif ps.node_kind:
        constraint = NodeConstraint(node_kind=ps.node_kind)

    # sh:datatype
    elif ps.datatype:
        constraint = NodeConstraint(datatype=ps.datatype)

    # sh:pattern → try IRI stem
    elif ps.pattern:
        stem = _pattern_to_iri_stem(ps.pattern)
        if stem:
            constraint = NodeConstraint(
                values=[ValueSetValue(value=stem)]
            )

    # sh:node → shape reference
    elif ps.node:
        constraint = ShapeRef(name=ps.node)

    # If pattern is set alongside other constraints, handle it
    if ps.pattern and constraint is None:
        stem = _pattern_to_iri_stem(ps.pattern)
        if stem:
            constraint = NodeConstraint(
                values=[ValueSetValue(value=stem)]
            )

    return TripleConstraint(
        predicate=predicate,
        constraint=constraint,
        cardinality=card,
    )


def _make_or_shape_name(
    ps: PropertyShape, existing: dict[str, Shape]
) -> str:
    """Generate a shape name for an sh:or constraint."""
    # Use the property local name as the shape name
    path_local = ps.path.iri.value.rsplit("/", 1)[-1]
    # Capitalize first letter
    name = path_local[0].upper() + path_local[1:] if path_local else "OrShape"
    # Ensure uniqueness
    if name in existing:
        i = 2
        while f"{name}{i}" in existing:
            i += 1
        name = f"{name}{i}"
    return name


def _create_auxiliary_or_shape(
    name: str, class_iris: list[IRI], auxiliary_shapes: dict[str, Shape]
):
    """Create an auxiliary shape for sh:or class constraints.

    E.g., sh:class [ sh:or ( schema:Organization schema:Person ) ]
    becomes:
        <Organizer> EXTRA rdf:type { rdf:type [ schema:Organization schema:Person ] }
    """
    if name in auxiliary_shapes:
        return

    values = [ValueSetValue(value=c) for c in class_iris]
    tc = TripleConstraint(
        predicate=RDF_TYPE,
        constraint=NodeConstraint(values=values),
        cardinality=Cardinality(),  # default {1,1}
    )
    auxiliary_shapes[name] = Shape(
        name=IRI(name),
        expression=tc,
        extra=[RDF_TYPE],
    )


def _ensure_auxiliary_class_shape(
    name: str, class_iri: IRI, auxiliary_shapes: dict[str, Shape]
):
    """Ensure an auxiliary shape exists for a class reference.

    E.g., sh:class schema:Place → <Place> EXTRA rdf:type { rdf:type [ schema:Place ] }
    """
    if name in auxiliary_shapes:
        return

    tc = TripleConstraint(
        predicate=RDF_TYPE,
        constraint=NodeConstraint(
            values=[ValueSetValue(value=class_iri)]
        ),
        cardinality=Cardinality(),  # default {1,1}
    )
    auxiliary_shapes[name] = Shape(
        name=IRI(name),
        expression=tc,
        extra=[RDF_TYPE],
    )


def _collect_used_iris(shapes: list[Shape]) -> set[str]:
    """Collect all IRIs used in shapes for prefix filtering."""
    iris: set[str] = set()
    for shape in shapes:
        iris.add(shape.name.value)
        for e in shape.extra:
            iris.add(e.value)
        if shape.expression is None:
            continue
        tcs = []
        if isinstance(shape.expression, EachOf):
            tcs = shape.expression.expressions
        elif isinstance(shape.expression, TripleConstraint):
            tcs = [shape.expression]
        for tc in tcs:
            if not isinstance(tc, TripleConstraint):
                continue
            iris.add(tc.predicate.value)
            if isinstance(tc.constraint, NodeConstraint):
                if tc.constraint.datatype:
                    iris.add(tc.constraint.datatype.value)
                if tc.constraint.values:
                    for v in tc.constraint.values:
                        if isinstance(v.value, IRI):
                            iris.add(v.value.value)
            elif isinstance(tc.constraint, ShapeRef):
                iris.add(tc.constraint.name.value)
    return iris


def convert_shacl_to_shex(shacl: SHACLSchema) -> ShExSchema:
    """Convert a SHACL schema to a ShEx schema.

    Args:
        shacl: The SHACL schema to convert.

    Returns:
        Equivalent ShEx schema.
    """
    shapes: list[Shape] = []
    auxiliary_shapes: dict[str, Shape] = {}
    start: Optional[IRI] = None

    for node_shape in shacl.shapes:
        shape_name = _shape_name_from_iri(node_shape.iri)

        triple_constraints: list[TripleConstraint] = []

        # sh:targetClass → rdf:type [TargetClass] as first triple constraint
        if node_shape.target_class:
            tc_type = TripleConstraint(
                predicate=RDF_TYPE,
                constraint=NodeConstraint(
                    values=[ValueSetValue(value=node_shape.target_class)]
                ),
                cardinality=Cardinality(),  # default {1,1}
            )
            triple_constraints.append(tc_type)

        # Convert each property shape
        has_rdf_type_prop = False
        for ps in node_shape.properties:
            # Skip rdf:type property if we already added targetClass as rdf:type
            if (ps.path.iri == RDF_TYPE and node_shape.target_class and
                    ps.has_value is not None):
                has_rdf_type_prop = True
                continue

            tc = _convert_property_to_triple_constraint(ps, auxiliary_shapes)
            triple_constraints.append(tc)

        # Build expression
        expr = None
        if len(triple_constraints) == 1:
            expr = triple_constraints[0]
        elif len(triple_constraints) > 1:
            expr = EachOf(expressions=triple_constraints)

        # EXTRA rdf:type — add when shape has rdf:type constraint
        extra = [RDF_TYPE]

        # CLOSED handling
        closed = node_shape.closed

        shape = Shape(
            name=IRI(shape_name),
            expression=expr,
            closed=closed,
            extra=extra,
        )
        shapes.append(shape)

        # First shape is the start shape
        if start is None:
            start = IRI(shape_name)

    # Add auxiliary shapes (sorted by name for consistent output)
    for name in sorted(auxiliary_shapes):
        # Don't add auxiliary shape if it has the same name as a main shape
        main_names = {s.name.value for s in shapes}
        if name not in main_names:
            shapes.append(auxiliary_shapes[name])

    # Use standard ShEx prefixes only — rdflib adds many built-in prefixes
    # that aren't relevant. We start with the standard set and only add
    # prefixes from the SHACL source that we know are actually used.
    prefixes = list(STANDARD_SHEX_PREFIXES)
    standard_iris = {p.iri for p in STANDARD_SHEX_PREFIXES}
    # Collect all IRIs used in the converted shapes to find needed prefixes
    used_iris = _collect_used_iris(shapes)
    for pfx in shacl.prefixes:
        if (pfx.name and pfx.iri not in standard_iris and pfx.name != 'sh'
                and any(iri.startswith(pfx.iri) for iri in used_iris)):
            prefixes.append(pfx)

    return ShExSchema(shapes=shapes, prefixes=prefixes, start=start)
