"""Convert a ShexJESchema to a CanonicalSchema.

Only the subset of ShexJE that maps cleanly to the canonical model is
converted.  Constructs that go beyond canonical expressivity (property paths,
qualified value shapes, SPARQL constraints, etc.) are silently skipped —
consistent with the existing policy for features outside the canonical model.

Mapping strategy
----------------
* :class:`ShapeE` → :class:`CanonicalShape`
* :class:`ShapeOrE` (all-NodeConstraint children with datatype) → datatypeOr
* :class:`TripleConstraintE` → :class:`CanonicalProperty`

Value-expr resolution
~~~~~~~~~~~~~~~~~~~~~
``valueExpr`` is resolved recursively:

+---------------------------------------+---------------------+
| ShexJE valueExpr                      | Canonical field     |
+=======================================+=====================+
| NodeConstraintE(datatype=…)           | datatype            |
+---------------------------------------+---------------------+
| NodeConstraintE(nodeKind=…)           | nodeKind            |
+---------------------------------------+---------------------+
| NodeConstraintE(values=[single IRI])  | hasValue            |
+---------------------------------------+---------------------+
| NodeConstraintE(values=[many])        | inValues            |
+---------------------------------------+---------------------+
| NodeConstraintE(values=[IriStem])     | iriStem             |
+---------------------------------------+---------------------+
| ShapeRefE                             | nodeRef             |
+---------------------------------------+---------------------+
| ShapeOrE (all NodeConstraint+datatype)| classRefOr          |
+---------------------------------------+---------------------+

Shorthand fields on TripleConstraintE take priority over ``valueExpr``.
"""
from __future__ import annotations

from typing import Optional, Union

from shaclex_py.schema.canonical import (
    CanonicalCardinality,
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)
from shaclex_py.schema.shexje import (
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
)

_UNBOUNDED = -1


def convert_shexje_to_canonical(schema: ShexJESchema) -> CanonicalSchema:
    """Convert *schema* to a :class:`CanonicalSchema`.

    Args:
        schema: Source :class:`ShexJESchema`.

    Returns:
        Equivalent :class:`CanonicalSchema` (best-effort; advanced ShexJE
        constructs are silently dropped).
    """
    shapes: list[CanonicalShape] = []

    for decl in schema.shapes:
        cs = _convert_decl(decl)
        if cs is not None:
            shapes.append(cs)

    return CanonicalSchema(shapes=shapes)


# ── Shape conversion ──────────────────────────────────────────────────────────

def _convert_decl(decl: ShapeDecl) -> Optional[CanonicalShape]:
    if isinstance(decl, ShapeE):
        return _convert_shape(decl)
    if isinstance(decl, ShapeOrE):
        return _convert_shape_or_as_datatype_or(decl)
    if isinstance(decl, NodeConstraintE):
        return _convert_node_constraint_decl(decl)
    # ShapeAnd / ShapeNot / ShapeXone at top level are beyond canonical — skip.
    return None


def _convert_shape(shape: ShapeE) -> CanonicalShape:
    properties: list[CanonicalProperty] = []

    if shape.expression is not None:
        props = _collect_properties(shape.expression)
        properties.extend(props)

    return CanonicalShape(
        name=shape.id,
        targetClass=_normalize_target_class(shape.targetClass),
        closed=shape.closed,
        properties=properties,
    )


def _convert_node_constraint_decl(nc: NodeConstraintE) -> Optional[CanonicalShape]:
    """Map a top-level NodeConstraintE to a CanonicalShape with node-level constraints."""
    if not nc.id:
        return None
    in_vals = None
    if nc.in_values is not None:
        in_vals = [_normalise_value(v) for v in nc.in_values]
    elif nc.values is not None:
        in_vals = [_normalise_value(v) for v in nc.values]
    return CanonicalShape(
        name=nc.id,
        nodeKind=nc.nodeKind,
        datatype=nc.datatype,
        inValues=in_vals,
    )


def _convert_shape_or_as_datatype_or(shape_or: ShapeOrE) -> Optional[CanonicalShape]:
    """Map an all-datatype ShapeOr to a datatypeOr CanonicalShape."""
    if not shape_or.id:
        return None
    datatypes: list[str] = []
    for se in shape_or.shapeExprs:
        if isinstance(se, NodeConstraintE) and se.datatype is not None:
            datatypes.append(se.datatype)
        else:
            return None  # mixed content — cannot represent in canonical
    if not datatypes:
        return None
    return CanonicalShape(
        name=shape_or.id,
        datatypeOr=datatypes,
        closed=False,
        properties=[],
    )


# ── Triple-expression → property list ────────────────────────────────────────

