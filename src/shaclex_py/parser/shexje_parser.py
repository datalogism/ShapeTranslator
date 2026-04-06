"""Parse ShexJE JSON into a ShexJESchema object.

Supports:
* Full native ShexJE / ShexJ constructs (``type`` discriminator).
* Value-shape shorthand on ShapeE (``predicate``, ``values``).
* Compact or full IRI strings everywhere.

Backward compatibility
----------------------
Older ShexJE documents may carry the removed shorthand fields
``classRef``, ``classRefOr``, ``iriStem``, ``hasValue``, ``in`` directly on
``TripleConstraint`` objects.  The parser silently converts these to proper
``valueExpr`` forms so legacy files continue to work:

* ``classRef: X``         → ``valueExpr: NodeConstraintE(values=[X])``
  (inline; full value-shape generation requires schema context)
* ``classRefOr: [X, Y]``  → ``valueExpr: NodeConstraintE(values=[X, Y])``
* ``iriStem: S``           → ``valueExpr: NodeConstraintE(values=[IriStemValue(S)])``
* ``hasValue: V``          → ``valueExpr: NodeConstraintE(values=[V])``
* ``in: [...]``            → ``valueExpr: NodeConstraintE(values=[...])``
"""
from __future__ import annotations

import json
from typing import Any, Optional, Union

from shaclex_py.schema.shexje import (
    AlternativePath,
    EachOfE,
    InversePath,
    IriStemValue,
    LiteralValue,
    NodeConstraintE,
    OneOfE,
    OneOrMorePath,
    PropertyPath,
    SequencePath,
    ShapeAndE,
    ShapeE,
    ShapeExpression,
    ShapeNotE,
    ShapeOrE,
    ShapeRefE,
    ShapeXoneE,
    ShexJESchema,
    SparqlConstraintE,
    TripleConstraintE,
    TripleExpression,
    ValueSetEntry,
    ZeroOrMorePath,
    ZeroOrOnePath,
)

# Re-export for backward compatibility (external code may import from here)
__all__ = ["parse_shexje", "parse_shexje_file"]


# ── Public API ────────────────────────────────────────────────────────────────

def parse_shexje(source: str) -> ShexJESchema:
    """Parse a ShexJE JSON string or file path into a :class:`ShexJESchema`.

    Args:
        source: JSON string or path to a ``.shexje`` / ``.json`` file.

    Returns:
        Parsed :class:`ShexJESchema`.
    """
    try:
        with open(source, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, OSError):
        data = json.loads(source)

    return _parse_schema(data)


def parse_shexje_file(filepath: str) -> ShexJESchema:
    """Parse a ShexJE JSON file."""
    return parse_shexje(filepath)


# ── Schema ────────────────────────────────────────────────────────────────────

def _parse_schema(d: dict) -> ShexJESchema:
    shapes = [_parse_shape_decl(s) for s in d.get("shapes", [])]
    raw_prefixes = d.get("prefixes", {})
    # Accept both dict (ShexJE) and list-of-objects (some ShexJ dialects)
    if isinstance(raw_prefixes, list):
        prefixes = {item["prefix"]: item["iri"] for item in raw_prefixes}
    else:
        prefixes = dict(raw_prefixes)

    return ShexJESchema(
        shapes=shapes,
        prefixes=prefixes,
        base=d.get("base"),
        start=d.get("start"),
        startActs=d.get("startActs"),
        imports=d.get("imports"),
    )


# ── Shape declarations ────────────────────────────────────────────────────────

def _parse_shape_decl(d: dict) -> Any:
    t = d.get("type", "Shape")
    dispatch = {
        "Shape":       _parse_shape,
        "NodeConstraint": _parse_node_constraint,
        "ShapeOr":     _parse_shape_or,
        "ShapeAnd":    _parse_shape_and,
        "ShapeNot":    _parse_shape_not,
        "ShapeXone":   _parse_shape_xone,
    }
    fn = dispatch.get(t)
    if fn is None:
        raise ValueError(f"Unknown shape type: {t!r}")
    return fn(d)


def _parse_shape(d: dict) -> ShapeE:
    expr_raw = d.get("expression")
    expression = _parse_triple_expr(expr_raw) if expr_raw is not None else None

    and_raw = d.get("and")
    or_raw = d.get("or")
    not_raw = d.get("not")
    xone_raw = d.get("xone")
    sparql_raw = d.get("sparql")

    # Value-shape shorthand: "predicate" + "values" fields on Shape
    values_raw = d.get("values")
    values = [_parse_value_set_entry(v) for v in values_raw] if values_raw else None

    return ShapeE(
        id=d["id"],
        closed=d.get("closed", False),
        extra=d.get("extra", []),
        expression=expression,
        extends=d.get("extends", []),
        restricts=d.get("restricts", []),
        semActs=d.get("semActs"),
        annotations=d.get("annotations"),
        # ShexJE target declarations
        targetClass=d.get("targetClass"),
        targetNode=d.get("targetNode"),
        targetSubjectsOf=d.get("targetSubjectsOf"),
        targetObjectsOf=d.get("targetObjectsOf"),
        # ShexJE validation metadata
        severity=d.get("severity"),
        message=d.get("message"),
        deactivated=d.get("deactivated"),
        # ShexJE logical operators
        and_=[_parse_shape_expr(e) for e in and_raw] if and_raw else None,
        or_=[_parse_shape_expr(e) for e in or_raw] if or_raw else None,
        not_=_parse_shape_expr(not_raw) if not_raw is not None else None,
        xone=[_parse_shape_expr(e) for e in xone_raw] if xone_raw else None,
        sparql=[_parse_sparql_constraint(c) for c in sparql_raw] if sparql_raw else None,
        # ShexJE value-shape shorthand
        predicate=d.get("predicate"),
        values=values,
    )


