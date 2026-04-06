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
| str (shape ID reference)              | resolved via schema |
|   → ShapeE with predicate/values      |                     |
|     (1 value)  → classRef             |                     |
|     (N values) → classRefOr           |                     |
+---------------------------------------+---------------------+
| ShapeRefE                             | nodeRef             |
+---------------------------------------+---------------------+
| ShapeOrE (all NodeConstraint+datatype)| classRefOr          |
+---------------------------------------+---------------------+
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
    # Build a lookup map: shape ID → ShapeE for value-shape resolution
    shape_map: dict[str, ShapeDecl] = {
        s.id: s for s in schema.shapes if hasattr(s, "id") and s.id
    }

    shapes: list[CanonicalShape] = []

    for decl in schema.shapes:
        cs = _convert_decl(decl, shape_map)
        if cs is not None:
            shapes.append(cs)

    return CanonicalSchema(shapes=shapes)


# ── Shape conversion ──────────────────────────────────────────────────────────

def _convert_decl(
    decl: ShapeDecl,
    shape_map: dict[str, ShapeDecl],
) -> Optional[CanonicalShape]:
    if isinstance(decl, ShapeE):
        # Skip value-shape helpers (they have no targetClass and are referenced
        # only via valueExpr; they do not represent top-level canonical shapes)
        if decl.predicate is not None and decl.targetClass is None:
            return None
        return _convert_shape(decl, shape_map)
    if isinstance(decl, ShapeOrE):
        return _convert_shape_or_as_datatype_or(decl)
    if isinstance(decl, NodeConstraintE):
        return _convert_node_constraint_decl(decl)
    # ShapeAnd / ShapeNot / ShapeXone at top level are beyond canonical — skip.
    return None


