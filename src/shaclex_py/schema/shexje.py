"""ShexJE (ShEx JSON Extended) data model.

ShexJE is a proper superset of the W3C ShexJ format (JSON encoding of ShEx)
extended with full SHACL compatibility.  It serves as the new canonical
interchange format for this library.

Design principles
-----------------
* **ShexJ backward-compatible**: every valid ShexJ document is valid ShexJE.
* **SHACL-complete**: every SHACL feature can be expressed in ShexJE.
* **Canonical-JSON compatible**: the existing simplified canonical JSON
  constructs (classRef, iriStem, hasValue, …) are supported as first-class
  shorthand fields on TripleConstraintE.
* Same ``"type"`` discriminator pattern as ShexJ.
* Compact IRI strings (``"ex:foo"``) or full IRIs everywhere.

Type hierarchy
--------------
Schema
  shapes: list of ShapeDecl
    ShapeE          – main shape (extends ShexJ Shape)
    NodeConstraintE – node-level constraint (extends ShexJ NodeConstraint)
    ShapeOrE        – logical OR  (mirrors ShexJ ShapeOr)
    ShapeAndE       – logical AND (mirrors ShexJ ShapeAnd)
    ShapeNotE       – negation    (mirrors ShexJ ShapeNot)
    ShapeXoneE      – exclusive-OR (new; SHACL sh:xone)

TripleExpression
  TripleConstraintE – extends ShexJ TripleConstraint with SHACL extras
  EachOfE           – conjunction  (; in ShExC)
  OneOfE            – disjunction  (| in ShExC)

PropertyPath (new in ShexJE for SHACL SPARQL-path support)
  InversePath | SequencePath | AlternativePath
  ZeroOrMorePath | OneOrMorePath | ZeroOrOnePath
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union


# ── Value-set entries (mirrors ShexJ) ─────────────────────────────────────────

@dataclass
class IriStemValue:
    """``{"type": "IriStem", "stem": "..."}``"""
    stem: str

    def to_dict(self) -> dict:
        return {"type": "IriStem", "stem": self.stem}


@dataclass
class LiteralValue:
    """Typed or language-tagged literal in a value set."""
    value: str
    datatype: Optional[str] = None   # datatype IRI (compact or full)
    language: Optional[str] = None

    def to_dict(self) -> Any:
        if self.datatype is None and self.language is None:
            return self.value          # plain-string short form
        d: dict = {"value": self.value}
        if self.datatype is not None:
            d["type"] = self.datatype
        if self.language is not None:
            d["language"] = self.language
        return d


# A value-set entry: plain IRI string, LiteralValue, IriStemValue,
# or a raw dict for advanced stem-range types (pass-through).
ValueSetEntry = Union[str, LiteralValue, IriStemValue, dict]


# ── Property Paths (new in ShexJE) ─────────────────────────────────────────────

@dataclass
class InversePath:
    """Inverse property path (SHACL sh:inversePath / SPARQL ``^p``)."""
    expression: Union[str, "PropertyPath"]

    def to_dict(self) -> dict:
        expr = self.expression if isinstance(self.expression, str) else self.expression.to_dict()
        return {"type": "InversePath", "expression": expr}


@dataclass
class SequencePath:
    """Sequence of property paths (SPARQL ``p1/p2``)."""
    expressions: list[Union[str, "PropertyPath"]]

    def to_dict(self) -> dict:
        return {
            "type": "SequencePath",
            "expressions": [
                e if isinstance(e, str) else e.to_dict() for e in self.expressions
            ],
        }


@dataclass
class AlternativePath:
    """Alternative property paths (SHACL sh:alternativePath / SPARQL ``p1|p2``)."""
    expressions: list[Union[str, "PropertyPath"]]

    def to_dict(self) -> dict:
        return {
            "type": "AlternativePath",
            "expressions": [
                e if isinstance(e, str) else e.to_dict() for e in self.expressions
            ],
        }


@dataclass
class ZeroOrMorePath:
    """Zero-or-more repetition (sh:zeroOrMorePath / SPARQL ``p*``)."""
    expression: Union[str, "PropertyPath"]

    def to_dict(self) -> dict:
        expr = self.expression if isinstance(self.expression, str) else self.expression.to_dict()
        return {"type": "ZeroOrMorePath", "expression": expr}


@dataclass
class OneOrMorePath:
    """One-or-more repetition (sh:oneOrMorePath / SPARQL ``p+``)."""
    expression: Union[str, "PropertyPath"]

    def to_dict(self) -> dict:
        expr = self.expression if isinstance(self.expression, str) else self.expression.to_dict()
        return {"type": "OneOrMorePath", "expression": expr}


@dataclass
class ZeroOrOnePath:
    """Zero-or-one repetition (sh:zeroOrOnePath / SPARQL ``p?``)."""
    expression: Union[str, "PropertyPath"]

    def to_dict(self) -> dict:
        expr = self.expression if isinstance(self.expression, str) else self.expression.to_dict()
        return {"type": "ZeroOrOnePath", "expression": expr}


PropertyPath = Union[
    InversePath, SequencePath, AlternativePath,
    ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath,
]


# ── Node Constraint ───────────────────────────────────────────────────────────

@dataclass
class NodeConstraintE:
    """ShexJE NodeConstraint.

    Extends ShexJ NodeConstraint with SHACL-specific facets (``languageIn``,
    ``uniqueLang``) and shorthand fields (``hasValue``, ``in``).
    """
    id: Optional[str] = None            # IRI when used as a top-level shape

    # ---- ShexJ fields -------------------------------------------------------
    nodeKind: Optional[str] = None       # iri | bnode | nonliteral | literal
    datatype: Optional[str] = None       # datatype IRI
    values: Optional[list[ValueSetEntry]] = None   # value set [v1 v2 …]
    pattern: Optional[str] = None        # regex string facet
    flags: Optional[str] = None          # regex flags (e.g. "i")
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    minInclusive: Optional[float] = None
    maxInclusive: Optional[float] = None
    minExclusive: Optional[float] = None
    maxExclusive: Optional[float] = None
    totalDigits: Optional[int] = None
    fractionDigits: Optional[int] = None

    # ---- ShexJE SHACL additions ---------------------------------------------
    hasValue: Optional[Union[str, dict]] = None    # sh:hasValue shorthand
    in_values: Optional[list[ValueSetEntry]] = None  # sh:in shorthand (JSON key: "in")
    languageIn: Optional[list[str]] = None          # sh:languageIn
    uniqueLang: Optional[bool] = None               # sh:uniqueLang

    def to_dict(self) -> dict:
        d: dict = {"type": "NodeConstraint"}
        if self.id is not None:
            d["id"] = self.id
        if self.nodeKind is not None:
            d["nodeKind"] = self.nodeKind
        if self.datatype is not None:
            d["datatype"] = self.datatype
        if self.values is not None:
            d["values"] = [_vse_to_dict(v) for v in self.values]
        if self.pattern is not None:
            d["pattern"] = self.pattern
        if self.flags is not None:
            d["flags"] = self.flags
        if self.minLength is not None:
            d["minLength"] = self.minLength
        if self.maxLength is not None:
            d["maxLength"] = self.maxLength
        if self.minInclusive is not None:
            d["minInclusive"] = self.minInclusive
        if self.maxInclusive is not None:
            d["maxInclusive"] = self.maxInclusive
        if self.minExclusive is not None:
            d["minExclusive"] = self.minExclusive
        if self.maxExclusive is not None:
            d["maxExclusive"] = self.maxExclusive
        if self.totalDigits is not None:
            d["totalDigits"] = self.totalDigits
        if self.fractionDigits is not None:
            d["fractionDigits"] = self.fractionDigits
        # ShexJE SHACL extensions
        if self.hasValue is not None:
            d["hasValue"] = self.hasValue
        if self.in_values is not None:
            d["in"] = [_vse_to_dict(v) for v in self.in_values]
        if self.languageIn is not None:
            d["languageIn"] = self.languageIn
        if self.uniqueLang is not None:
            d["uniqueLang"] = self.uniqueLang
        return d


# ── Shape Reference ───────────────────────────────────────────────────────────

@dataclass
class ShapeRefE:
    """Reference to a named shape (``@<ShapeName>`` in ShExC)."""
    reference: str   # shape IRI (compact or full)

    def to_dict(self) -> dict:
        return {"type": "ShapeRef", "reference": self.reference}


# ── Shape Expressions ─────────────────────────────────────────────────────────

# Note: ShapeExpression is forward-declared; concrete definition appears after
# all constituent types are defined.

@dataclass
class ShapeOrE:
    """Logical OR of shape expressions (ShexJ ShapeOr / SHACL sh:or)."""
    shapeExprs: list["ShapeExpression"]
    id: Optional[str] = None
    severity: Optional[str] = None
    message: Optional[Union[str, list[str]]] = None
    deactivated: Optional[bool] = None

    def to_dict(self) -> dict:
        d: dict = {"type": "ShapeOr", "shapeExprs": [_se_to_dict(e) for e in self.shapeExprs]}
        if self.id is not None:
            d["id"] = self.id
        _add_validation_meta(d, self)
        return d


@dataclass
class ShapeAndE:
    """Logical AND of shape expressions (ShexJ ShapeAnd / SHACL sh:and)."""
    shapeExprs: list["ShapeExpression"]
    id: Optional[str] = None
    severity: Optional[str] = None
    message: Optional[Union[str, list[str]]] = None
    deactivated: Optional[bool] = None

    def to_dict(self) -> dict:
        d: dict = {"type": "ShapeAnd", "shapeExprs": [_se_to_dict(e) for e in self.shapeExprs]}
        if self.id is not None:
            d["id"] = self.id
        _add_validation_meta(d, self)
        return d


@dataclass
class ShapeNotE:
    """Negation of a shape expression (ShexJ ShapeNot / SHACL sh:not)."""
    shapeExpr: "ShapeExpression"
    id: Optional[str] = None
    severity: Optional[str] = None
    message: Optional[Union[str, list[str]]] = None
    deactivated: Optional[bool] = None

    def to_dict(self) -> dict:
        d: dict = {"type": "ShapeNot", "shapeExpr": _se_to_dict(self.shapeExpr)}
        if self.id is not None:
            d["id"] = self.id
        _add_validation_meta(d, self)
        return d


@dataclass
class ShapeXoneE:
    """Exclusive-OR of shape expressions (SHACL sh:xone). *New in ShexJE.*"""
    shapeExprs: list["ShapeExpression"]
    id: Optional[str] = None
    severity: Optional[str] = None
    message: Optional[Union[str, list[str]]] = None
    deactivated: Optional[bool] = None

    def to_dict(self) -> dict:
        d: dict = {"type": "ShapeXone", "shapeExprs": [_se_to_dict(e) for e in self.shapeExprs]}
        if self.id is not None:
            d["id"] = self.id
        _add_validation_meta(d, self)
        return d


# Concrete definition of ShapeExpression union
ShapeExpression = Union[
    "ShapeE", NodeConstraintE, ShapeRefE,
    ShapeOrE, ShapeAndE, ShapeNotE, ShapeXoneE,
]


# ── SPARQL Constraint (new in ShexJE) ─────────────────────────────────────────

@dataclass
class SparqlConstraintE:
    """SHACL ``sh:sparql`` constraint. *New in ShexJE.*"""
    select: str                                       # SPARQL SELECT query
    prefixes: Optional[dict[str, str]] = None         # local prefix map
    message: Optional[Union[str, list[str]]] = None
    severity: Optional[str] = None
    deactivated: Optional[bool] = None

    def to_dict(self) -> dict:
        d: dict = {"type": "SparqlConstraint", "select": self.select}
        if self.prefixes:
            d["prefixes"] = self.prefixes
        _add_validation_meta(d, self)
        return d


# ── Triple Expressions ────────────────────────────────────────────────────────

TripleExpression = Union["TripleConstraintE", "EachOfE", "OneOfE", str]


@dataclass
class TripleConstraintE:
    """ShexJE TripleConstraint.

    Extends ShexJ TripleConstraint with:

    * **Property paths** (``path`` field) for SHACL SPARQL-path support.
    * **Validation metadata**: ``severity``, ``message``, ``deactivated``.
    * **Property-pair constraints**: ``equals``, ``disjoint``, ``lessThan``,
      ``lessThanOrEquals``.
    * **Qualified value shapes**: ``qualifiedValueShape``, ``qualifiedMinCount``,
      ``qualifiedMaxCount``, ``qualifiedValueShapesDisjoint``.
    * **Canonical-JSON shorthands**: ``classRef``, ``classRefOr``, ``iriStem``,
      ``hasValue``, ``in`` — for compact representation of common patterns.
    """
    # ---- ShexJ fields -------------------------------------------------------
    predicate: Optional[str] = None          # simple IRI predicate
    valueExpr: Optional[ShapeExpression] = None
    inverse: bool = False
    min: Optional[int] = None                # cardinality min (None = language default)
    max: Optional[int] = None                # cardinality max (-1 = unbounded)
    semActs: Optional[list[dict]] = None
    annotations: Optional[list[dict]] = None

    # ---- ShexJE: property path ----------------------------------------------
    # When set, overrides ``predicate`` and ``inverse`` (supports complex paths).
    path: Optional[PropertyPath] = None

    # ---- ShexJE SHACL validation metadata -----------------------------------
    severity: Optional[str] = None           # sh:Violation | sh:Warning | sh:Info
    message: Optional[Union[str, list[str]]] = None
    deactivated: Optional[bool] = None

    # ---- ShexJE SHACL property-pair constraints -----------------------------
    equals: Optional[str] = None             # sh:equals (other predicate IRI)
    disjoint: Optional[str] = None           # sh:disjoint
    lessThan: Optional[str] = None           # sh:lessThan
    lessThanOrEquals: Optional[str] = None   # sh:lessThanOrEquals

    # ---- ShexJE SHACL qualified value shapes --------------------------------
    qualifiedValueShape: Optional[ShapeExpression] = None
    qualifiedMinCount: Optional[int] = None
    qualifiedMaxCount: Optional[int] = None
    qualifiedValueShapesDisjoint: Optional[bool] = None

    # ---- ShexJE SHACL language facets ---------------------------------------
    uniqueLang: Optional[bool] = None        # sh:uniqueLang

    # ---- ShexJE canonical-JSON shorthand fields -----------------------------
    # These are convenience alternatives to fully expanded ``valueExpr`` forms.
    classRef: Optional[str] = None           # → ShapeRef to a single-class shape
    classRefOr: Optional[list[str]] = None   # → OR of class-instance shapes
    iriStem: Optional[str] = None            # → IriStem value-set constraint
    hasValue: Optional[Union[str, dict]] = None  # → sh:hasValue (IRI or literal)
    in_values: Optional[list] = None         # → sh:in enumeration (JSON key: "in")

    def to_dict(self) -> dict:
        d: dict = {"type": "TripleConstraint"}
        # Path or predicate (path takes precedence)
        if self.path is not None:
            d["path"] = self.path.to_dict()
        elif self.predicate is not None:
            d["predicate"] = self.predicate
        if self.inverse and self.path is None:
            d["inverse"] = True
        if self.valueExpr is not None:
            d["valueExpr"] = _se_to_dict(self.valueExpr)
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        if self.semActs:
            d["semActs"] = self.semActs
        if self.annotations:
            d["annotations"] = self.annotations
        # ShexJE extensions
        _add_validation_meta(d, self)
        if self.equals is not None:
            d["equals"] = self.equals
        if self.disjoint is not None:
            d["disjoint"] = self.disjoint
        if self.lessThan is not None:
            d["lessThan"] = self.lessThan
        if self.lessThanOrEquals is not None:
            d["lessThanOrEquals"] = self.lessThanOrEquals
        if self.qualifiedValueShape is not None:
            d["qualifiedValueShape"] = _se_to_dict(self.qualifiedValueShape)
        if self.qualifiedMinCount is not None:
            d["qualifiedMinCount"] = self.qualifiedMinCount
        if self.qualifiedMaxCount is not None:
            d["qualifiedMaxCount"] = self.qualifiedMaxCount
        if self.qualifiedValueShapesDisjoint is not None:
            d["qualifiedValueShapesDisjoint"] = self.qualifiedValueShapesDisjoint
        if self.uniqueLang is not None:
            d["uniqueLang"] = self.uniqueLang
        # Shorthand fields
        if self.classRef is not None:
            d["classRef"] = self.classRef
        if self.classRefOr is not None:
            d["classRefOr"] = sorted(self.classRefOr)
        if self.iriStem is not None:
            d["iriStem"] = self.iriStem
        if self.hasValue is not None:
            d["hasValue"] = self.hasValue
        if self.in_values is not None:
            d["in"] = list(self.in_values)
        return d


@dataclass
class EachOfE:
    """Conjunction of triple expressions (``;`` in ShExC). Mirrors ShexJ EachOf."""
    expressions: list[TripleExpression] = field(default_factory=list)
    min: Optional[int] = None
    max: Optional[int] = None
    semActs: Optional[list[dict]] = None
    annotations: Optional[list[dict]] = None

    def to_dict(self) -> dict:
        d: dict = {
            "type": "EachOf",
            "expressions": [_te_to_dict(e) for e in self.expressions],
        }
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d


@dataclass
class OneOfE:
    """Disjunction of triple expressions (``|`` in ShExC). Mirrors ShexJ OneOf."""
    expressions: list[TripleExpression] = field(default_factory=list)
    min: Optional[int] = None
    max: Optional[int] = None
    semActs: Optional[list[dict]] = None
    annotations: Optional[list[dict]] = None

    def to_dict(self) -> dict:
        d: dict = {
            "type": "OneOf",
            "expressions": [_te_to_dict(e) for e in self.expressions],
        }
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d


# ── Shape ─────────────────────────────────────────────────────────────────────

@dataclass
class ShapeE:
    """ShexJE Shape.

    Extends ShexJ Shape with SHACL target declarations, validation metadata,
    logical operators at the shape level (``and``, ``or``, ``not``, ``xone``),
    and SPARQL constraints.

    All ShexJ Shape fields are preserved verbatim; new fields are omitted from
    JSON output when ``None`` / empty.
    """
    id: str    # shape IRI or local name (e.g. "Person" or "ex:PersonShape")

    # ---- ShexJ fields -------------------------------------------------------
    closed: bool = False
    extra: list[str] = field(default_factory=list)    # EXTRA predicate IRIs
    expression: Optional[TripleExpression] = None
    extends: list[str] = field(default_factory=list)  # shape IRIs
    restricts: list[str] = field(default_factory=list)
    semActs: Optional[list[dict]] = None
    annotations: Optional[list[dict]] = None

    # ---- ShexJE SHACL target declarations -----------------------------------
    targetClass: Optional[Union[str, list[str]]] = None   # sh:targetClass
    targetNode: Optional[list[str]] = None                 # sh:targetNode
    targetSubjectsOf: Optional[list[str]] = None           # sh:targetSubjectsOf
    targetObjectsOf: Optional[list[str]] = None            # sh:targetObjectsOf

    # ---- ShexJE SHACL validation metadata -----------------------------------
    severity: Optional[str] = None           # sh:Violation | sh:Warning | sh:Info
    message: Optional[Union[str, list[str]]] = None
    deactivated: Optional[bool] = None

    # ---- ShexJE SHACL logical operators at shape level ----------------------
    # These are *in addition to* the ShexJ top-level ShapeOr / ShapeAnd / ShapeNot
    # types; here they apply to the current shape's constraints inline.
    and_: Optional[list[ShapeExpression]] = None   # sh:and  (JSON key: "and")
    or_: Optional[list[ShapeExpression]] = None    # sh:or   (JSON key: "or")
    not_: Optional[ShapeExpression] = None         # sh:not  (JSON key: "not")
    xone: Optional[list[ShapeExpression]] = None   # sh:xone

    # ---- ShexJE SHACL SPARQL constraints ------------------------------------
    sparql: Optional[list[SparqlConstraintE]] = None

    def to_dict(self) -> dict:
        d: dict = {"type": "Shape", "id": self.id}
        if self.closed:
            d["closed"] = True
        if self.extra:
            d["extra"] = self.extra
        if self.extends:
            d["extends"] = self.extends
        if self.restricts:
            d["restricts"] = self.restricts
        if self.expression is not None:
            d["expression"] = _te_to_dict(self.expression)
        if self.semActs:
            d["semActs"] = self.semActs
        if self.annotations:
            d["annotations"] = self.annotations
        # ShexJE target declarations
        if self.targetClass is not None:
            d["targetClass"] = self.targetClass
        if self.targetNode:
            d["targetNode"] = self.targetNode
        if self.targetSubjectsOf:
            d["targetSubjectsOf"] = self.targetSubjectsOf
        if self.targetObjectsOf:
            d["targetObjectsOf"] = self.targetObjectsOf
        # ShexJE validation metadata
        _add_validation_meta(d, self)
        # ShexJE logical operators
        if self.and_:
            d["and"] = [_se_to_dict(e) for e in self.and_]
        if self.or_:
            d["or"] = [_se_to_dict(e) for e in self.or_]
        if self.not_ is not None:
            d["not"] = _se_to_dict(self.not_)
        if self.xone:
            d["xone"] = [_se_to_dict(e) for e in self.xone]
        if self.sparql:
            d["sparql"] = [c.to_dict() for c in self.sparql]
        return d


# ── Top-level Shape declarations (mirrors ShexJ) ──────────────────────────────

ShapeDecl = Union[ShapeE, NodeConstraintE, ShapeOrE, ShapeAndE, ShapeNotE, ShapeXoneE]


# ── Schema ────────────────────────────────────────────────────────────────────

@dataclass
class ShexJESchema:
    """Top-level ShexJE schema.

    Extends ShexJ Schema.  ``prefixes`` is a plain ``dict`` (more ergonomic
    than a list of Prefix objects) consistent with the existing canonical JSON.
    """
    shapes: list[ShapeDecl] = field(default_factory=list)
    prefixes: dict[str, str] = field(default_factory=dict)  # prefix → IRI namespace
    base: Optional[str] = None
    start: Optional[str] = None       # IRI of start shape
    startActs: Optional[list[dict]] = None
    imports: Optional[list[str]] = None

    def to_dict(self) -> dict:
        d: dict = {
            "@context": "http://www.w3.org/ns/shexje.jsonld",
            "type": "Schema",
        }
        if self.prefixes:
            d["prefixes"] = self.prefixes
        if self.base is not None:
            d["base"] = self.base
        if self.start is not None:
            d["start"] = self.start
        if self.startActs:
            d["startActs"] = self.startActs
        if self.imports:
            d["imports"] = self.imports
        d["shapes"] = [s.to_dict() for s in self.shapes]
        return d


# ── Internal helpers ──────────────────────────────────────────────────────────

def _vse_to_dict(v: ValueSetEntry) -> Any:
    """Convert a value-set entry to a JSON-serialisable value."""
    if isinstance(v, (str, dict)):
        return v
    return v.to_dict()


def _se_to_dict(se: ShapeExpression) -> Any:
    """Convert a shape expression to a JSON-serialisable value."""
    if isinstance(se, str):
        return se           # bare ShapeRef (IRI string)
    return se.to_dict()


def _te_to_dict(te: TripleExpression) -> Any:
    """Convert a triple expression to a JSON-serialisable value."""
    if isinstance(te, str):
        return te           # TripleExprRef
    return te.to_dict()


def _add_validation_meta(d: dict, obj: Any) -> None:
    """Append severity / message / deactivated to *d* when present on *obj*."""
    if getattr(obj, "severity", None) is not None:
        d["severity"] = obj.severity
    if getattr(obj, "message", None) is not None:
        d["message"] = obj.message
    if getattr(obj, "deactivated", None) is not None:
        d["deactivated"] = obj.deactivated
