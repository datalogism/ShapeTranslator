"""ShEx → ShexJE direct converter.

ShexJE is the canonical format.  This replaces the two-step
ShEx → CanonicalSchema → ShexJE pipeline with a single direct pass.
"""
from __future__ import annotations

from typing import Optional

from shaclex_py.schema.common import IRI, UNBOUNDED, IriStem, Literal, NodeKind
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
from shaclex_py.schema.shexje import (
    EachOfE,
    IriStemValue,
    NodeConstraintE,
    ShapeE,
    ShapeOrE,
    ShapeRefE,
    ShexJESchema,
    TripleConstraintE,
    ValueSetEntry,
)

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_WDT_P31 = "http://www.wikidata.org/prop/direct/P31"
_INSTANCE_OF = {_RDF_TYPE, _WDT_P31}
_UNBOUNDED = -1


# ── Shape filtering helpers ───────────────────────────────────────────────────

def _get_triple_constraints(shape) -> list[TripleConstraint]:
    if isinstance(shape, NodeConstraintShape) or shape.expression is None:
        return []
    if isinstance(shape.expression, TripleConstraint):
        return [shape.expression]
    if isinstance(shape.expression, EachOf):
        return [e for e in shape.expression.expressions if isinstance(e, TripleConstraint)]
    return []


def _extract_target_class(tcs: list[TripleConstraint]) -> Optional[str]:
    for tc in tcs:
        if tc.predicate.value not in _INSTANCE_OF:
            continue
        if not isinstance(tc.constraint, NodeConstraint):
            continue
        if tc.constraint.values and len(tc.constraint.values) == 1:
            v = tc.constraint.values[0].value
            if isinstance(v, IRI):
                return v.value
    return None


def _is_target_class_tc(tc: TripleConstraint, target_class: Optional[str]) -> bool:
    if not target_class or tc.predicate.value not in _INSTANCE_OF:
        return False
    if not isinstance(tc.constraint, NodeConstraint):
        return False
    if tc.constraint.values and len(tc.constraint.values) == 1:
        v = tc.constraint.values[0].value
        return isinstance(v, IRI) and v.value == target_class
    return False


def _identify_main_shapes(shex: ShExSchema) -> set[str]:
    """Return names of shapes that represent top-level schemas (not auxiliary class shapes)."""
    main: set[str] = set()
    # NodeConstraintShapes are always main
    for s in shex.shapes:
        if isinstance(s, NodeConstraintShape):
            main.add(s.name.value)
    # Start shape
    if shex.start:
        main.add(shex.start.value)
    else:
        # Shapes with more than one TC are main
        for s in shex.shapes:
            if not isinstance(s, NodeConstraintShape) and len(_get_triple_constraints(s)) > 1:
                main.add(s.name.value)
    # Fallback: first non-NCS shape
    if not any(not isinstance(s, NodeConstraintShape) and s.name.value in main
               for s in shex.shapes):
        for s in shex.shapes:
            if not isinstance(s, NodeConstraintShape):
                main.add(s.name.value)
                break
    return main


# ── Value-shape resolution ────────────────────────────────────────────────────

def _resolve_shape_ref(
    ref_name: str,
    shape_map: dict,
) -> tuple[Optional[str], Optional[list[str]]]:
    """Return (classRef, classRefOr) for an auxiliary class shape, or (None, None)."""
    ref_shape = shape_map.get(ref_name)
    if ref_shape is None or isinstance(ref_shape, NodeConstraintShape):
        return None, None
    tcs = _get_triple_constraints(ref_shape)
    if len(tcs) != 1:
        return None, None
    tc = tcs[0]
    if not isinstance(tc.constraint, NodeConstraint) or not tc.constraint.values:
        return None, None
    iris = [v.value.value for v in tc.constraint.values if isinstance(v.value, IRI)]
    if not iris:
        return None, None
    if len(iris) == 1:
        return iris[0], None
    return None, sorted(iris)


def _local_name(iri: str) -> str:
    for sep in ("#", "/"):
        idx = iri.rfind(sep)
        if idx != -1:
            return iri[idx + 1:]
    return iri


def _derive_value_shape_id(class_iris: list[str]) -> str:
    return "Or".join(_local_name(iri) for iri in sorted(class_iris))


def _ensure_value_shape(
    class_iris: list[str],
    value_shapes: dict[tuple, ShapeE],
    type_predicate: str,
) -> str:
    key = tuple(sorted(class_iris))
    if key not in value_shapes:
        shape_id = _derive_value_shape_id(class_iris)
        value_shapes[key] = ShapeE(
            id=shape_id,
            extra=[type_predicate],
            predicate=type_predicate,
            values=list(class_iris),
        )
    return value_shapes[key].id


# ── Value helpers ─────────────────────────────────────────────────────────────

