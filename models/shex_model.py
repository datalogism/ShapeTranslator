"""ShEx data model (Shape, TripleConstraint, NodeConstraint, etc.)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from models.common import IRI, Cardinality, IriStem, Literal, NodeKind, Prefix


@dataclass
class ValueSetValue:
    """A single value in a ShEx value set: can be IRI, Literal, or IriStem."""
    value: Union[IRI, Literal, IriStem]


@dataclass
class NodeConstraint:
    datatype: Optional[IRI] = None
    node_kind: Optional[NodeKind] = None
    values: Optional[list[ValueSetValue]] = None  # value set [v1 v2 ...]
    pattern: Optional[str] = None  # string facet
    min_length: Optional[int] = None
    max_length: Optional[int] = None


@dataclass
class ShapeRef:
    """Reference to another shape: @<ShapeName>"""
    name: IRI


@dataclass
class TripleConstraint:
    predicate: IRI
    constraint: Optional[Union[NodeConstraint, ShapeRef]] = None
    cardinality: Cardinality = field(default_factory=Cardinality)
    inverse: bool = False


@dataclass
class EachOf:
    """Conjunction of triple expressions (;-separated in ShExC)."""
    expressions: list[Union[TripleConstraint, EachOf, OneOf]] = field(
        default_factory=list
    )


@dataclass
class OneOf:
    """Disjunction of triple expressions (|-separated in ShExC)."""
    expressions: list[Union[TripleConstraint, EachOf, OneOf]] = field(
        default_factory=list
    )


@dataclass
class Shape:
    name: IRI
    expression: Optional[Union[EachOf, OneOf, TripleConstraint]] = None
    closed: bool = False
    extra: list[IRI] = field(default_factory=list)  # EXTRA predicates
    extends: list[IRI] = field(default_factory=list)


@dataclass
class ShExSchema:
    shapes: list[Shape] = field(default_factory=list)
    prefixes: list[Prefix] = field(default_factory=list)
    start: Optional[IRI] = None  # start = @<Shape>
