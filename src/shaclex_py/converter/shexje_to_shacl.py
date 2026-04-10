"""ShexJE → SHACL direct converter.

ShexJE is the canonical format.  This replaces the two-step
ShexJE → CanonicalSchema → SHACL pipeline with a single direct pass.
"""
from __future__ import annotations

from typing import Optional, Union

from shaclex_py.schema.common import IRI, UNBOUNDED, Literal, NodeKind, Path
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.shexje import (
    AlternativePath,
    EachOfE,
    IriStemValue,
    NodeConstraintE,
    ShapeAndE,
    ShapeDecl,
    ShapeE,
    ShapeExpression,
    ShapeNotE,
    ShapeOrE,
    ShapeRefE,
    ShapeXoneE,
    ShexJESchema,
    TripleConstraintE,
    TripleExpression,
    OneOfE,
)

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_UNBOUNDED = -1
_SHACL_SHAPES_BASE = "http://shaclshapes.org/"

_NODE_KIND_MAP: dict[str, NodeKind] = {
    "IRI": NodeKind.IRI,
    "BlankNode": NodeKind.BLANK_NODE,
    "Literal": NodeKind.LITERAL,
    "BlankNodeOrIRI": NodeKind.BLANK_NODE_OR_IRI,
    "BlankNodeOrLiteral": NodeKind.BLANK_NODE_OR_LITERAL,
    "IRIOrLiteral": NodeKind.IRI_OR_LITERAL,
    # ShexJ lowercase forms (kept for robustness)
    "iri": NodeKind.IRI,
    "bnode": NodeKind.BLANK_NODE,
    "literal": NodeKind.LITERAL,
    "nonliteral": NodeKind.BLANK_NODE_OR_IRI,
}

