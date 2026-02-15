"""Convert canonical JSON model to ShEx model.

Reverse mapping of shex_to_canonical:
- targetClass → rdf:type [targetClass] triple constraint
- classRef → auxiliary shape with rdf:type [class], referenced via @<ShapeName>
- classRefOr → auxiliary shape with rdf:type [class1 class2 ...], via @<ShapeName>
- iriStem → value set with IriStem
- cardinality min/max → ShEx cardinality
"""
from __future__ import annotations

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
from shaclex_py.schema.shex import (
    EachOf,
    NodeConstraint,
    Shape,
    ShapeRef,
    ShExSchema,
    TripleConstraint,
    ValueSetValue,
)
from shaclex_py.schema.canonical import (
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)

RDF_TYPE = IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

NODE_KIND_MAP = {
    "IRI": NodeKind.IRI,
    "BlankNode": NodeKind.BLANK_NODE,
    "Literal": NodeKind.LITERAL,
    "BlankNodeOrIRI": NodeKind.BLANK_NODE_OR_IRI,
    "BlankNodeOrLiteral": NodeKind.BLANK_NODE_OR_LITERAL,
    "IRIOrLiteral": NodeKind.IRI_OR_LITERAL,
}

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


def _canonical_value_to_model(val: Union[str, dict]) -> Union[IRI, Literal]:
    """Convert a canonical JSON value back to IRI or Literal."""
    if isinstance(val, str):
        return IRI(val)
    if isinstance(val, dict):
        dt = IRI(val["datatype"]) if "datatype" in val else None
        lang = val.get("language")
        return Literal(value=val["value"], datatype=dt, language=lang)
    return IRI(str(val))


def _class_to_shape_name(class_iri: str) -> str:
    """Extract local name from a class IRI for use as a shape name."""
    return class_iri.rsplit("/", 1)[-1]


def _convert_cardinality(cprop: CanonicalProperty) -> Cardinality:
    """Convert canonical cardinality to ShEx Cardinality."""
    mn = cprop.cardinality.min
    mx = cprop.cardinality.max  # -1 = UNBOUNDED
    return Cardinality(min=mn, max=mx)


def _unique_aux_name(
    base: str,
    auxiliary_shapes: dict[str, Shape],
    main_shape_names: set[str],
) -> str:
    """Generate a unique auxiliary shape name that doesn't clash with main or existing aux shapes."""
    if base not in main_shape_names and base not in auxiliary_shapes:
        return base
    # Append suffix to avoid collision
    candidate = f"{base}_class"
    if candidate not in main_shape_names and candidate not in auxiliary_shapes:
        return candidate
    i = 2
    while True:
        candidate = f"{base}_class{i}"
        if candidate not in main_shape_names and candidate not in auxiliary_shapes:
            return candidate
        i += 1


def _convert_property(
    cprop: CanonicalProperty,
    auxiliary_shapes: dict[str, Shape],
    main_shape_names: set[str],
) -> TripleConstraint:
    """Convert a CanonicalProperty to a ShEx TripleConstraint."""
    predicate = IRI(cprop.path)
    card = _convert_cardinality(cprop)

    constraint: Optional[Union[NodeConstraint, ShapeRef]] = None

    if cprop.datatype is not None:
        constraint = NodeConstraint(datatype=IRI(cprop.datatype))

    elif cprop.classRef is not None:
        base_name = _class_to_shape_name(cprop.classRef)
        shape_name = _unique_aux_name(base_name, auxiliary_shapes, main_shape_names)
        _ensure_auxiliary_class_shape(shape_name, IRI(cprop.classRef), auxiliary_shapes)
        constraint = ShapeRef(name=IRI(shape_name))

    elif cprop.classRefOr is not None:
        # Generate auxiliary shape name from property local name
        path_local = cprop.path.rsplit("/", 1)[-1]
        base_name = path_local[0].upper() + path_local[1:] if path_local else "OrShape"
        shape_name = _unique_aux_name(base_name, auxiliary_shapes, main_shape_names)
        class_iris = [IRI(c) for c in cprop.classRefOr]
        _create_auxiliary_or_shape(shape_name, class_iris, auxiliary_shapes)
        constraint = ShapeRef(name=IRI(shape_name))

    elif cprop.nodeKind is not None:
        nk = NODE_KIND_MAP.get(cprop.nodeKind)
        if nk:
            constraint = NodeConstraint(node_kind=nk)

    elif cprop.hasValue is not None:
        val = _canonical_value_to_model(cprop.hasValue)
        constraint = NodeConstraint(values=[ValueSetValue(value=val)])

    elif cprop.inValues is not None:
        vals = [ValueSetValue(value=_canonical_value_to_model(v)) for v in cprop.inValues]
        constraint = NodeConstraint(values=vals)

    elif cprop.iriStem is not None:
        constraint = NodeConstraint(
            values=[ValueSetValue(value=IriStem(stem=cprop.iriStem))]
        )

    elif cprop.pattern is not None:
        constraint = NodeConstraint(pattern=cprop.pattern)

    elif cprop.nodeRef is not None:
        constraint = ShapeRef(name=IRI(cprop.nodeRef))

    return TripleConstraint(
        predicate=predicate,
        constraint=constraint,
        cardinality=card,
    )