def _collect_properties(te: TripleExpression) -> list[CanonicalProperty]:
    if isinstance(te, str):
        return []   # TripleExprRef — not resolvable without full schema
    if isinstance(te, TripleConstraintE):
        cp = _convert_triple_constraint(te)
        return [cp] if cp is not None else []
    if isinstance(te, EachOfE):
        result: list[CanonicalProperty] = []
        for sub in te.expressions:
            result.extend(_collect_properties(sub))
        return result
    # OneOf at triple-expression level — flatten (semantics relaxed)
    from shaclex_py.schema.shexje import OneOfE
    if isinstance(te, OneOfE):
        result = []
        for sub in te.expressions:
            result.extend(_collect_properties(sub))
        return result
    return []


# ── TripleConstraint → CanonicalProperty ─────────────────────────────────────

def _convert_triple_constraint(tc: TripleConstraintE) -> Optional[CanonicalProperty]:
    # Skip inverse predicates and complex paths (beyond canonical model)
    if tc.path is not None or tc.inverse:
        return None
    if tc.predicate is None:
        return None

    cardinality = _parse_cardinality(tc.min, tc.max)
    cp = CanonicalProperty(path=tc.predicate, cardinality=cardinality)

    # 1. Shorthand fields take priority -----------------------------------
    if tc.classRef is not None:
        cp.classRef = tc.classRef
        return cp

    if tc.classRefOr is not None:
        cp.classRefOr = sorted(tc.classRefOr)
        return cp

    if tc.iriStem is not None:
        cp.iriStem = tc.iriStem
        return cp

    if tc.hasValue is not None:
        cp.hasValue = tc.hasValue
        return cp

    if tc.in_values is not None:
        cp.inValues = [_normalise_value(v) for v in tc.in_values]
        return cp

    # 2. valueExpr resolution ---------------------------------------------
    if tc.valueExpr is not None:
        _resolve_value_expr(tc.valueExpr, cp)

    return cp


def _resolve_value_expr(ve: ShapeExpression, cp: CanonicalProperty) -> None:
    """Mutate *cp* in-place based on the resolved *ve*."""
    if isinstance(ve, NodeConstraintE):
        _resolve_node_constraint(ve, cp)
        return

    if isinstance(ve, ShapeRefE):
        cp.nodeRef = ve.reference
        return

    if isinstance(ve, ShapeOrE):
        # Check if this is an OR of single-class shapes (classRefOr pattern)
        classes = _extract_or_classes(ve)
        if classes is not None:
            cp.classRefOr = sorted(classes)
        # Other ShapeOr forms are beyond canonical — leave cp unconstrained
        return

    if isinstance(ve, (ShapeAndE, ShapeNotE, ShapeXoneE, ShapeE)):
        # Beyond canonical expressivity — skip
        return


def _resolve_node_constraint(nc: NodeConstraintE, cp: CanonicalProperty) -> None:
    if nc.datatype is not None:
        cp.datatype = nc.datatype
        if nc.pattern is not None:
            cp.pattern = nc.pattern
        return

    if nc.nodeKind is not None:
        cp.nodeKind = nc.nodeKind
        if nc.pattern is not None:
            cp.pattern = nc.pattern
        return

    if nc.hasValue is not None:
        cp.hasValue = nc.hasValue
        return

    if nc.in_values is not None:
        cp.inValues = [_normalise_value(v) for v in nc.in_values]
        return

    if nc.values is not None:
        # IriStem value set → iriStem
        if len(nc.values) == 1 and isinstance(nc.values[0], IriStemValue):
            cp.iriStem = nc.values[0].stem
            return
        # Value set → inValues (single-element sets stay as inValues, not hasValue,
        # because hasValue is routed through tc.hasValue shorthand, not nc.values)
        cp.inValues = [_normalise_value(v) for v in nc.values]
        return

    if nc.pattern is not None:
        cp.pattern = nc.pattern


def _extract_or_classes(shape_or: ShapeOrE) -> Optional[list[str]]:
    """Return list of class IRIs if the ShapeOr encodes a classRefOr pattern."""
    classes: list[str] = []
    for se in shape_or.shapeExprs:
        if isinstance(se, NodeConstraintE) and se.values and len(se.values) == 1:
            v = se.values[0]
            if isinstance(v, str):
                classes.append(v)
                continue
        # Does not match classRefOr pattern
        return None
    return classes if classes else None


# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_cardinality(mn: Optional[int], mx: Optional[int]) -> CanonicalCardinality:
    return CanonicalCardinality(
        min=mn if mn is not None else 0,
        max=mx if mx is not None else _UNBOUNDED,
    )


def _normalize_target_class(tc) -> Optional[str]:
    if tc is None:
        return None
    if isinstance(tc, list):
        return tc[0] if tc else None
    return str(tc)


def _normalise_value(v) -> Union[str, dict]:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v
    if hasattr(v, "to_dict"):
        return v.to_dict()
    return str(v)