def _convert_shape(
    shape: ShapeE,
    shape_map: dict[str, ShapeDecl],
) -> CanonicalShape:
    properties: list[CanonicalProperty] = []
    alternative_groups = None

    if shape.expression is not None:
        props = _collect_properties(shape.expression, shape_map)
        properties.extend(props)
        if isinstance(shape.expression, EachOfE) and shape.expression.alternativeGroups:
            alternative_groups = shape.expression.alternativeGroups

    return CanonicalShape(
        name=shape.id,
        targetClass=_normalize_target_class(shape.targetClass),
        closed=shape.closed,
        properties=properties,
        property_alternative_groups=alternative_groups,
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

def _collect_properties(
    te: TripleExpression,
    shape_map: dict[str, ShapeDecl],
) -> list[CanonicalProperty]:
    if isinstance(te, str):
        return []   # TripleExprRef — not resolvable without full schema
    if isinstance(te, TripleConstraintE):
        cp = _convert_triple_constraint(te, shape_map)
        return [cp] if cp is not None else []
    if isinstance(te, EachOfE):
        result: list[CanonicalProperty] = []
        for sub in te.expressions:
            result.extend(_collect_properties(sub, shape_map))
        return result
    # OneOf at triple-expression level — flatten (semantics relaxed)
    from shaclex_py.schema.shexje import OneOfE
    if isinstance(te, OneOfE):
        result = []
        for sub in te.expressions:
            result.extend(_collect_properties(sub, shape_map))
        return result
    return []


# ── TripleConstraint → CanonicalProperty ─────────────────────────────────────

def _convert_triple_constraint(
    tc: TripleConstraintE,
    shape_map: dict[str, ShapeDecl],
) -> Optional[CanonicalProperty]:
    # Handle sh:alternativePath encoded as AlternativePath
    if isinstance(tc.path, AlternativePath):
        paths = [e for e in tc.path.expressions if isinstance(e, str)]
        if not paths:
            return None
        cardinality = _parse_cardinality(tc.min, tc.max)
        cp = CanonicalProperty(path=paths[0], pathAlternatives=paths, cardinality=cardinality)
        if tc.valueExpr is not None:
            _resolve_value_expr(tc.valueExpr, cp, shape_map)
        return cp

    # Skip other complex paths (inverse, sequence, etc.) and skip if no predicate
    if tc.path is not None or tc.inverse:
        return None
    if tc.predicate is None:
        return None

    cardinality = _parse_cardinality(tc.min, tc.max)
    cp = CanonicalProperty(path=tc.predicate, cardinality=cardinality)

    if tc.valueExpr is not None:
        _resolve_value_expr(tc.valueExpr, cp, shape_map)

    return cp


def _resolve_value_expr(
    ve: ShapeExpression,
    cp: CanonicalProperty,
    shape_map: dict[str, ShapeDecl],
) -> None:
    """Mutate *cp* in-place based on the resolved *ve*."""
    # String → look up referenced shape for classRef / classRefOr
    if isinstance(ve, str):
        referenced = shape_map.get(ve)
        if referenced is not None and isinstance(referenced, ShapeE):
            _resolve_value_shape(referenced, cp)
        # Unknown reference — leave cp unconstrained
        return

    if isinstance(ve, NodeConstraintE):
        _resolve_node_constraint(ve, cp)
        return

    if isinstance(ve, ShapeRefE):
        # ShapeRef ({"type": "ShapeRef", "reference": "..."}) → look up shape
        referenced = shape_map.get(ve.reference)
        if referenced is not None and isinstance(referenced, ShapeE):
            _resolve_value_shape(referenced, cp)
            # If the referenced shape is not a value shape (e.g. self-references or
            # non-class entity shapes), nothing is extracted — fall back to nodeRef.
            if cp.classRef is None and cp.classRefOr is None:
                cp.nodeRef = ve.reference
        else:
            cp.nodeRef = ve.reference
        return

    if isinstance(ve, ShapeOrE):
        # Check if this is an OR of single-class shapes (classRefOr pattern)
        classes = _extract_or_classes(ve)
        if classes is not None:
            cp.classRefOr = sorted(classes)
        # Other ShapeOr forms are beyond canonical — leave cp unconstrained
        return

    if isinstance(ve, ShapeAndE):
        # Special case: [shape_ref, NodeConstraint(nodeKind=...)] — classRef + companion nodeKind
        shape_refs = [e for e in ve.shapeExprs if isinstance(e, str)]
        ncs = [e for e in ve.shapeExprs if isinstance(e, NodeConstraintE)]
        if shape_refs and ncs:
            _resolve_value_expr(shape_refs[0], cp, shape_map)
            _resolve_node_constraint(ncs[0], cp)
            return
        # Other ShapeAnd forms are beyond canonical expressivity — skip
        return

    if isinstance(ve, (ShapeNotE, ShapeXoneE, ShapeE)):
        # Beyond canonical expressivity — skip
        return


def _resolve_value_shape(shape: ShapeE, cp: CanonicalProperty) -> None:
    """Extract classRef / classRefOr from a value-shape ShapeE.

    Handles both the compact shorthand (``predicate`` / ``values``) and the
    full ``expression`` form.
    """
    # Compact shorthand: predicate + values directly on ShapeE
    if shape.predicate is not None and shape.values is not None:
        class_iris = [v for v in shape.values if isinstance(v, str)]
        if len(class_iris) == 1:
            cp.classRef = class_iris[0]
        elif len(class_iris) > 1:
            cp.classRefOr = sorted(class_iris)
        return

    # Full expression form: look for a TripleConstraint with a NodeConstraint values
    if shape.expression is not None:
        _extract_class_from_expression(shape.expression, cp)


def _extract_class_from_expression(
    te: TripleExpression,
    cp: CanonicalProperty,
) -> None:
    """Try to extract a classRef/classRefOr from a value-shape expression."""
    if not isinstance(te, TripleConstraintE):
        return
    if not isinstance(te.valueExpr, NodeConstraintE):
        return
    nc = te.valueExpr
    if nc.values is not None:
        class_iris = [v for v in nc.values if isinstance(v, str)]
        if len(class_iris) == 1:
            cp.classRef = class_iris[0]
        elif len(class_iris) > 1:
            cp.classRefOr = sorted(class_iris)


def _resolve_node_constraint(nc: NodeConstraintE, cp: CanonicalProperty) -> None:
    # datatype and nodeKind are captured independently — both can be present simultaneously
    # (e.g. NodeConstraintE(datatype="xsd:string", nodeKind="Literal"))
    if nc.datatype is not None:
        cp.datatype = nc.datatype
    if nc.nodeKind is not None:
        cp.nodeKind = nc.nodeKind
    if nc.datatype is not None or nc.nodeKind is not None:
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
        # Single IRI value → hasValue (value-set constraint, not a class constraint;
        # class constraints use companion value shapes referenced via ShapeRefE)
        if len(nc.values) == 1 and isinstance(nc.values[0], str):
            cp.hasValue = nc.values[0]
            return
        # Multiple values → inValues (value-set)
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
