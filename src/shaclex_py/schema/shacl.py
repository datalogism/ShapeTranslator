"""SHACL data model (NodeShape, PropertyShape, etc.)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from shaclex_py.schema.common import IRI, Cardinality, Literal, NodeKind, Path, Prefix


@dataclass
class PropertyShape:
    path: Path
    datatype: Optional[IRI] = None
    class_: Optional[IRI] = None
    node_kind: Optional[NodeKind] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    pattern: Optional[str] = None
    has_value: Optional[Union[IRI, Literal]] = None
    in_values: Optional[list[Union[IRI, Literal]]] = None
    node: Optional[IRI] = None  # sh:node reference to another shape
    or_constraints: Optional[list[IRI]] = None  # sh:or list of class IRIs
    and_constraints: Optional[list[IRI]] = None
    not_constraint: Optional[IRI] = None

    @property
    def cardinality(self) -> Cardinality:
        return Cardinality(min=self.min_count, max=self.max_count)


@dataclass
class NodeShape:
    iri: IRI
    target_class: Optional[IRI] = None
    properties: list[PropertyShape] = field(default_factory=list)
    closed: bool = False
    ignored_properties: list[IRI] = field(default_factory=list)


@dataclass
class SHACLSchema:
    shapes: list[NodeShape] = field(default_factory=list)
    prefixes: list[Prefix] = field(default_factory=list)
