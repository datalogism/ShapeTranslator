"""Convert ShEx model to canonical JSON model.

Normalization rules:
- Cardinality: ShEx default {1,1} → explicit min/max ints
- rdf:type [Class] when it acts as targetClass → absorbed into targetClass field
- ShapeRef to auxiliary class shapes → resolved to classRef IRI (or classRefOr)
- IriStem → iriStem field
- Properties sorted by path IRI; shapes sorted by name
"""
from __future__ import annotations

from typing import Optional, Union

from models.common import IRI, UNBOUNDED, IriStem, Literal, NodeKind
from models.shex_model import (
    EachOf,
    NodeConstraint,
    OneOf,
    Shape,
    ShapeRef,
    ShExSchema,
    TripleConstraint,
    ValueSetValue,
)
from models.json_model import (
    CanonicalCardinality,
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
WDT_P31 = "http://www.wikidata.org/prop/direct/P31"
INSTANCE_OF_PREDICATES = {RDF_TYPE, WDT_P31}


def _get_triple_constraints(shape: Shape) -> list[TripleConstraint]:
    """Extract TripleConstraints from a shape expression."""
    if shape.expression is None:
        return []
    if isinstance(shape.expression, TripleConstraint):
        return [shape.expression]
    if isinstance(shape.expression, EachOf):
        return [
            e for e in shape.expression.expressions
            if isinstance(e, TripleConstraint)
        ]
    return []


def _find_shape(schema: ShExSchema, name: str) -> Optional[Shape]:
    """Find a shape by name in the schema."""
    for shape in schema.shapes:
        if shape.name.value == name:
            return shape
    return None


def _is_instance_of_predicate(pred: str) -> bool:
    return pred in INSTANCE_OF_PREDICATES


def _extract_target_class(tcs: list[TripleConstraint]) -> Optional[str]:
    """Extract target class from an instance-of triple constraint with a single value."""
    for tc in tcs:
        if not _is_instance_of_predicate(tc.predicate.value):
            continue
        if not isinstance(tc.constraint, NodeConstraint):
            continue
        if not tc.constraint.values or len(tc.constraint.values) != 1:
            continue
        val = tc.constraint.values[0].value
        if isinstance(val, IRI):
            return val.value
    return None


def _is_target_class_tc(tc: TripleConstraint, target_class: Optional[str]) -> bool:
    """Check if a triple constraint is the instance-of constraint that maps to targetClass."""
    if target_class is None:
        return False
    if not _is_instance_of_predicate(tc.predicate.value):
        return False
    if not isinstance(tc.constraint, NodeConstraint):
        return False
    if not tc.constraint.values or len(tc.constraint.values) != 1:
        return False
    val = tc.constraint.values[0].value
    return isinstance(val, IRI) and val.value == target_class


def _resolve_shape_ref(
    ref_name: str, schema: ShExSchema
) -> tuple[Optional[str], Optional[list[str]], bool]:
    """Resolve a ShapeRef to classRef, classRefOr, or indicate it's unresolvable.

    Returns:
        (classRef, classRefOr, resolved) — exactly one of classRef/classRefOr is set
        if resolved is True. If resolved is False, both are None.
    """
    ref_shape = _find_shape(schema, ref_name)
    if ref_shape is None:
        return None, None, False

    ref_tcs = _get_triple_constraints(ref_shape)
    if len(ref_tcs) != 1:
        return None, None, False

    tc = ref_tcs[0]
    if not isinstance(tc.constraint, NodeConstraint) or not tc.constraint.values:
        return None, None, False

    iris = [
        v.value.value for v in tc.constraint.values
        if isinstance(v.value, IRI)
    ]
    if not iris:
        return None, None, False

    if len(iris) == 1:
        return iris[0], None, True
    return None, sorted(iris), True


def _value_to_canonical(val: Union[IRI, Literal, IriStem]) -> Union[str, dict]:
    """Convert a value to canonical JSON-serialisable form."""
    if isinstance(val, IRI):
        return val.value
    if isinstance(val, Literal):
        d: dict = {"value": val.value}
        if val.datatype:
            d["datatype"] = val.datatype.value
        if val.language:
            d["language"] = val.language
        return d
    if isinstance(val, IriStem):
        return val.stem
    return str(val)


def _convert_cardinality(tc: TripleConstraint) -> CanonicalCardinality:
    """Convert ShEx cardinality to canonical form. Default {1,1}."""
    mn = tc.cardinality.effective_min  # defaults to 1
    mx_raw = tc.cardinality.effective_max  # None = unbounded, int otherwise
    mx = UNBOUNDED if mx_raw is None else mx_raw
    return CanonicalCardinality(min=mn, max=mx)


def _identify_main_shapes(schema: ShExSchema) -> set[str]:
    """Identify main (non-auxiliary) shape names."""
    main_names: set[str] = set()
    if schema.start:
        main_names.add(schema.start.value)
    else:
        for shape in schema.shapes:
            tcs = _get_triple_constraints(shape)
            if len(tcs) > 1:
                main_names.add(shape.name.value)
    if not main_names and schema.shapes:
        main_names.add(schema.shapes[0].name.value)
    return main_names


def convert_shex_to_json(shex: ShExSchema) -> CanonicalSchema:
    """Convert a ShEx schema to a canonical JSON schema.

    Args:
        shex: The ShEx schema to convert.

    Returns:
        Canonical JSON schema with normalised shapes.
    """
    main_names = _identify_main_shapes(shex)
    canonical_shapes: list[CanonicalShape] = []

    for shape in shex.shapes:
        if shape.name.value not in main_names:
            continue

        tcs = _get_triple_constraints(shape)
        target_class = _extract_target_class(tcs)

        properties: list[CanonicalProperty] = []
        for tc in tcs:
            # Skip the instance-of constraint that maps to targetClass
            if _is_target_class_tc(tc, target_class):
                continue

            path = tc.predicate.value
            cardinality = _convert_cardinality(tc)
            prop = CanonicalProperty(path=path, cardinality=cardinality)

            # Resolve constraint
            if isinstance(tc.constraint, ShapeRef):
                ref_name = tc.constraint.name.value
                class_ref, class_ref_or, resolved = _resolve_shape_ref(
                    ref_name, shex
                )
                if resolved:
                    if class_ref:
                        prop.classRef = class_ref
                    elif class_ref_or:
                        prop.classRefOr = class_ref_or
                else:
                    prop.nodeRef = ref_name

            elif isinstance(tc.constraint, NodeConstraint):
                nc = tc.constraint

                if nc.datatype:
                    prop.datatype = nc.datatype.value

                elif nc.node_kind:
                    prop.nodeKind = nc.node_kind.value

                elif nc.values:
                    # Check for IRI stem
                    if (len(nc.values) == 1
                            and isinstance(nc.values[0].value, IriStem)):
                        prop.iriStem = nc.values[0].value.stem
                    else:
                        # Value set
                        vals = [
                            _value_to_canonical(v.value) for v in nc.values
                            if isinstance(v.value, (IRI, Literal))
                        ]
                        if len(vals) == 1:
                            prop.hasValue = vals[0]
                        elif len(vals) > 1:
                            prop.inValues = vals

                elif nc.pattern:
                    prop.pattern = nc.pattern

            properties.append(prop)

        canonical_shapes.append(CanonicalShape(
            name=shape.name.value,
            targetClass=target_class,
            closed=shape.closed,
            properties=properties,
        ))

    return CanonicalSchema(shapes=canonical_shapes)
