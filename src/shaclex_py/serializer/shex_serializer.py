"""Serialize ShEx model to ShExC compact syntax.

Pass ``label_map`` to ``serialize_shex`` to enable Wikidata-friendly output:

* Shape references use human-readable labels (``@<Human>``, not ``@<Q5>``).
* Every triple constraint gets an aligned ``# property label`` comment.
* Auxiliary shapes get ``# type1, type2`` comments from QID labels.
* WikibaseItem properties and literal/IRI properties are separated by
  section-header comments (``# WikibaseItem property`` etc.).

``label_map`` is a plain ``dict[str, str]`` mapping full Wikidata IRIs to
their English labels.  Build one with
:func:`shaclex_py.utils.wikidata.fetch_labels`.
"""
from __future__ import annotations

from typing import Optional, Union

from shaclex_py.schema.common import IRI, UNBOUNDED, IriStem, Literal, NodeKind
from shaclex_py.schema.shex import (
    EachOf,
    NodeConstraint,
    NodeConstraintShape,
    OneOf,
    Shape,
    ShapeRef,
    ShExSchema,
    TripleConstraint,
    ValueSetValue,
)

# Column at which ``#`` starts in aligned comments (1-indexed: column 43).
_COMMENT_COL = 42

# IRIs considered "instance-of" predicates — used to detect auxiliary shapes.
_INSTANCE_OF = {
    "http://www.wikidata.org/prop/direct/P31",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
}


# ── PrefixMap ────────────────────────────────────────────────────────────────

class PrefixMap:
    """Manages IRI-to-prefixed-name resolution."""

    def __init__(self, prefixes: list):
        # Sort by longest IRI first to get most specific match
        self.entries = sorted(
            [(p.name, p.iri) for p in prefixes],
            key=lambda x: -len(x[1]),
        )

    def compact(self, iri: str) -> str:
        """Try to compact a full IRI to a prefixed name."""
        for name, prefix_iri in self.entries:
            if iri.startswith(prefix_iri):
                local = iri[len(prefix_iri):]
                return f"{name}:{local}" if name else f":{local}"
        return f"<{iri}>"

    def compact_iri(self, iri: IRI) -> str:
        return self.compact(iri.value)


# ── Low-level serialisation helpers ─────────────────────────────────────────

def _serialize_cardinality(card) -> str:
    return card.to_shex_string()


def _serialize_value_set_value(v: ValueSetValue, pm: PrefixMap) -> str:
    val = v.value
    if isinstance(val, IriStem):
        return f"<{val.stem}>~"
    if isinstance(val, IRI):
        return pm.compact_iri(val)
    if isinstance(val, Literal):
        s = f'"{val.value}"'
        if val.datatype:
            s += f"^^{pm.compact_iri(val.datatype)}"
        elif val.language:
            s += f"@{val.language}"
        return s
    return str(val)


def _serialize_pattern_facet(pattern: str) -> str:
    """Serialize a regex pattern as a ShExC pattern facet /regex/."""
    escaped = pattern.replace("\\", "\\\\").replace("/", "\\/")
    return f" /{escaped}/"


def _serialize_node_constraint(nc: NodeConstraint, pm: PrefixMap) -> str:
    if nc.values is not None:
        items = " ".join(_serialize_value_set_value(v, pm) for v in nc.values)
        return f"[ {items} ]"
    if nc.node_kind is not None:
        kind_map = {
            NodeKind.IRI: "IRI",
            NodeKind.LITERAL: "LITERAL",
            NodeKind.BLANK_NODE: "BNODE",
            NodeKind.BLANK_NODE_OR_IRI: "NONLITERAL",
        }
        base = kind_map.get(nc.node_kind, ".")
        if nc.pattern:
            base += _serialize_pattern_facet(nc.pattern)
        return base
    if nc.datatype is not None:
        base = pm.compact_iri(nc.datatype)
        if nc.pattern:
            base += _serialize_pattern_facet(nc.pattern)
        return base
    if nc.pattern is not None:
        return "." + _serialize_pattern_facet(nc.pattern)
    return "."


def _serialize_constraint(
    constraint: Union[NodeConstraint, ShapeRef, None], pm: PrefixMap
) -> str:
    if constraint is None:
        return "."
    if isinstance(constraint, ShapeRef):
        return f"@<{constraint.name.value}>"
    if isinstance(constraint, NodeConstraint):
        return _serialize_node_constraint(constraint, pm)
    return "."


