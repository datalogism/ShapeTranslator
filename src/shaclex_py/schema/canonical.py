"""Canonical JSON intermediate representation for SHACL/ShEx shapes.

Language-neutral dataclasses that produce deterministic, sorted JSON output_old.
Semantically equivalent SHACL and ShEx shapes produce identical canonical JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class CanonicalCardinality:
    min: int
    max: int  # -1 = unbounded

    def to_dict(self) -> dict:
        return {"min": self.min, "max": self.max}


@dataclass
class CanonicalProperty:
    path: str

    # Constraint fields (mutually exclusive)
    datatype: Optional[str] = None
    classRef: Optional[str] = None
    classRefOr: Optional[list[str]] = None  # sorted list of class IRIs
    nodeKind: Optional[str] = None
    hasValue: Optional[Union[str, dict]] = None
    inValues: Optional[list[Union[str, dict]]] = None  # sorted
    iriStem: Optional[str] = None
    pattern: Optional[str] = None
    nodeRef: Optional[str] = None
    # sh:alternativePath: first path stored in `path`, full list here
    pathAlternatives: Optional[list[str]] = None

    cardinality: CanonicalCardinality = field(
        default_factory=lambda: CanonicalCardinality(0, -1)
    )

    def to_dict(self) -> dict:
        d: dict = {"path": self.path}
        if self.pathAlternatives is not None:
            d["pathAlternatives"] = self.pathAlternatives

        if self.datatype is not None:
            d["datatype"] = self.datatype
        elif self.classRef is not None:
            d["classRef"] = self.classRef
        elif self.classRefOr is not None:
            d["classRefOr"] = sorted(self.classRefOr)
        elif self.nodeKind is not None:
            d["nodeKind"] = self.nodeKind
        elif self.hasValue is not None:
            d["hasValue"] = self.hasValue
        elif self.inValues is not None:
            d["inValues"] = sorted(
                self.inValues,
                key=lambda v: v if isinstance(v, str) else str(v),
            )
        elif self.iriStem is not None:
            d["iriStem"] = self.iriStem
        elif self.nodeRef is not None:
            d["nodeRef"] = self.nodeRef

        # pattern is output_old independently: it can accompany a primary constraint
        if self.pattern is not None:
            d["pattern"] = self.pattern

        d["cardinality"] = self.cardinality.to_dict()
        return d


@dataclass
class CanonicalShape:
    name: str
    targetClass: Optional[str] = None
    closed: bool = False
    properties: list[CanonicalProperty] = field(default_factory=list)
    # OR-of-datatypes at NodeShape level (DBpedia named value shapes)
    datatypeOr: Optional[list[str]] = None
    # Node-level constraints (reusable value shapes, e.g. LangStringShape, TimeZoneShape)
    nodeKind: Optional[str] = None          # sh:nodeKind at NodeShape level
    datatype: Optional[str] = None          # sh:datatype at NodeShape level
    inValues: Optional[list] = None         # sh:in at NodeShape level
    # sh:or with sh:property groups — groups of mutually exclusive predicate URIs.
    # Each inner list is one alternative group; properties remain in ``properties`` (flattened).
    property_alternative_groups: Optional[list[list[str]]] = None

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.targetClass is not None:
            d["targetClass"] = self.targetClass
        d["closed"] = self.closed
        if self.datatypeOr is not None:
            d["datatypeOr"] = self.datatypeOr
        if self.nodeKind is not None:
            d["nodeKind"] = self.nodeKind
        if self.datatype is not None:
            d["datatype"] = self.datatype
        if self.inValues is not None:
            d["inValues"] = sorted(
                self.inValues,
                key=lambda v: v if isinstance(v, str) else str(v),
            )
        d["properties"] = sorted(
            [p.to_dict() for p in self.properties],
            key=lambda p: (p["path"], str(sorted(p.items()))),
        )
        return d


@dataclass
class CanonicalSchema:
    shapes: list[CanonicalShape] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "shapes": sorted(
                [s.to_dict() for s in self.shapes],
                key=lambda s: s["name"],
            )
        }
