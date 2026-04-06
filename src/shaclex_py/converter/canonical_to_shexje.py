"""Convert a CanonicalSchema to a ShexJESchema.

Mapping strategy
----------------
* Each :class:`CanonicalShape` becomes a :class:`ShapeE`.
* ``datatypeOr`` shapes become a :class:`ShapeOrE` (top-level shape declaration).
* Each :class:`CanonicalProperty` becomes a :class:`TripleConstraintE`.
* All constraint fields are mapped to proper ShexJ ``valueExpr`` forms:

  +--------------+-------------------------------------------------------+
  | Canonical    | ShexJE (TripleConstraintE)                            |
  +==============+=======================================================+
  | datatype     | valueExpr: NodeConstraintE(datatype=…)                |
  +--------------+-------------------------------------------------------+
  | classRef     | valueExpr: "<ShapeId>" (string ref) + ShapeE added    |
  |              | to schema with predicate/values shorthand             |
  +--------------+-------------------------------------------------------+
  | classRefOr   | valueExpr: "<ShapeId>" (string ref) + ShapeE with     |
  |              | multiple values in predicate/values shorthand         |
  +--------------+-------------------------------------------------------+
  | nodeKind     | valueExpr: NodeConstraintE(nodeKind=…)                |
  +--------------+-------------------------------------------------------+
  | hasValue     | valueExpr: NodeConstraintE(values=[value])            |
  +--------------+-------------------------------------------------------+
  | inValues     | valueExpr: NodeConstraintE(values=[…])                |
  +--------------+-------------------------------------------------------+
  | iriStem      | valueExpr: NodeConstraintE(values=[IriStemValue(…)])  |
  +--------------+-------------------------------------------------------+
  | nodeRef      | valueExpr: ShapeRefE(reference=…)                    |
  +--------------+-------------------------------------------------------+
  | pattern      | added to NodeConstraintE alongside primary constraint |
  +--------------+-------------------------------------------------------+
  | cardinality  | min / max on TripleConstraintE                        |
  +--------------+-------------------------------------------------------+

Value shapes for classRef / classRefOr
---------------------------------------
When a property points to a class-constrained node, a companion ``ShapeE``
(the "value shape") is generated and added once to the schema:

.. code-block:: json

    {
      "type": "Shape",
      "id": "Country",
      "extra": ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"],
      "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      "values": ["http://dbpedia.org/ontology/Country"]
    }

The shape ID is derived from the local name(s) of the class IRI(s).  Multiple
properties referencing the same class share one value shape.

The type predicate defaults to ``rdf:type``; Wikidata datasets should override
this to ``wdt:P31`` (pass ``type_predicate`` to the converter).
"""
from __future__ import annotations

from typing import Optional

from shaclex_py.schema.canonical import CanonicalProperty, CanonicalSchema, CanonicalShape
from shaclex_py.schema.shexje import (
    AlternativePath,
    EachOfE,
    IriStemValue,
    NodeConstraintE,
    ShapeAndE,
    ShapeE,
    ShapeOrE,
    ShapeRefE,
    ShexJESchema,
    TripleConstraintE,
    ValueSetEntry,
)

_UNBOUNDED = -1
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def convert_canonical_to_shexje(
    canonical: CanonicalSchema,
    type_predicate: str = _RDF_TYPE,
) -> ShexJESchema:
    """Convert *canonical* to a :class:`ShexJESchema`.

    Args:
        canonical: Source :class:`CanonicalSchema`.
        type_predicate: IRI of the predicate used to assert class membership
            in generated value shapes (default: ``rdf:type``).  For Wikidata
            datasets use ``http://www.wikidata.org/prop/direct/P31``.

    Returns:
        Equivalent :class:`ShexJESchema`.
    """
    # Maps (frozenset-of-class-IRIs) → ShapeE for deduplication
    value_shapes: dict[tuple, ShapeE] = {}

    shape_decls: list = []

    for cs in canonical.shapes:
        if cs.datatypeOr:
            # DBpedia-style value shape: OR of NodeConstraints
            shape_decls.append(_make_datatype_or_shape(cs))
        elif cs.nodeKind is not None or cs.datatype is not None or cs.inValues is not None:
            # Node-level constraint shape → top-level NodeConstraintE
            shape_decls.append(_make_node_constraint_shape(cs))
        else:
            shape_decls.append(
                _make_shape(cs, value_shapes, type_predicate)
            )

    # Append collected value shapes (in deterministic order)
    for vs in _ordered_value_shapes(value_shapes):
        shape_decls.append(vs)

    return ShexJESchema(shapes=shape_decls)


# ── Shape helpers ─────────────────────────────────────────────────────────────

def _make_shape(
    cs: CanonicalShape,
    value_shapes: dict[tuple, ShapeE],
    type_predicate: str,
) -> ShapeE:
    tcs = [
        _make_triple_constraint(cp, value_shapes, type_predicate)
        for cp in cs.properties
    ]

    if len(tcs) == 1:
        expression = tcs[0]
    elif len(tcs) > 1:
        expression = EachOfE(
            expressions=tcs,
            alternativeGroups=cs.property_alternative_groups,
        )
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