def _serialize_triple_constraint(tc: TripleConstraint, pm: PrefixMap) -> str:
    """Serialize a single triple constraint (no comment, no trailing `;`)."""
    pred = pm.compact_iri(tc.predicate)
    constraint_str = _serialize_constraint(tc.constraint, pm)
    card_str = _serialize_cardinality(tc.cardinality)
    return f"  {pred} {constraint_str}{card_str}"


# ── Expression serialisation (no label_map — plain mode) ────────────────────

def _serialize_expression(
    expr: Union[EachOf, OneOf, TripleConstraint, None], pm: PrefixMap
) -> str:
    """Serialize a triple expression (plain, no comments)."""
    if expr is None:
        return ""
    if isinstance(expr, TripleConstraint):
        return _serialize_triple_constraint(expr, pm)
    if isinstance(expr, EachOf):
        return " ;\n".join(
            _serialize_expression(sub, pm) for sub in expr.expressions
        )
    if isinstance(expr, OneOf):
        return " |\n".join(
            _serialize_expression(sub, pm) for sub in expr.expressions
        )
    return ""


# ── Wikidata label-aware serialisation ──────────────────────────────────────

def _is_wikidata_schema(schema: ShExSchema) -> bool:
    """True if the schema has a ``wdt:`` prefix pointing to Wikidata."""
    for pfx in schema.prefixes:
        if pfx.name == "wdt" and "wikidata.org" in pfx.iri:
            return True
    return False


def _is_auxiliary_shape(shape) -> bool:
    """True if the shape contains only a single (instance-of) triple constraint."""
    if isinstance(shape, NodeConstraintShape):
        return True
    expr = shape.expression
    if expr is None:
        return True
    if isinstance(expr, TripleConstraint):
        return True
    if isinstance(expr, EachOf):
        return len(expr.expressions) <= 1
    return False


def _flat_tcs(expr) -> list[TripleConstraint]:
    """Flatten an expression to a list of TripleConstraints."""
    if expr is None:
        return []
    if isinstance(expr, TripleConstraint):
        return [expr]
    if isinstance(expr, (EachOf, OneOf)):
        result = []
        for sub in expr.expressions:
            result.extend(_flat_tcs(sub))
        return result
    return []


def _is_wikibase_item_tc(tc: TripleConstraint) -> bool:
    """True if the constraint references another item (shape-ref or wd: value set)."""
    if isinstance(tc.constraint, ShapeRef):
        return True
    if isinstance(tc.constraint, NodeConstraint) and tc.constraint.values:
        for v in tc.constraint.values:
            if isinstance(v.value, IRI) and "wikidata.org/entity/Q" in v.value.value:
                return True
    return False


def _add_comment(line: str, comment: str) -> str:
    """Pad *line* to _COMMENT_COL and append ``# comment``."""
    if not comment:
        return line
    pad = max(2, _COMMENT_COL - len(line))
    return f"{line}{' ' * pad}# {comment}"


def _tc_comment(
    tc: TripleConstraint,
    label_map: dict[str, str],
    is_auxiliary: bool,
) -> str:
    """Return the inline comment for one triple constraint.

    * Auxiliary shapes (single P31/rdf:type constraint): list QID labels
      separated by commas — e.g. ``"organization, research project"``.
    * Main shapes: always the property label — e.g. ``"instance of"``.
    """
    prop_label = label_map.get(tc.predicate.value, "")

    if is_auxiliary and tc.predicate.value in _INSTANCE_OF:
        if isinstance(tc.constraint, NodeConstraint) and tc.constraint.values:
            qid_labels = [
                label_map.get(v.value.value, "")
                for v in tc.constraint.values
                if isinstance(v.value, IRI)
            ]
            qid_labels = [l for l in qid_labels if l]
            if qid_labels:
                return ", ".join(qid_labels)

    return prop_label


def _format_tc_line(
    tc: TripleConstraint,
    pm: PrefixMap,
    label_map: Optional[dict[str, str]],
    trailing_semi: bool,
    is_auxiliary: bool,
) -> str:
    """Format one triple constraint line, adding ``;`` and ``# comment`` as needed."""
    base = _serialize_triple_constraint(tc, pm)
    if trailing_semi:
        base += " ;"

    if label_map:
        comment = _tc_comment(tc, label_map, is_auxiliary)
        return _add_comment(base, comment)
    return base


