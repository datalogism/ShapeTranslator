"""Convert SHACL model to ShEx model.

Mapping rules based on the Validating RDF Book Ch. 13 and weso/shaclex.

Pass ``label_map`` (a ``dict[str, str]`` mapping Wikidata IRIs to English
labels) to ``convert_shacl_to_shex`` to enable label-based auxiliary shape
naming.  Shape references will use human-readable labels such as
``@<Human>`` instead of ``@<Q5>``.  Build the map with
:func:`shaclex_py.utils.wikidata.fetch_labels`.
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
    NodeConstraintShape,
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


def _class_to_shape_name(
    class_iri: IRI,
    label_map: Optional[dict[str, str]] = None,
) -> str:
    """Convert a class IRI to a shape name.

    When *label_map* is provided and the IRI is a known Wikidata entity, the
    English label is used (CamelCased).  Falls back to the IRI local name.

    Examples::

        _class_to_shape_name(IRI("http://schema.org/Person"))    → "Person"
        _class_to_shape_name(IRI("http://wikidata.org/entity/Q5"),
                              {"http://wikidata.org/entity/Q5": "human"})
                                                                  → "Human"
    """
    if label_map:
        label = label_map.get(class_iri.value)
        if label:
            from shaclex_py.utils.wikidata import to_shape_name
            return to_shape_name(label)
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
    label_map: Optional[dict[str, str]] = None,
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

    # sh:class with sh:or → auxiliary shape with value set for rdf:type.
    # For Wikidata: use the property label as the shape name (multiple classes
    # mean no single class label applies).
    elif ps.or_constraints:
        shape_name = _make_or_shape_name(ps, auxiliary_shapes, label_map)
        _create_auxiliary_or_shape(shape_name, ps.or_constraints, auxiliary_shapes)
        constraint = ShapeRef(name=IRI(shape_name))

    # sh:class → shape reference.
    # For Wikidata: prefer the class label (single type → share the shape,
    # e.g. P488/P112/P3975 all → @<Human>).  Fall back to property label, then
    # IRI local name.
    elif ps.class_:
        shape_name = _resolve_class_shape_name(
            ps.class_, ps.path.iri, auxiliary_shapes, label_map
        )
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


def _resolve_class_shape_name(
    class_iri: IRI,
    prop_iri: IRI,
    existing: dict[str, Shape],
    label_map: Optional[dict[str, str]] = None,
) -> str:
    """Choose the best auxiliary shape name for a single-class reference.

    Priority:
    1. Class label from *label_map* (e.g. Q5 → "Human")  — preferred because
       multiple properties pointing to the same type share one shape.
    2. Property label from *label_map* (e.g. P159 → "HeadquartersLocation").
    3. IRI local name (e.g. "Person", "Q5").

    Uniqueness: if the chosen name is already in *existing* pointing to a
    *different* class, append a numeric suffix.
    """
    if label_map:
        from shaclex_py.utils.wikidata import to_shape_name
        class_label = label_map.get(class_iri.value)
        if class_label:
            return _ensure_unique(to_shape_name(class_label), class_iri, existing)
        prop_label = label_map.get(prop_iri.value)
        if prop_label:
            return _ensure_unique(to_shape_name(prop_label), class_iri, existing)
    local = class_iri.value.rsplit("/", 1)[-1]
    return _ensure_unique(local, class_iri, existing)


def _ensure_unique(
    name: str, class_iri: IRI, existing: dict[str, Shape]
) -> str:
    """Return *name* or a suffixed variant that is not already taken by a
    different class in *existing*."""
    if name not in existing:
        return name
    # If the existing shape with this name already represents the same class,
    # reuse it (this is exactly the sharing we want for e.g. @<Human>).
    from shaclex_py.schema.shex import TripleConstraint, NodeConstraint
    from shaclex_py.schema.common import IRI as _IRI
    shape = existing[name]
    if shape.expression is not None:
        tc = shape.expression
        if isinstance(tc, TripleConstraint):
            nc = tc.constraint
            if (isinstance(nc, NodeConstraint) and nc.values
                    and len(nc.values) == 1
                    and isinstance(nc.values[0].value, _IRI)
                    and nc.values[0].value.value == class_iri.value):
                return name  # same class → reuse
    # Different class, need a fresh name
    i = 2
    while f"{name}{i}" in existing:
        i += 1
    return f"{name}{i}"


def _make_or_shape_name(
    ps: PropertyShape,
    existing: dict[str, Shape],
    label_map: Optional[dict[str, str]] = None,
) -> str:
    """Generate a shape name for an sh:or (multi-class) constraint.

    Uses the property label when *label_map* is available; falls back to
    the property IRI local name.
    """
    if label_map:
        prop_label = label_map.get(ps.path.iri.value)
        if prop_label:
            from shaclex_py.utils.wikidata import to_shape_name
            name = to_shape_name(prop_label)
            if name not in existing:
                return name
            i = 2
            while f"{name}{i}" in existing:
                i += 1
            return f"{name}{i}"
    # Fallback: property IRI local name, CamelCased
    path_local = ps.path.iri.value.rsplit("/", 1)[-1]
    name = path_local[0].upper() + path_local[1:] if path_local else "OrShape"
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


def _collect_used_iris(shapes: list) -> set[str]:
    """Collect all IRIs used in shapes for prefix filtering."""
    iris: set[str] = set()
    for shape in shapes:
        iris.add(shape.name.value)
        if isinstance(shape, NodeConstraintShape):
            for dt in shape.datatypes:
                iris.add(dt.value)
            continue
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


def convert_shacl_to_shex(
    shacl: SHACLSchema,
    label_map: Optional[dict[str, str]] = None,
) -> ShExSchema:
    """Convert a SHACL schema to a ShEx schema.

    Args:
        shacl:      The SHACL schema to convert.
        label_map:  Optional mapping of Wikidata IRI → English label.  When
                    provided, auxiliary shape names are derived from labels
                    (e.g. ``@<Human>`` instead of ``@<Q5>``).  Build with
                    :func:`shaclex_py.utils.wikidata.fetch_labels`.

    Returns:
        Equivalent ShEx schema.
    """
    shapes: list = []
    auxiliary_shapes: dict[str, Shape] = {}
    start: Optional[IRI] = None

    for node_shape in shacl.shapes:
        shape_name = _shape_name_from_iri(node_shape.iri)

        # Named value shape: sh:or ([sh:datatype D1] [sh:datatype D2] ...) at NodeShape level.
        # Emit as NodeConstraintShape (ShExC: <Name> D1 OR D2 OR ...).
        if node_shape.or_datatypes:
            nc_shape = NodeConstraintShape(
                name=IRI(shape_name),
                datatypes=list(node_shape.or_datatypes),
            )
            shapes.append(nc_shape)
            # Don't set start for pure NodeConstraintShapes — they are auxiliary
            continue

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
        for ps in node_shape.properties:
            # Skip rdf:type property if we already added targetClass as rdf:type
            if (ps.path.iri == RDF_TYPE and node_shape.target_class and
                    ps.has_value is not None):
                continue

            tc = _convert_property_to_triple_constraint(ps, auxiliary_shapes, label_map)
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

    # Add auxiliary shapes (sorted by name for consistent output_old)
    main_names = {s.name.value for s in shapes}
    for name in sorted(auxiliary_shapes):
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