def _make_node_constraint_shape(cs: CanonicalShape) -> NodeConstraintE:
    """Map node-level constraints to a top-level ``NodeConstraint``."""
    values = None
    if cs.inValues is not None:
        values = [_canonical_value_to_shexje(v) for v in cs.inValues]
    return NodeConstraintE(
        id=cs.name,
        nodeKind=cs.nodeKind,
        datatype=cs.datatype,
        values=values,
    )


def _canonical_value_to_shexje(v) -> object:
    """Convert a canonical value (str or dict) to a ShexJE value-set entry."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v
    return str(v)


# ── Property helpers ──────────────────────────────────────────────────────────

def _make_triple_constraint(
    cp: CanonicalProperty,
    value_shapes: dict[tuple, ShapeE],
    type_predicate: str,
) -> TripleConstraintE:
    if cp.pathAlternatives is not None:
        tc = TripleConstraintE(path=AlternativePath(expressions=list(cp.pathAlternatives)))
    else:
        tc = TripleConstraintE(predicate=cp.path)

    # Cardinality
    mn = cp.cardinality.min
    mx = cp.cardinality.max
    if mn != 0 or mx != _UNBOUNDED:
        tc.min = mn
        tc.max = mx

    # Primary constraint → always expressed via valueExpr
    if cp.datatype is not None:
        # Companion nodeKind (e.g. sh:Literal) is included in the same NodeConstraint
        nc = NodeConstraintE(datatype=cp.datatype, nodeKind=cp.nodeKind)
        if cp.pattern is not None:
            nc.pattern = cp.pattern
        tc.valueExpr = nc

    elif cp.classRef is not None:
        shape_id = _ensure_value_shape(
            [cp.classRef], value_shapes, type_predicate
        )
        if cp.nodeKind is not None:
            # Combine shape reference with companion nodeKind via ShapeAnd
            tc.valueExpr = ShapeAndE(shapeExprs=[shape_id, NodeConstraintE(nodeKind=cp.nodeKind)])
        else:
            tc.valueExpr = shape_id   # string reference

    elif cp.classRefOr is not None:
        shape_id = _ensure_value_shape(
            sorted(cp.classRefOr), value_shapes, type_predicate
        )
        if cp.nodeKind is not None:
            tc.valueExpr = ShapeAndE(shapeExprs=[shape_id, NodeConstraintE(nodeKind=cp.nodeKind)])
        else:
            tc.valueExpr = shape_id   # string reference

    elif cp.nodeKind is not None:
        nc = NodeConstraintE(nodeKind=cp.nodeKind)
        if cp.pattern is not None:
            nc.pattern = cp.pattern
        tc.valueExpr = nc

    elif cp.hasValue is not None:
        tc.valueExpr = NodeConstraintE(values=[cp.hasValue])

    elif cp.inValues is not None:
        tc.valueExpr = NodeConstraintE(
            values=_canonical_values_to_shexje(cp.inValues)
        )

    elif cp.iriStem is not None:
        tc.valueExpr = NodeConstraintE(
            values=[IriStemValue(stem=cp.iriStem)]
        )

    elif cp.nodeRef is not None:
        # Use ShapeRefE to preserve the full IRI on round-trip
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
            result.append(v)
        else:
            result.append(str(v))
    return result


# ── Value-shape registry ──────────────────────────────────────────────────────

def _ensure_value_shape(
    class_iris: list[str],
    value_shapes: dict[tuple, ShapeE],
    type_predicate: str,
) -> str:
    """Return the shape ID for the given class IRI(s), creating the shape if new.

    The ``value_shapes`` dict maps a sorted tuple of class IRIs to the
    corresponding :class:`ShapeE`, ensuring deduplication across the schema.
    """
    key = tuple(sorted(class_iris))
    if key not in value_shapes:
        shape_id = _derive_shape_id(class_iris)
        value_shapes[key] = ShapeE(
            id=shape_id,
            extra=[type_predicate],
            predicate=type_predicate,
            values=list(class_iris),
        )
    return value_shapes[key].id


def _derive_shape_id(class_iris: list[str]) -> str:
    """Derive a short shape ID from one or more class IRIs.

    Uses the local name (part after the last ``/`` or ``#``) of each IRI,
    joined with ``"Or"`` for multi-class OR shapes.

    Examples::

        ["http://dbpedia.org/ontology/Country"]
            → "Country"
        ["http://dbpedia.org/ontology/AcademicSubject",
         "http://dbpedia.org/ontology/MedicalSpecialty"]
            → "AcademicSubjectOrMedicalSpecialty"
    """
    local_names = [_local_name(iri) for iri in sorted(class_iris)]
    return "Or".join(local_names)


def _local_name(iri: str) -> str:
    """Return the local name of an IRI (part after the last '/' or '#')."""
    for sep in ("#", "/"):
        idx = iri.rfind(sep)
        if idx != -1:
            return iri[idx + 1:]
    return iri


def _ordered_value_shapes(value_shapes: dict[tuple, ShapeE]) -> list[ShapeE]:
    """Return value shapes sorted deterministically by shape ID."""
    return sorted(value_shapes.values(), key=lambda s: s.id)