def _create_auxiliary_or_shape(
    name: str, class_iris: list[IRI], auxiliary_shapes: dict[str, Shape],
):
    """Create an auxiliary shape for OR class constraints."""
    if name in auxiliary_shapes:
        return
    values = [ValueSetValue(value=c) for c in class_iris]
    tc = TripleConstraint(
        predicate=RDF_TYPE,
        constraint=NodeConstraint(values=values),
        cardinality=Cardinality(),
    )
    auxiliary_shapes[name] = Shape(
        name=IRI(name),
        expression=tc,
        extra=[RDF_TYPE],
    )


def _ensure_auxiliary_class_shape(
    name: str, class_iri: IRI, auxiliary_shapes: dict[str, Shape],
):
    """Ensure an auxiliary shape exists for a single class reference."""
    if name in auxiliary_shapes:
        return
    tc = TripleConstraint(
        predicate=RDF_TYPE,
        constraint=NodeConstraint(values=[ValueSetValue(value=class_iri)]),
        cardinality=Cardinality(),
    )
    auxiliary_shapes[name] = Shape(
        name=IRI(name),
        expression=tc,
        extra=[RDF_TYPE],
    )


def convert_canonical_to_shex(canonical: CanonicalSchema) -> ShExSchema:
    """Convert a canonical JSON schema to a ShEx schema.

    Args:
        canonical: The canonical schema to convert.

    Returns:
        Equivalent ShEx schema.
    """
    shapes: list[Shape] = []
    auxiliary_shapes: dict[str, Shape] = {}
    start: Optional[IRI] = None
    main_shape_names = {cs.name for cs in canonical.shapes}

    for cshape in canonical.shapes:
        shape_name = cshape.name

        triple_constraints: list[TripleConstraint] = []

        # targetClass → rdf:type [targetClass]
        if cshape.targetClass:
            tc_type = TripleConstraint(
                predicate=RDF_TYPE,
                constraint=NodeConstraint(
                    values=[ValueSetValue(value=IRI(cshape.targetClass))]
                ),
                cardinality=Cardinality(),
            )
            triple_constraints.append(tc_type)

        # Convert each property
        for cprop in cshape.properties:
            tc = _convert_property(cprop, auxiliary_shapes, main_shape_names)
            triple_constraints.append(tc)

        # Build expression
        expr = None
        if len(triple_constraints) == 1:
            expr = triple_constraints[0]
        elif len(triple_constraints) > 1:
            expr = EachOf(expressions=triple_constraints)

        extra = [RDF_TYPE]

        shape = Shape(
            name=IRI(shape_name),
            expression=expr,
            closed=cshape.closed,
            extra=extra,
        )
        shapes.append(shape)

        if start is None:
            start = IRI(shape_name)

    # Add auxiliary shapes
    main_names = {s.name.value for s in shapes}
    for name in sorted(auxiliary_shapes):
        if name not in main_names:
            shapes.append(auxiliary_shapes[name])

    return ShExSchema(shapes=shapes, prefixes=list(STANDARD_SHEX_PREFIXES), start=start)
