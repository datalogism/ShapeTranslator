"""Shared types for SHACL and ShEx models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeKind(Enum):
    IRI = "IRI"
    BLANK_NODE = "BlankNode"
    LITERAL = "Literal"
    BLANK_NODE_OR_IRI = "BlankNodeOrIRI"
    BLANK_NODE_OR_LITERAL = "BlankNodeOrLiteral"
    IRI_OR_LITERAL = "IRIOrLiteral"


UNBOUNDED = -1  # Sentinel for unbounded max cardinality


@dataclass
class Cardinality:
    min: Optional[int] = None   # None = not specified (use language default)
    max: Optional[int] = None   # None = not specified, UNBOUNDED = unlimited

    @property
    def is_default_shacl(self) -> bool:
        """SHACL default: {0,*}"""
        return self.min in (None, 0) and self.max in (None, UNBOUNDED)

    @property
    def is_default_shex(self) -> bool:
        """ShEx default: {1,1}"""
        return self.min in (None, 1) and self.max in (None, 1)

    @property
    def effective_min(self) -> int:
        """Effective min for ShEx (default 1)."""
        return self.min if self.min is not None else 1

    @property
    def effective_max(self) -> Optional[int]:
        """Effective max for ShEx. Returns None for unbounded, int otherwise."""
        if self.max == UNBOUNDED:
            return None  # unbounded
        if self.max is None:
            return 1  # ShEx default
        return self.max

    def to_shex_string(self) -> str:
        mn = self.effective_min
        mx = self.effective_max  # None = unbounded
        if mn == 0 and mx is None:
            return " *"
        if mn == 0 and mx == 1:
            return " ?"
        if mn == 1 and mx is None:
            return " +"
        if mn == 1 and mx == 1:
            return ""
        if mx is None:
            return f" {{{mn},}}"
        if mn == mx:
            return f" {{{mn}}}"
        return f" {{{mn},{mx}}}"


@dataclass
class IRI:
    value: str

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, IRI):
            return self.value == other.value
        return False

    def __repr__(self):
        return f"IRI({self.value!r})"


@dataclass
class Prefix:
    name: str
    iri: str


@dataclass
class Path:
    iri: IRI
    inverse: bool = False


@dataclass
class IriStem:
    """An IRI stem for ShEx value sets, e.g. <http://example.org/~>"""
    stem: str


@dataclass
class Literal:
    value: str
    datatype: Optional[IRI] = None
    language: Optional[str] = None

    def __hash__(self):
        return hash((self.value, self.datatype, self.language))

    def __eq__(self, other):
        if isinstance(other, Literal):
            return (self.value == other.value and
                    self.datatype == other.datatype and
                    self.language == other.language)
        return False
