"""Canonical JSON intermediate representation for SHACL/ShEx shapes.

Language-neutral dataclasses that produce deterministic, sorted JSON output.
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

    cardinality: CanonicalCardinality = field(
        default_factory=lambda: CanonicalCardinality(0, -1)
    )

    def to_dict(self) -> dict:
        d: dict = {"path": self.path}

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
        elif self.pattern is not None:
            d["pattern"] = self.pattern
        elif self.nodeRef is not None:
            d["nodeRef"] = self.nodeRef

        d["cardinality"] = self.cardinality.to_dict()
        return d


@dataclass
class CanonicalShape:
    name: str
    targetClass: Optional[str] = None
    closed: bool = False
    properties: list[CanonicalProperty] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.targetClass is not None:
            d["targetClass"] = self.targetClass
        d["closed"] = self.closed
        d["properties"] = sorted(
            [p.to_dict() for p in self.properties],
            key=lambda p: p["path"],
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