def _parse_node_constraint(d: dict) -> NodeConstraintE:
    values_raw = d.get("values")
    in_raw = d.get("in")
    return NodeConstraintE(
        id=d.get("id"),
        nodeKind=d.get("nodeKind"),
        datatype=d.get("datatype"),
        values=[_parse_value_set_entry(v) for v in values_raw] if values_raw else None,
        pattern=d.get("pattern"),
        flags=d.get("flags"),
        minLength=d.get("minLength"),
        maxLength=d.get("maxLength"),
        minInclusive=d.get("minInclusive"),
        maxInclusive=d.get("maxInclusive"),
        minExclusive=d.get("minExclusive"),
        maxExclusive=d.get("maxExclusive"),
        totalDigits=d.get("totalDigits"),
        fractionDigits=d.get("fractionDigits"),
        hasValue=d.get("hasValue"),
        in_values=[_parse_value_set_entry(v) for v in in_raw] if in_raw else None,
        languageIn=d.get("languageIn"),
        uniqueLang=d.get("uniqueLang"),
    )


def _parse_shape_or(d: dict) -> ShapeOrE:
    return ShapeOrE(
        id=d.get("id"),
        shapeExprs=[_parse_shape_expr(e) for e in d.get("shapeExprs", [])],
        severity=d.get("severity"),
        message=d.get("message"),
        deactivated=d.get("deactivated"),
    )


def _parse_shape_and(d: dict) -> ShapeAndE:
    return ShapeAndE(
        id=d.get("id"),
        shapeExprs=[_parse_shape_expr(e) for e in d.get("shapeExprs", [])],
        severity=d.get("severity"),
        message=d.get("message"),
        deactivated=d.get("deactivated"),
    )


def _parse_shape_not(d: dict) -> ShapeNotE:
    return ShapeNotE(
        id=d.get("id"),
        shapeExpr=_parse_shape_expr(d["shapeExpr"]),
        severity=d.get("severity"),
        message=d.get("message"),
        deactivated=d.get("deactivated"),
    )


def _parse_shape_xone(d: dict) -> ShapeXoneE:
    return ShapeXoneE(
        id=d.get("id"),
        shapeExprs=[_parse_shape_expr(e) for e in d.get("shapeExprs", [])],
        severity=d.get("severity"),
        message=d.get("message"),
        deactivated=d.get("deactivated"),
    )


# ── Shape expressions ─────────────────────────────────────────────────────────

def _parse_shape_expr(v: Any) -> ShapeExpression:
    """Parse a shape expression value (dict or bare IRI string)."""
    if isinstance(v, str):
        return ShapeRefE(reference=v)
    t = v.get("type", "Shape")
    dispatch = {
        "Shape":          _parse_shape,
        "NodeConstraint": _parse_node_constraint,
        "ShapeRef":       lambda d: ShapeRefE(reference=d["reference"]),
        "ShapeOr":        _parse_shape_or,
        "ShapeAnd":       _parse_shape_and,
        "ShapeNot":       _parse_shape_not,
        "ShapeXone":      _parse_shape_xone,
    }
    fn = dispatch.get(t)
    if fn is None:
        raise ValueError(f"Unknown shape expression type: {t!r}")
    return fn(v)


# ── Triple expressions ────────────────────────────────────────────────────────

def _parse_triple_expr(v: Any) -> TripleExpression:
    """Parse a triple expression (dict or bare TripleExprRef string)."""
    if isinstance(v, str):
        return v   # TripleExprRef
    t = v.get("type", "TripleConstraint")
    if t == "TripleConstraint":
        return _parse_triple_constraint(v)
    if t == "EachOf":
        return EachOfE(
            expressions=[_parse_triple_expr(e) for e in v.get("expressions", [])],
            min=v.get("min"),
            max=v.get("max"),
            semActs=v.get("semActs"),
            annotations=v.get("annotations"),
            alternativeGroups=v.get("alternativeGroups"),
        )
    if t == "OneOf":
        return OneOfE(
            expressions=[_parse_triple_expr(e) for e in v.get("expressions", [])],
            min=v.get("min"),
            max=v.get("max"),
            semActs=v.get("semActs"),
            annotations=v.get("annotations"),
        )
    raise ValueError(f"Unknown triple expression type: {t!r}")