def _vsv_to_shexje(vsv: ValueSetValue) -> ValueSetEntry:
    v = vsv.value
    if isinstance(v, IRI):
        return v.value
    if isinstance(v, Literal):
        d: dict = {"value": v.value}
        if v.datatype:
            d["type"] = v.datatype.value
        if v.language:
            d["language"] = v.language
        return d
    if isinstance(v, IriStem):
        return IriStemValue(stem=v.stem)
    return str(v)


# ── Triple constraint conversion ──────────────────────────────────────────────

def _tc_to_shexje(
    tc: TripleConstraint,
    shape_map: dict,
    value_shapes: dict[tuple, ShapeE],
    type_predicate: str,
) -> Optional[TripleConstraintE]:
    """Convert a ShEx TripleConstraint to a ShexJE TripleConstraintE."""
    tc_e = TripleConstraintE(predicate=tc.predicate.value)

    # Cardinality (ShEx default {1,1})
    mn = tc.cardinality.effective_min
    mx_raw = tc.cardinality.effective_max
    mx = _UNBOUNDED if mx_raw is None else mx_raw
    if mn != 0 or mx != _UNBOUNDED:
        tc_e.min = mn
        tc_e.max = mx

    if isinstance(tc.constraint, ShapeRef):
        ref_name = tc.constraint.name.value
        class_ref, class_ref_or = _resolve_shape_ref(ref_name, shape_map)
        if class_ref:
            tc_e.valueExpr = _ensure_value_shape([class_ref], value_shapes, type_predicate)
        elif class_ref_or:
            tc_e.valueExpr = _ensure_value_shape(class_ref_or, value_shapes, type_predicate)
        else:
            tc_e.valueExpr = ShapeRefE(reference=ref_name)

    elif isinstance(tc.constraint, NodeConstraint):
        nc = tc.constraint
        if nc.datatype:
            ve = NodeConstraintE(datatype=nc.datatype.value)
            if nc.pattern:
                ve.pattern = nc.pattern
            tc_e.valueExpr = ve
        elif nc.node_kind:
            ve = NodeConstraintE(nodeKind=nc.node_kind.value)
            if nc.pattern:
                ve.pattern = nc.pattern
            tc_e.valueExpr = ve
        elif nc.values:
            shexje_vals = [_vsv_to_shexje(v) for v in nc.values]
            tc_e.valueExpr = NodeConstraintE(values=shexje_vals)
        elif nc.pattern:
            tc_e.valueExpr = NodeConstraintE(pattern=nc.pattern)

    return tc_e


# ── Main converter ────────────────────────────────────────────────────────────

def convert_shex_to_shexje(
    shex: ShExSchema,
    type_predicate: str = _RDF_TYPE,
) -> ShexJESchema:
    """Convert a ShEx schema directly to a ShexJESchema.

    Args:
        shex: Parsed ShEx schema.
        type_predicate: IRI used as the class-membership predicate in companion
            value shapes (default: ``rdf:type``).

    Returns:
        Equivalent ShexJE schema.
    """
    main_names = _identify_main_shapes(shex)
    shape_map = {s.name.value: s for s in shex.shapes}
    value_shapes: dict[tuple, ShapeE] = {}
    shape_decls: list = []

    for shape in shex.shapes:
        if shape.name.value not in main_names:
            continue

        # NodeConstraintShape → NodeConstraintE or ShapeOrE
        if isinstance(shape, NodeConstraintShape):
            if shape.values is not None:
                vals = [_vsv_to_shexje(v) for v in shape.values]
                shape_decls.append(NodeConstraintE(id=shape.name.value, values=vals))
            elif shape.datatypes:
                nc_list = [NodeConstraintE(datatype=dt.value) for dt in shape.datatypes]
                shape_decls.append(ShapeOrE(id=shape.name.value, shapeExprs=nc_list))
            else:
                shape_decls.append(NodeConstraintE(
                    id=shape.name.value,
                    nodeKind=shape.node_kind.value if shape.node_kind else None,
                    datatype=shape.datatype.value if shape.datatype else None,
                ))
            continue

        tcs = _get_triple_constraints(shape)
        target_class = _extract_target_class(tcs)

        triple_constraints: list[TripleConstraintE] = []
        for tc in tcs:
            if _is_target_class_tc(tc, target_class):
                continue
            # Expand alternativePaths (ShEx serialiser creates a OneOf per path)
            tc_e = _tc_to_shexje(tc, shape_map, value_shapes, type_predicate)
            if tc_e is not None:
                triple_constraints.append(tc_e)

        if not triple_constraints:
            expression = None
        elif len(triple_constraints) == 1:
            expression = triple_constraints[0]
        else:
            expression = EachOfE(expressions=triple_constraints)

        shape_decls.append(ShapeE(
            id=shape.name.value,
            closed=shape.closed,
            expression=expression,
            targetClass=target_class,
        ))

    # Append companion value shapes in deterministic order
    for vs in sorted(value_shapes.values(), key=lambda s: s.id):
        shape_decls.append(vs)

    return ShexJESchema(shapes=shape_decls)