# Standard SHACL prefixes
from shaclex_py.schema.common import Prefix
_STANDARD_PREFIXES = [
    Prefix("sh", "http://www.w3.org/ns/shacl#"),
    Prefix("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    Prefix("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    Prefix("xsd", "http://www.w3.org/2001/XMLSchema#"),
    Prefix("schema", "http://schema.org/"),
    Prefix("owl", "http://www.w3.org/2002/07/owl#"),
    Prefix("yago", "http://yago-knowledge.org/resource/"),
]


# ── Shape filtering ───────────────────────────────────────────────────────────

def _is_value_shape_stub(shape: ShapeE) -> bool:
    """True for shapes that only serve as companion value-shape helpers."""
    return shape.predicate is not None and shape.targetClass is None


def _is_rdf_type_only_stub(shape: ShapeE) -> bool:
    """True for shapes with only an unconstrained rdf:type triple (no targetClass)."""
    if shape.targetClass is not None:
        return False
    expr = shape.expression
    if expr is None:
        return True
    if isinstance(expr, TripleConstraintE):
        return (expr.predicate == _RDF_TYPE
                and expr.min is None and expr.max is None)
    return False


# ── Value helpers ─────────────────────────────────────────────────────────────

def _shexje_value_to_shacl(val) -> Union[IRI, Literal]:
    if isinstance(val, str):
        return IRI(val)
    if isinstance(val, dict):
        dt = IRI(val["datatype"]) if "datatype" in val else None
        lang = val.get("language")
        return Literal(value=val["value"], datatype=dt, language=lang)
    return IRI(str(val))


def _shape_ref_iri(ref: str) -> IRI:
    """Reconstruct the full SHACL shape IRI from a short name."""
    return IRI(f"{_SHACL_SHAPES_BASE}{ref.replace(' ', '_')}Shape")


# ── Value-expr resolution → SHACL PropertyShape fields ───────────────────────

def _resolve_ve_to_ps(
    ve: ShapeExpression,
    shape_map: dict[str, ShapeDecl],
    ps: PropertyShape,
) -> None:
    """Mutate *ps* fields based on the resolved *ve*."""
    if isinstance(ve, str):
        referenced = shape_map.get(ve)
        if isinstance(referenced, ShapeE):
            _resolve_value_shape_to_ps(referenced, ps)
            if ps.class_ is None and ps.or_constraints is None:
                ps.node = _shape_ref_iri(ve)
        else:
            ps.node = _shape_ref_iri(ve)
        return

    if isinstance(ve, NodeConstraintE):
        _resolve_nc_to_ps(ve, ps)
        return

    if isinstance(ve, ShapeRefE):
        referenced = shape_map.get(ve.reference)
        if isinstance(referenced, ShapeE):
            _resolve_value_shape_to_ps(referenced, ps)
            if ps.class_ is None and ps.or_constraints is None:
                ps.node = _shape_ref_iri(ve.reference)
        else:
            ps.node = _shape_ref_iri(ve.reference)
        return

    if isinstance(ve, ShapeOrE):
        classes = _extract_or_classes(ve)
        if classes:
            ps.or_constraints = [IRI(c) for c in classes]
        return

    if isinstance(ve, ShapeAndE):
        # Pattern: [shape_ref, NodeConstraint(nodeKind=...)]
        str_refs = [e for e in ve.shapeExprs if isinstance(e, str)]
        ncs = [e for e in ve.shapeExprs if isinstance(e, NodeConstraintE)]
        if str_refs:
            _resolve_ve_to_ps(str_refs[0], shape_map, ps)
        if ncs:
            _resolve_nc_to_ps(ncs[0], ps)
        return

    # ShapeNot / ShapeXone / ShapeE at property level — beyond SHACL property shape scope
    return


def _resolve_value_shape_to_ps(shape: ShapeE, ps: PropertyShape) -> None:
    """Extract class IRI(s) from a value-shape helper ShapeE."""
    # Compact shorthand: predicate + values on ShapeE
    if shape.predicate is not None and shape.values is not None:
        class_iris = [v for v in shape.values if isinstance(v, str)]
        if len(class_iris) == 1:
            ps.class_ = IRI(class_iris[0])
        elif len(class_iris) > 1:
            ps.or_constraints = [IRI(c) for c in sorted(class_iris)]
        return
    # Full expression form
    if isinstance(shape.expression, TripleConstraintE):
        _extract_class_from_tc(shape.expression, ps)


def _extract_class_from_tc(tc: TripleConstraintE, ps: PropertyShape) -> None:
    if not isinstance(tc.valueExpr, NodeConstraintE):
        return
    nc = tc.valueExpr
    if nc.values:
        class_iris = [v for v in nc.values if isinstance(v, str)]
        if len(class_iris) == 1:
            ps.class_ = IRI(class_iris[0])
        elif len(class_iris) > 1:
            ps.or_constraints = [IRI(c) for c in sorted(class_iris)]


def _resolve_nc_to_ps(nc: NodeConstraintE, ps: PropertyShape) -> None:
    if nc.datatype is not None:
        ps.datatype = IRI(nc.datatype)
    if nc.nodeKind is not None:
        ps.node_kind = _NODE_KIND_MAP.get(nc.nodeKind)
    if nc.datatype is not None or nc.nodeKind is not None:
        if nc.pattern is not None:
            ps.pattern = nc.pattern
        return
    if nc.hasValue is not None:
        ps.has_value = _shexje_value_to_shacl(nc.hasValue)
        return
    if nc.in_values is not None:
        ps.in_values = [_shexje_value_to_shacl(v) for v in nc.in_values]
        return
    if nc.values is not None:
        if len(nc.values) == 1 and isinstance(nc.values[0], IriStemValue):
            ps.pattern = f"^{nc.values[0].stem}/"
            return
        if len(nc.values) == 1 and isinstance(nc.values[0], str):
            ps.has_value = IRI(nc.values[0])
            return
        ps.in_values = [_shexje_value_to_shacl(v) for v in nc.values]
        return
    if nc.pattern is not None:
        ps.pattern = nc.pattern


def _extract_or_classes(shape_or: ShapeOrE) -> Optional[list[str]]:
    classes: list[str] = []
    for se in shape_or.shapeExprs:
        if isinstance(se, NodeConstraintE) and se.values and len(se.values) == 1:
            v = se.values[0]
            if isinstance(v, str):
                classes.append(v)
                continue
        return None
    return classes or None


# ── Triple expression → PropertyShape(s) ─────────────────────────────────────

def _collect_tcs(te: TripleExpression) -> list[TripleConstraintE]:
    """Flatten a triple expression into individual TripleConstraintEs."""
    if isinstance(te, TripleConstraintE):
        return [te]
    if isinstance(te, EachOfE):
        result: list[TripleConstraintE] = []
        for sub in te.expressions:
            result.extend(_collect_tcs(sub))
        return result
    if isinstance(te, OneOfE):
        result = []
        for sub in te.expressions:
            result.extend(_collect_tcs(sub))
        return result
    return []


def _tc_to_ps(
    tc: TripleConstraintE,
    shape_map: dict[str, ShapeDecl],
) -> Optional[PropertyShape]:
    """Convert a TripleConstraintE to a SHACL PropertyShape."""
    # Complex paths other than AlternativePath are skipped
    if tc.path is not None and not isinstance(tc.path, AlternativePath):
        return None
    if tc.predicate is None and tc.path is None:
        return None

    # Path
    if isinstance(tc.path, AlternativePath):
        alt_iris = [IRI(e) for e in tc.path.expressions if isinstance(e, str)]
        if not alt_iris:
            return None
        ps = PropertyShape(
            path=Path(iri=alt_iris[0]),
            alternative_paths=alt_iris,
        )
    else:
        ps = PropertyShape(path=Path(iri=IRI(tc.predicate)))  # type: ignore[arg-type]

    # Cardinality
    mn = tc.min if tc.min is not None else 0
    mx = tc.max if tc.max is not None else _UNBOUNDED
    ps.min_count = mn if mn != 0 else None
    ps.max_count = mx if mx != _UNBOUNDED else None

    # valueExpr
    if tc.valueExpr is not None:
        _resolve_ve_to_ps(tc.valueExpr, shape_map, ps)

    return ps


# ── Main converter ────────────────────────────────────────────────────────────

def convert_shexje_to_shacl(shexje: ShexJESchema) -> SHACLSchema:
    """Convert a ShexJE schema directly to a SHACLSchema.

    Args:
        shexje: Parsed ShexJE schema.

    Returns:
        Equivalent SHACL schema.
    """
    shape_map: dict[str, ShapeDecl] = {
        s.id: s for s in shexje.shapes if hasattr(s, "id") and s.id
    }

    # Honour start-shape ordering (place start shape first)
    start_decl = shape_map.get(shexje.start) if shexje.start else None
    ordered: list[ShapeDecl] = []
    if start_decl is not None:
        ordered.append(start_decl)
    for decl in shexje.shapes:
        if start_decl is not None and decl is start_decl:
            continue
        ordered.append(decl)

    node_shapes: list[NodeShape] = []

    for decl in ordered:
        ns = _decl_to_node_shape(decl, shape_map)
        if ns is not None:
            node_shapes.append(ns)

    return SHACLSchema(shapes=node_shapes, prefixes=list(_STANDARD_PREFIXES))


def _decl_to_node_shape(
    decl: ShapeDecl,
    shape_map: dict[str, ShapeDecl],
) -> Optional[NodeShape]:
    if isinstance(decl, ShapeE):
        if _is_value_shape_stub(decl):
            return None
        if _is_rdf_type_only_stub(decl):
            return None
        return _shape_to_node_shape(decl, shape_map)

    if isinstance(decl, ShapeOrE):
        return _shape_or_to_node_shape(decl)

    if isinstance(decl, NodeConstraintE):
        return _nc_decl_to_node_shape(decl)

    return None


def _shape_to_node_shape(
    shape: ShapeE,
    shape_map: dict[str, ShapeDecl],
) -> NodeShape:
    shape_iri = IRI(f"{_SHACL_SHAPES_BASE}{shape.id.replace(' ', '_')}Shape")
    target_class = None
    if shape.targetClass:
        tc_val = shape.targetClass
        target_class = IRI(tc_val[0] if isinstance(tc_val, list) else tc_val)

    # Collect all triple constraints
    all_tcs: list[TripleConstraintE] = []
    if shape.expression is not None:
        all_tcs = _collect_tcs(shape.expression)

    # Identify alternative groups if present
    alt_groups: Optional[list[list[str]]] = None
    if isinstance(shape.expression, EachOfE) and shape.expression.alternativeGroups:
        alt_groups = shape.expression.alternativeGroups

    all_group_preds: set[str] = set()
    pred_to_ps: dict[str, PropertyShape] = {}
    if alt_groups:
        all_group_preds = {pred for group in alt_groups for pred in group}
        for tc in all_tcs:
            pred = tc.predicate
            if pred and pred in all_group_preds:
                ps = _tc_to_ps(tc, shape_map)
                if ps:
                    pred_to_ps[pred] = ps

    # Regular properties (not in alternative groups)
    properties: list[PropertyShape] = []
    for tc in all_tcs:
        pred = tc.predicate
        if pred and pred in all_group_preds:
            continue
        ps = _tc_to_ps(tc, shape_map)
        if ps is not None:
            properties.append(ps)

    # or_property_groups: one branch per predicate in each group
    or_property_groups: Optional[list[list[PropertyShape]]] = None
    if alt_groups:
        or_property_groups = [
            [pred_to_ps[pred]]
            for group in alt_groups
            for pred in group
            if pred in pred_to_ps
        ]

    return NodeShape(
        iri=shape_iri,
        target_class=target_class,
        properties=properties,
        closed=shape.closed,
        or_property_groups=or_property_groups or None,
    )


def _shape_or_to_node_shape(shape_or: ShapeOrE) -> Optional[NodeShape]:
    """Convert a top-level ShapeOrE (OR-of-datatypes) to a NodeShape."""
    if not shape_or.id:
        return None
    datatypes: list[IRI] = []
    for se in shape_or.shapeExprs:
        if isinstance(se, NodeConstraintE) and se.datatype is not None:
            datatypes.append(IRI(se.datatype))
        else:
            return None
    if not datatypes:
        return None
    shape_iri = IRI(f"{_SHACL_SHAPES_BASE}{shape_or.id.replace(' ', '_')}Shape")
    return NodeShape(iri=shape_iri, or_datatypes=datatypes)


def _nc_decl_to_node_shape(nc: NodeConstraintE) -> Optional[NodeShape]:
    """Convert a top-level NodeConstraintE to a NodeShape with node-level constraints."""
    if not nc.id:
        return None
    shape_iri = IRI(f"{_SHACL_SHAPES_BASE}{nc.id.replace(' ', '_')}Shape")
    node_kind = _NODE_KIND_MAP.get(nc.nodeKind) if nc.nodeKind else None
    node_datatype = IRI(nc.datatype) if nc.datatype else None
    node_in_values: Optional[list] = None
    if nc.in_values is not None:
        node_in_values = [_shexje_value_to_shacl(v) for v in nc.in_values]
    elif nc.values is not None:
        node_in_values = [_shexje_value_to_shacl(v) for v in nc.values]
    return NodeShape(
        iri=shape_iri,
        node_kind=node_kind,
        node_datatype=node_datatype,
        node_in_values=node_in_values,
    )
