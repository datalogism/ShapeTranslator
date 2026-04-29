"""Canonical schema representation used by the shapespresso metrics layer.

CanonicalProperty / CanonicalShape / CanonicalSchema are language-neutral
dataclasses that act as a common target for both SHACL and ShExJE parsers.
The metrics layer (shapespresso.metrics.classification / similarity) only
depends on this interface, never on SHACL-specific or ShExJE-specific types.

Field conventions
-----------------
- ``path``       — predicate URI string (full IRI)
- ``cardinality`` — ``Cardinality`` with ``min`` normalised to 0 when absent
                    and ``max`` normalised to ``UNBOUNDED`` (-1) when absent.
- ``datatype``   — XSD / custom datatype IRI string, or None
- ``classRef``   — single object-class IRI string (sh:class), or None
- ``classRefOr`` — list of class IRI strings (sh:or of sh:class), or None
- ``nodeKind``   — "IRI", "BlankNode", "Literal", etc., or None
- ``iriStem``    — IRI stem string (ShEx IriStem facet), or None
- ``pattern``    — regex string (sh:pattern / ShEx pattern facet), or None
- ``nodeRef``    — shape-reference IRI (sh:node / ShEx @ShapeName), or None
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shaclex_py.schema.common import Cardinality


@dataclass
class CanonicalProperty:
    """Language-neutral representation of one property constraint."""
    path: str                              # full predicate URI
    cardinality: Cardinality               # normalised min/max
    datatype: Optional[str] = None
    classRef: Optional[str] = None        # single sh:class target
    classRefOr: Optional[list[str]] = None  # multiple sh:class targets (sh:or)
    nodeKind: Optional[str] = None        # "IRI" | "Literal" | "BlankNode" | …
    iriStem: Optional[str] = None
    pattern: Optional[str] = None
    nodeRef: Optional[str] = None         # sh:node / @ShapeName reference


@dataclass
class CanonicalShape:
    """Language-neutral representation of one node/shape."""
    name: str                              # shape IRI or local name
    targetClass: Optional[str] = None     # sh:targetClass / ShEx @<Class>
    properties: list[CanonicalProperty] = field(default_factory=list)


@dataclass
class CanonicalSchema:
    """A collection of CanonicalShape objects."""
    shapes: list[CanonicalShape] = field(default_factory=list)
