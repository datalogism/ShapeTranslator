"""Convert a CanonicalSchema to a ShexJESchema.

Mapping strategy
----------------
* Each :class:`CanonicalShape` becomes a :class:`ShapeE`.
* ``datatypeOr`` shapes become a :class:`ShapeOrE` (top-level shape declaration).
* Each :class:`CanonicalProperty` becomes a :class:`TripleConstraintE`.
* Constraint fields are mapped to their most precise ShexJE representation:

  +--------------+-------------------------------------------------------+
  | Canonical    | ShexJE (TripleConstraintE)                            |
  +==============+=======================================================+
  | datatype     | valueExpr: NodeConstraintE(datatype=…)                |
  +--------------+-------------------------------------------------------+
  | classRef     | classRef shorthand (→ ShapeRefE on expansion)         |
  +--------------+-------------------------------------------------------+
  | classRefOr   | classRefOr shorthand (→ ShapeOrE of classes)          |
  +--------------+-------------------------------------------------------+
  | nodeKind     | valueExpr: NodeConstraintE(nodeKind=…)                |
  +--------------+-------------------------------------------------------+
  | hasValue     | hasValue shorthand                                    |
  +--------------+-------------------------------------------------------+
  | inValues     | valueExpr: NodeConstraintE(values=[…])                |
  +--------------+-------------------------------------------------------+
  | iriStem      | iriStem shorthand                                     |
  +--------------+-------------------------------------------------------+
  | nodeRef      | valueExpr: ShapeRefE(reference=…)                    |
  +--------------+-------------------------------------------------------+
  | pattern      | added to NodeConstraintE alongside primary constraint |
  +--------------+-------------------------------------------------------+
  | cardinality  | min / max on TripleConstraintE                        |
  +--------------+-------------------------------------------------------+
"""
from __future__ import annotations

from typing import Optional

from shaclex_py.schema.canonical import CanonicalProperty, CanonicalSchema, CanonicalShape
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

_UNBOUNDED = -1


def convert_canonical_to_shexje(canonical: CanonicalSchema) -> ShexJESchema:
    """Convert *canonical* to a :class:`ShexJESchema`.

    Args:
        canonical: Source :class:`CanonicalSchema`.

    Returns:
        Equivalent :class:`ShexJESchema`.
    """
    shape_decls: list = []

    for cs in canonical.shapes:
        if cs.datatypeOr:
            # DBpedia-style value shape: OR of NodeConstraints
            shape_decls.append(_make_datatype_or_shape(cs))
        else:
            shape_decls.append(_make_shape(cs))

    return ShexJESchema(shapes=shape_decls)


# ── Shape helpers ─────────────────────────────────────────────────────────────

def _make_shape(cs: CanonicalShape) -> ShapeE:
    tcs = [_make_triple_constraint(cp) for cp in cs.properties]

    if len(tcs) == 1:
        expression = tcs[0]
    elif len(tcs) > 1:
        expression = EachOfE(expressions=tcs)
    else:
        expression = None

    return ShapeE(
        id=cs.name,
        closed=cs.closed,
        expression=expression,
        targetClass=cs.targetClass,
    )


def _make_datatype_or_shape(cs: CanonicalShape) -> ShapeOrE:
    """Map ``datatypeOr`` to a top-level ``ShapeOr`` of ``NodeConstraint``s."""
    nc_list = [NodeConstraintE(datatype=dt) for dt in cs.datatypeOr]  # type: ignore[union-attr]
    return ShapeOrE(id=cs.name, shapeExprs=nc_list)


# ── Property helpers ──────────────────────────────────────────────────────────

def _make_triple_constraint(cp: CanonicalProperty) -> TripleConstraintE:
    tc = TripleConstraintE(predicate=cp.path)

    # Cardinality
    mn = cp.cardinality.min
    mx = cp.cardinality.max
    if mn != 0 or mx != _UNBOUNDED:
        tc.min = mn
        tc.max = mx

    # Primary constraint
    if cp.datatype is not None:
        nc = NodeConstraintE(datatype=cp.datatype)
        if cp.pattern is not None:
            nc.pattern = cp.pattern
        tc.valueExpr = nc

    elif cp.classRef is not None:
        tc.classRef = cp.classRef

    elif cp.classRefOr is not None:
        tc.classRefOr = list(cp.classRefOr)

    elif cp.nodeKind is not None:
        nc = NodeConstraintE(nodeKind=cp.nodeKind)
        if cp.pattern is not None:
            nc.pattern = cp.pattern
        tc.valueExpr = nc

    elif cp.hasValue is not None:
        tc.hasValue = cp.hasValue

    elif cp.inValues is not None:
        tc.valueExpr = NodeConstraintE(
            values=_canonical_values_to_shexje(cp.inValues)
        )

    elif cp.iriStem is not None:
        tc.iriStem = cp.iriStem

    elif cp.nodeRef is not None:
        tc.valueExpr = ShapeRefE(reference=cp.nodeRef)

    # Standalone pattern (no primary constraint)
    elif cp.pattern is not None:
        tc.valueExpr = NodeConstraintE(pattern=cp.pattern)

    return tc


def _canonical_values_to_shexje(values: list) -> list[ValueSetEntry]:
    """Convert canonical inValues list to ShexJE value-set entries."""
    result: list[ValueSetEntry] = []
    for v in values:
        if isinstance(v, str):
            result.append(v)
        elif isinstance(v, dict):
            # canonical literal: {"value": "…", "datatype": "…"}  or
            #                    {"value": "…", "language": "…"}
            result.append(v)
        else:
            result.append(str(v))
    return result
