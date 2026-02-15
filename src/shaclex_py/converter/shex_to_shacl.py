"""Convert ShEx model to SHACL model.

Mapping rules based on the Validating RDF Book Ch. 13 and weso/shaclex.
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
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.shex import (
    EachOf,
    NodeConstraint,
    OneOf,
    Shape,
    ShapeRef,
    ShExSchema,
    TripleConstraint,
    ValueSetValue,
)

RDF_TYPE = IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
WDT_P31 = IRI("http://www.wikidata.org/prop/direct/P31")  # Wikidata instance-of
INSTANCE_OF_PREDICATES = {RDF_TYPE, WDT_P31}
SHACL_SHAPES_BASE = "http://shaclshapes.org/"

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


def _make_shape_iri(name: str) -> IRI:
    """Make a SHACL shape IRI from a ShEx shape name."""
    return IRI(f"{SHACL_SHAPES_BASE}{name}Shape")


def _get_triple_constraints(shape: Shape) -> list[TripleConstraint]:
    """Extract triple constraints from a shape expression."""
    if shape.expression is None:
        return []
    if isinstance(shape.expression, TripleConstraint):
        return [shape.expression]
    if isinstance(shape.expression, EachOf):
        tcs = []
        for expr in shape.expression.expressions:
            if isinstance(expr, TripleConstraint):
                tcs.append(expr)
        return tcs
    return []


def _is_instance_of_predicate(predicate: IRI) -> bool:
    """Check if a predicate is an instance-of predicate (rdf:type or wdt:P31)."""
    return predicate in INSTANCE_OF_PREDICATES


def _extract_target_class(tcs: list[TripleConstraint]) -> Optional[IRI]:
    """Check if any triple constraint is an instance-of with a value set -> target class."""
    for tc in tcs:
        if _is_instance_of_predicate(tc.predicate) and isinstance(tc.constraint, NodeConstraint):
            if tc.constraint.values and len(tc.constraint.values) == 1:
                val = tc.constraint.values[0].value
                if isinstance(val, IRI):
                    return val
    return None


def _is_instance_of_with_single_class(tc: TripleConstraint) -> bool:
    """Check if this is an instance-of [ClassName] constraint (rdf:type or wdt:P31)."""
    if not _is_instance_of_predicate(tc.predicate):
        return False
    if not isinstance(tc.constraint, NodeConstraint):
        return False
    if not tc.constraint.values:
        return False
    if len(tc.constraint.values) != 1:
        return False
    return isinstance(tc.constraint.values[0].value, IRI)


def _is_instance_of_with_multi_class(tc: TripleConstraint) -> bool:
    """Check if this is an instance-of [Class1 Class2 ...] constraint."""
    if not _is_instance_of_predicate(tc.predicate):
        return False
    if not isinstance(tc.constraint, NodeConstraint):
        return False
    if not tc.constraint.values:
        return False
    return len(tc.constraint.values) > 1


def _convert_cardinality_to_shacl(
    card: Cardinality,
) -> tuple[Optional[int], Optional[int]]:
    """Convert ShEx cardinality to SHACL min/maxCount.

    ShEx default is {1,1}. Only emit min/maxCount when they differ
    from SHACL default {0,*}.
    """
    mn = card.effective_min  # resolved to int
    mx = card.effective_max  # None = unbounded, int otherwise

    min_count = mn if mn > 0 else None
    max_count = mx if mx is not None else None  # None = unbounded → no maxCount

    return min_count, max_count


def _value_set_to_iri_stem_pattern(values: list[ValueSetValue]) -> Optional[str]:
    """Convert a value set with an IRI stem to a SHACL pattern."""
    if len(values) == 1 and isinstance(values[0].value, IriStem):
        stem = values[0].value.stem
        return f"^{stem}/"
    return None


def _convert_triple_constraint_to_property(
    tc: TripleConstraint,
    schema: ShExSchema,
) -> PropertyShape:
    """Convert a ShEx TripleConstraint to a SHACL PropertyShape."""
    from shaclex_py.schema.common import Path

    path = Path(iri=tc.predicate)
    min_count, max_count = _convert_cardinality_to_shacl(tc.cardinality)

    datatype = None
    class_ = None
    node_kind = None
    pattern = None
    has_value = None
    in_values = None
    node = None
    or_constraints = None

    if isinstance(tc.constraint, ShapeRef):
        # Shape reference → check if the referenced shape is a simple class shape
        ref_name = tc.constraint.name.value
        ref_shape = _find_shape(schema, ref_name)

        if ref_shape:
            ref_tcs = _get_triple_constraints(ref_shape)
            # If it's a single-constraint shape with a value set of one class,
            # inline as sh:class (covers rdf:type, wdt:P31, wdt:P279, etc.)
            if (len(ref_tcs) == 1
                    and isinstance(ref_tcs[0].constraint, NodeConstraint)
                    and ref_tcs[0].constraint.values
                    and len(ref_tcs[0].constraint.values) == 1
                    and isinstance(ref_tcs[0].constraint.values[0].value, IRI)):
                class_ = ref_tcs[0].constraint.values[0].value
            # If it's a single-constraint shape with multiple classes in value set
            elif (len(ref_tcs) == 1
                    and isinstance(ref_tcs[0].constraint, NodeConstraint)
                    and ref_tcs[0].constraint.values
                    and len(ref_tcs[0].constraint.values) > 1):
                class_iris = [
                    v.value for v in ref_tcs[0].constraint.values
                    if isinstance(v.value, IRI)
                ]
                if class_iris:
                    or_constraints = class_iris
                else:
                    node = _make_shape_iri(ref_name)
            else:
                # Complex shape → sh:class with the extracted target, or sh:node
                class_ = _extract_target_class(ref_tcs)
                if class_ is None:
                    node = _make_shape_iri(ref_name)
        else:
            class_ = IRI(ref_name)

    elif isinstance(tc.constraint, NodeConstraint):
        nc = tc.constraint

        if nc.datatype:
            datatype = nc.datatype

        elif nc.node_kind:
            node_kind = nc.node_kind

        elif nc.values:
            # Check for IRI stem → pattern
            stem_pattern = _value_set_to_iri_stem_pattern(nc.values)
            if stem_pattern:
                pattern = stem_pattern
            else:
                # Value set → sh:in or sh:hasValue
                iri_values = [v.value for v in nc.values if isinstance(v.value, (IRI, Literal))]
                if len(iri_values) == 1:
                    has_value = iri_values[0]
                elif len(iri_values) > 1:
                    in_values = iri_values

    return PropertyShape(
        path=path,
        datatype=datatype,
        class_=class_,
        node_kind=node_kind,
        min_count=min_count,
        max_count=max_count,
        pattern=pattern,
        has_value=has_value,
        in_values=in_values,
        node=node,
        or_constraints=or_constraints,
    )


def _find_shape(schema: ShExSchema, name: str) -> Optional[Shape]:
    """Find a shape by name in the schema."""
    for shape in schema.shapes:
        if shape.name.value == name:
            return shape
    return None


def _is_auxiliary_shape(shape: Shape, main_shape_names: set[str]) -> bool:
    """Determine if a shape is auxiliary (referenced by main shapes)."""
    return shape.name.value not in main_shape_names


def convert_shex_to_shacl(shex: ShExSchema) -> SHACLSchema:
    """Convert a ShEx schema to a SHACL schema.

    Args:
        shex: The ShEx schema to convert.

    Returns:
        Equivalent SHACL schema.
    """
    shapes: list[NodeShape] = []

    # Identify the "main" shape (start shape or first shape with many constraints)
    main_shape_names: set[str] = set()
    if shex.start:
        main_shape_names.add(shex.start.value)
    else:
        # Use shapes with more than one triple constraint as main shapes
        for shape in shex.shapes:
            tcs = _get_triple_constraints(shape)
            if len(tcs) > 1:
                main_shape_names.add(shape.name.value)

    # If no main shapes identified, treat first shape as main
    if not main_shape_names and shex.shapes:
        main_shape_names.add(shex.shapes[0].name.value)

    for shape in shex.shapes:
        # Skip auxiliary shapes (they get inlined as sh:class references)
        if shape.name.value not in main_shape_names:
            continue

        shape_iri = _make_shape_iri(shape.name.value)
        tcs = _get_triple_constraints(shape)

        # Extract target class from rdf:type constraint
        target_class = _extract_target_class(tcs)

        properties: list[PropertyShape] = []
        has_rdf_type_target = False

        for tc in tcs:
            # If this is the instance-of constraint that maps to targetClass,
            # skip it (it becomes sh:targetClass on the NodeShape)
            if _is_instance_of_with_single_class(tc) and target_class:
                has_rdf_type_target = True
                continue

            ps = _convert_triple_constraint_to_property(tc, shex)
            properties.append(ps)

        node_shape = NodeShape(
            iri=shape_iri,
            target_class=target_class,
            properties=properties,
        )
        shapes.append(node_shape)

    # Build prefixes — use standard SHACL prefixes plus any from the source
    prefixes = list(STANDARD_SHACL_PREFIXES)
    standard_iris = {p.iri for p in STANDARD_SHACL_PREFIXES}
    for pfx in shex.prefixes:
        if pfx.iri not in standard_iris and pfx.name not in ('sh',):
            prefixes.append(pfx)

    return SHACLSchema(shapes=shapes, prefixes=prefixes)
