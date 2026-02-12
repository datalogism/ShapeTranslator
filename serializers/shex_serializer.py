"""Serialize ShEx model to ShExC compact syntax."""
from __future__ import annotations

from typing import Union

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


class PrefixMap:
    """Manages IRI-to-prefixed-name resolution."""

    def __init__(self, prefixes: list):
        # Sort by longest IRI first to get most specific match
        self.entries = sorted(
            [(p.name, p.iri) for p in prefixes],
            key=lambda x: -len(x[1]),
        )

    def compact(self, iri: str) -> str:
        """Try to compact a full IRI to prefixed name."""
        for name, prefix_iri in self.entries:
            if iri.startswith(prefix_iri):
                local = iri[len(prefix_iri):]
                if name:
                    return f"{name}:{local}"
                else:
                    return f":{local}"
        return f"<{iri}>"

    def compact_iri(self, iri: IRI) -> str:
        return self.compact(iri.value)


def _serialize_cardinality(card) -> str:
    """Serialize cardinality to ShExC notation."""
    return card.to_shex_string()


def _serialize_value_set_value(v: ValueSetValue, pm: PrefixMap) -> str:
    """Serialize a single value set entry."""
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


def _serialize_node_constraint(nc: NodeConstraint, pm: PrefixMap) -> str:
    """Serialize a node constraint."""
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
        return kind_map.get(nc.node_kind, ".")

    if nc.datatype is not None:
        return pm.compact_iri(nc.datatype)

    return "."


def _serialize_constraint(
    constraint: Union[NodeConstraint, ShapeRef, None], pm: PrefixMap
) -> str:
    if constraint is None:
        return "."
    if isinstance(constraint, ShapeRef):
        name = constraint.name.value
        return f"@<{name}>"
    if isinstance(constraint, NodeConstraint):
        return _serialize_node_constraint(constraint, pm)
    return "."


def _serialize_triple_constraint(tc: TripleConstraint, pm: PrefixMap) -> str:
    """Serialize a single triple constraint."""
    pred = pm.compact_iri(tc.predicate)
    constraint_str = _serialize_constraint(tc.constraint, pm)
    card_str = _serialize_cardinality(tc.cardinality)
    return f"  {pred} {constraint_str}{card_str}"


def _serialize_expression(
    expr: Union[EachOf, OneOf, TripleConstraint, None], pm: PrefixMap
) -> str:
    """Serialize a triple expression."""
    if expr is None:
        return ""

    if isinstance(expr, TripleConstraint):
        return _serialize_triple_constraint(expr, pm)

    if isinstance(expr, EachOf):
        lines = []
        for sub in expr.expressions:
            lines.append(_serialize_expression(sub, pm))
        return " ;\n".join(lines)

    if isinstance(expr, OneOf):
        lines = []
        for sub in expr.expressions:
            lines.append(_serialize_expression(sub, pm))
        return " |\n".join(lines)

    return ""


def serialize_shex(schema: ShExSchema) -> str:
    """Serialize a ShExSchema to ShExC compact syntax string.

    Args:
        schema: The ShEx schema to serialize.

    Returns:
        ShExC format string.
    """
    pm = PrefixMap(schema.prefixes)
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
        header = f"<{shape.name.value}>"

        modifiers = []
        if shape.extra:
            extras = " ".join(pm.compact_iri(e) for e in shape.extra)
            modifiers.append(f"EXTRA {extras}")
        if shape.closed:
            modifiers.append("CLOSED")

        modifier_str = " ".join(modifiers)
        if modifier_str:
            header += f" {modifier_str}"

        body = _serialize_expression(shape.expression, pm)
        if body:
            lines.append(f"{header} {{")
            lines.append(body)
            lines.append("}")
        else:
            lines.append(f"{header} {{}}")
        lines.append("")

    return "\n".join(lines)


def serialize_shex_to_file(schema: ShExSchema, filepath: str):
    """Serialize a ShExSchema to a ShExC file."""
    shexc = serialize_shex(schema)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(shexc)
