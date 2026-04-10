"""SHACL → ShexJE direct converter.

ShexJE is the canonical format.  This replaces the two-step
SHACL → CanonicalSchema → ShexJE pipeline with a single direct pass.
"""
from __future__ import annotations

import re
from typing import Optional

from shaclex_py.schema.common import IRI, UNBOUNDED, Literal
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
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

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_UNBOUNDED = -1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _shape_name_from_iri(iri: IRI) -> str:
    """Extract short name from a SHACL shape IRI, stripping the 'Shape' suffix."""
    local = iri.value.rsplit("/", 1)[-1]
    return local[:-5] if local.endswith("Shape") else local


def _is_rdf_type_only_companion(ns: NodeShape) -> bool:
    """True for NodeShapes that are old-format companion value stubs.

    These are shapes with no targetClass whose only properties are
    ``rdf:type`` constraints (sh:hasValue, sh:in, or sh:class).  They were
    emitted by older versions of the converter as a side-effect of the
    value-shape mechanism and must not be re-emitted when reconverting the
    same SHACL.  The companion shapes will be regenerated automatically by
    ``_ensure_value_shape`` when processing the main shape.
    """
    if ns.target_class is not None:
        return False
    if ns.or_datatypes or ns.node_kind or ns.node_datatype or ns.node_in_values or ns.or_property_groups:
        return False
    if not ns.properties:
        return False
    return all(ps.path.iri.value == _RDF_TYPE for ps in ns.properties)


def _pattern_to_iri_stem(pattern: str) -> Optional[str]:
    """Return the stem if *pattern* matches a plain URL-prefix pattern, else None."""
    m = re.match(r'^\^(https?://[^$]*?)/?$', pattern)
    return m.group(1) if m else None


def _shacl_value_to_shexje(val) -> ValueSetEntry:
    """Convert an IRI or Literal to a ShexJE value-set entry."""
    if isinstance(val, IRI):
        return val.value
    if isinstance(val, Literal):
        d: dict = {"value": val.value}
        if val.datatype:
            d["type"] = val.datatype.value
        if val.language:
            d["language"] = val.language
        return d
    return str(val)


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
    """Return (and create if needed) the companion ShapeE id for *class_iris*."""
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


# ── Property conversion ───────────────────────────────────────────────────────

def _ps_to_tc(
    ps: PropertyShape,
    value_shapes: dict[tuple, ShapeE],
    type_predicate: str,
) -> TripleConstraintE:
    """Convert a SHACL PropertyShape to a ShexJE TripleConstraintE."""
    if ps.alternative_paths:
        tc = TripleConstraintE(
            path=AlternativePath(expressions=[p.value for p in ps.alternative_paths])
        )
    else:
        tc = TripleConstraintE(predicate=ps.path.iri.value)

    # Cardinality (SHACL default {0,*}; only emit when non-default)
    mn = ps.min_count if ps.min_count is not None else 0
    mx = ps.max_count if ps.max_count is not None else _UNBOUNDED
    if mn != 0 or mx != _UNBOUNDED:
        tc.min = mn
        tc.max = mx

    node_kind_str = ps.node_kind.value if ps.node_kind else None

    # Primary constraint
    if ps.has_value is not None:
        tc.valueExpr = NodeConstraintE(values=[_shacl_value_to_shexje(ps.has_value)])

    elif ps.in_values is not None:
        tc.valueExpr = NodeConstraintE(
            values=[_shacl_value_to_shexje(v) for v in ps.in_values]
        )

    elif ps.or_constraints:
        class_iris = sorted(c.value for c in ps.or_constraints)
        shape_id = _ensure_value_shape(class_iris, value_shapes, type_predicate)
        if node_kind_str:
            tc.valueExpr = ShapeAndE(
                shapeExprs=[shape_id, NodeConstraintE(nodeKind=node_kind_str)]
            )
        else:
            tc.valueExpr = shape_id

    elif ps.class_:
        shape_id = _ensure_value_shape([ps.class_.value], value_shapes, type_predicate)
        if node_kind_str:
            tc.valueExpr = ShapeAndE(
                shapeExprs=[shape_id, NodeConstraintE(nodeKind=node_kind_str)]
            )
        else:
            tc.valueExpr = shape_id

    elif ps.datatype:
        nc = NodeConstraintE(datatype=ps.datatype.value, nodeKind=node_kind_str)
        if ps.pattern is not None:
            nc.pattern = ps.pattern
        tc.valueExpr = nc

    elif ps.pattern:
        stem = _pattern_to_iri_stem(ps.pattern)
        if stem:
            tc.valueExpr = NodeConstraintE(values=[IriStemValue(stem=stem)])
        else:
            nc = NodeConstraintE(pattern=ps.pattern)
            if node_kind_str:
                nc.nodeKind = node_kind_str
            tc.valueExpr = nc

    elif node_kind_str:
        tc.valueExpr = NodeConstraintE(nodeKind=node_kind_str)

    elif ps.node:
        tc.valueExpr = ShapeRefE(reference=_shape_name_from_iri(ps.node))

    return tc