def _parse_triple_constraint(d: dict) -> TripleConstraintE:
    ve_raw = d.get("valueExpr")
    qvs_raw = d.get("qualifiedValueShape")
    path_raw = d.get("path")

    # Resolve valueExpr (native shexJ/shexJE form)
    value_expr = _parse_shape_expr(ve_raw) if ve_raw is not None else None

    # ── Backward-compat: convert legacy shorthand fields to valueExpr ─────
    # These fields were removed from TripleConstraintE in ShexJE v2 (shexJ
    # alignment).  Legacy documents that still carry them are silently
    # upgraded to the canonical valueExpr form.
    if value_expr is None:
        if d.get("classRef") is not None:
            # Single class IRI → inline NodeConstraint with that IRI as value.
            # Full value-shape generation (with rdf:type TripleConstraint)
            # requires schema context; the inline form preserves the IRI for
            # downstream processing.
            value_expr = NodeConstraintE(values=[d["classRef"]])

        elif d.get("classRefOr") is not None:
            value_expr = NodeConstraintE(values=list(d["classRefOr"]))

        elif d.get("iriStem") is not None:
            value_expr = NodeConstraintE(values=[IriStemValue(stem=d["iriStem"])])

        elif d.get("hasValue") is not None:
            value_expr = NodeConstraintE(values=[d["hasValue"]])

        elif d.get("in") is not None:
            in_raw = d["in"]
            value_expr = NodeConstraintE(
                values=[_parse_value_set_entry(v) for v in in_raw]
            )

    return TripleConstraintE(
        predicate=d.get("predicate"),
        valueExpr=value_expr,
        inverse=d.get("inverse", False),
        min=d.get("min"),
        max=d.get("max"),
        semActs=d.get("semActs"),
        annotations=d.get("annotations"),
        path=_parse_path(path_raw) if path_raw is not None else None,
        severity=d.get("severity"),
        message=d.get("message"),
        deactivated=d.get("deactivated"),
        equals=d.get("equals"),
        disjoint=d.get("disjoint"),
        lessThan=d.get("lessThan"),
        lessThanOrEquals=d.get("lessThanOrEquals"),
        qualifiedValueShape=_parse_shape_expr(qvs_raw) if qvs_raw is not None else None,
        qualifiedMinCount=d.get("qualifiedMinCount"),
        qualifiedMaxCount=d.get("qualifiedMaxCount"),
        qualifiedValueShapesDisjoint=d.get("qualifiedValueShapesDisjoint"),
        uniqueLang=d.get("uniqueLang"),
    )


# ── Property paths ────────────────────────────────────────────────────────────

def _parse_path(v: Any) -> PropertyPath:
    """Parse a property path (dict or plain IRI string → wrap as bare str)."""
    if isinstance(v, str):
        # A plain IRI used where a path is expected — treat as pass-through;
        # callers should use ``predicate`` for simple IRIs, but be tolerant.
        raise ValueError(
            "Plain IRI string is not a valid PropertyPath; use 'predicate' instead."
        )
    t = v["type"]
    if t == "InversePath":
        return InversePath(expression=_parse_path_or_iri(v["expression"]))
    if t == "SequencePath":
        return SequencePath(expressions=[_parse_path_or_iri(e) for e in v["expressions"]])
    if t == "AlternativePath":
        return AlternativePath(expressions=[_parse_path_or_iri(e) for e in v["expressions"]])
    if t == "ZeroOrMorePath":
        return ZeroOrMorePath(expression=_parse_path_or_iri(v["expression"]))
    if t == "OneOrMorePath":
        return OneOrMorePath(expression=_parse_path_or_iri(v["expression"]))
    if t == "ZeroOrOnePath":
        return ZeroOrOnePath(expression=_parse_path_or_iri(v["expression"]))
    raise ValueError(f"Unknown path type: {t!r}")


def _parse_path_or_iri(v: Any) -> Union[str, PropertyPath]:
    if isinstance(v, str):
        return v
    return _parse_path(v)


# ── Value set entries ─────────────────────────────────────────────────────────

def _parse_value_set_entry(v: Any) -> ValueSetEntry:
    if isinstance(v, str):
        return v   # plain IRI string
    if isinstance(v, dict):
        t = v.get("type", "")
        if t == "IriStem":
            return IriStemValue(stem=v["stem"])
        if "value" in v:
            return LiteralValue(
                value=v["value"],
                datatype=v.get("type") if t not in ("IriStem",) else None,
                language=v.get("language"),
            )
        return v   # pass-through for advanced types
    return str(v)


# ── SPARQL constraint ─────────────────────────────────────────────────────────

def _parse_sparql_constraint(d: dict) -> SparqlConstraintE:
    return SparqlConstraintE(
        select=d["select"],
        prefixes=d.get("prefixes"),
        message=d.get("message"),
        severity=d.get("severity"),
        deactivated=d.get("deactivated"),
    )