def _serialize_expression_with_labels(
    expr,
    pm: PrefixMap,
    label_map: dict[str, str],
    is_auxiliary: bool,
    is_wikidata: bool,
) -> str:
    """Serialize an expression with aligned comments and optional section headers.

    For Wikidata main shapes, WikibaseItem properties and literal/IRI properties
    are separated by ``# WikibaseItem property`` / ``# URL, String, Quantity,
    Time property`` section comments, matching the WES ShEx format.
    """
    tcs = _flat_tcs(expr)
    if not tcs:
        return ""

    if is_auxiliary or not is_wikidata:
        # Simple case: just format each TC with comments, no section headers.
        lines = []
        for i, tc in enumerate(tcs):
            trailing = (i < len(tcs) - 1)
            lines.append(_format_tc_line(tc, pm, label_map, trailing, is_auxiliary))
        return "\n".join(lines)

    # Wikidata main shape: group into WikibaseItem vs literal/IRI sections.
    wikibase = [tc for tc in tcs if _is_wikibase_item_tc(tc)]
    other    = [tc for tc in tcs if not _is_wikibase_item_tc(tc)]

    lines: list[str] = []

    if wikibase:
        lines.append("  # WikibaseItem property")
        for i, tc in enumerate(wikibase):
            trailing = (i < len(wikibase) - 1) or bool(other)
            lines.append(_format_tc_line(tc, pm, label_map, trailing, False))

    if other:
        if wikibase:
            lines.append("")
        lines.append("  # URL, String, Quantity, Time property")
        for i, tc in enumerate(other):
            trailing = (i < len(other) - 1)
            lines.append(_format_tc_line(tc, pm, label_map, trailing, False))

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────────────

def serialize_shex(
    schema: ShExSchema,
    label_map: Optional[dict[str, str]] = None,
) -> str:
    """Serialize a :class:`ShExSchema` to ShExC compact syntax.

    Args:
        schema:    The ShEx schema to serialize.
        label_map: Optional mapping of Wikidata IRI → English label.  When
                   provided **and** the schema uses ``wdt:`` prefixes, the
                   output will include aligned ``# comments`` for every triple
                   constraint and section-header comments separating
                   WikibaseItem from literal/IRI properties.  Build this map
                   with :func:`shaclex_py.utils.wikidata.fetch_labels`.
                   Pass ``None`` (default) for plain output without labels.

    Returns:
        ShExC string.
    """
    pm = PrefixMap(schema.prefixes)
    use_labels = label_map is not None
    is_wikidata = use_labels and _is_wikidata_schema(schema)

    lines: list[str] = []

    # PREFIX declarations
    for pfx in schema.prefixes:
        lines.append(f"PREFIX {pfx.name}: <{pfx.iri}>")
    if schema.prefixes:
        lines.append("")

    # start declaration
    if schema.start:
        lines.append(f"start = @<{schema.start.value}>")
        lines.append("")

    # Shape definitions
    for shape in schema.shapes:
        # NodeConstraintShape: OR-of-datatypes, serialized as `<Name> D1 OR D2 OR ...`
        if isinstance(shape, NodeConstraintShape):
            if shape.datatypes:
                parts = " OR ".join(pm.compact_iri(dt) for dt in shape.datatypes)
                lines.append(f"<{shape.name.value}> {parts}")
            else:
                lines.append(f"<{shape.name.value}> .")
            lines.append("")
            continue

        header = f"<{shape.name.value}>"

        modifiers: list[str] = []
        if shape.extra:
            extras = " ".join(pm.compact_iri(e) for e in shape.extra)
            modifiers.append(f"EXTRA {extras}")
        if shape.closed:
            modifiers.append("CLOSED")
        modifier_str = " ".join(modifiers)
        if modifier_str:
            header += f" {modifier_str}"

        if use_labels:
            is_aux = _is_auxiliary_shape(shape)
            body = _serialize_expression_with_labels(
                shape.expression, pm, label_map, is_aux, is_wikidata
            )
        else:
            body = _serialize_expression(shape.expression, pm)

        if body:
            lines.append(f"{header} {{")
            lines.append(body)
            lines.append("}")
        else:
            lines.append(f"{header} {{}}")
        lines.append("")

    return "\n".join(lines)


def serialize_shex_to_file(
    schema: ShExSchema,
    filepath: str,
    label_map: Optional[dict[str, str]] = None,
) -> None:
    """Serialize a :class:`ShExSchema` to a ShExC file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(serialize_shex(schema, label_map=label_map))