# ── Main converter ────────────────────────────────────────────────────────────

def convert_shacl_to_shexje(
    shacl: SHACLSchema,
    type_predicate: str = _RDF_TYPE,
) -> ShexJESchema:
    """Convert a SHACL schema directly to a ShexJESchema.

    Args:
        shacl: Parsed SHACL schema.
        type_predicate: IRI used as the class-membership predicate in companion
            value shapes (default: ``rdf:type``).

    Returns:
        Equivalent ShexJE schema.
    """
    value_shapes: dict[tuple, ShapeE] = {}
    shape_decls: list = []

    for ns in shacl.shapes:
        # Skip old-format companion stubs (rdf:type-only shapes without targetClass).
        # These were emitted by earlier converter versions; the companion shapes
        # will be regenerated via _ensure_value_shape when processing main shapes.
        if _is_rdf_type_only_companion(ns):
            continue
        # OR-of-datatypes at NodeShape level → ShapeOrE
        if ns.or_datatypes:
            nc_list = [NodeConstraintE(datatype=dt.value) for dt in ns.or_datatypes]
            shape_decls.append(ShapeOrE(id=_shape_name_from_iri(ns.iri), shapeExprs=nc_list))
            continue

        # Node-level constraints → top-level NodeConstraintE
        if ns.node_kind is not None or ns.node_datatype is not None or ns.node_in_values is not None:
            values = (
                [_shacl_value_to_shexje(v) for v in ns.node_in_values]
                if ns.node_in_values else None
            )
            shape_decls.append(NodeConstraintE(
                id=_shape_name_from_iri(ns.iri),
                nodeKind=ns.node_kind.value if ns.node_kind else None,
                datatype=ns.node_datatype.value if ns.node_datatype else None,
                values=values,
            ))
            continue

        shape_id = _shape_name_from_iri(ns.iri)
        target_class = ns.target_class.value if ns.target_class else None

        # Regular property constraints
        regular_tcs: list[TripleConstraintE] = []
        for ps in ns.properties:
            # Skip rdf:type constraints when targetClass already covers the class.
            # Handles both sh:hasValue and sh:class forms.
            if ps.path.iri.value == _RDF_TYPE and target_class is not None:
                if ps.has_value is not None:
                    continue
                if ps.class_ is not None and ps.class_.value == target_class:
                    continue
            regular_tcs.append(_ps_to_tc(ps, value_shapes, type_predicate))

        # sh:or property-group constraints → EachOfE.alternativeGroups
        group_tcs: list[TripleConstraintE] = []
        alt_groups: Optional[list[list[str]]] = None
        if ns.or_property_groups:
            all_group_preds: list[str] = []
            for group in ns.or_property_groups:
                for ps in group:
                    all_group_preds.append(ps.path.iri.value)
                    group_tcs.append(_ps_to_tc(ps, value_shapes, type_predicate))
            if all_group_preds:
                alt_groups = [all_group_preds]

        all_tcs = regular_tcs + group_tcs
        if not all_tcs:
            expression = None
        elif len(all_tcs) == 1:
            expression = all_tcs[0]
        else:
            expression = EachOfE(expressions=all_tcs, alternativeGroups=alt_groups)

        shape_decls.append(ShapeE(
            id=shape_id,
            closed=ns.closed,
            expression=expression,
            targetClass=target_class,
        ))

    # Append companion value shapes in deterministic order
    for vs in sorted(value_shapes.values(), key=lambda s: s.id):
        shape_decls.append(vs)

    return ShexJESchema(shapes=shape_decls)
