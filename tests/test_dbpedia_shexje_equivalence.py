"""DBpedia ShExJE equivalence test suite.

Translates every file that appears in both dataset/shex_dbpedia/ and
dataset/shacl_dbpedia/ to ShExJE and verifies the two representations are
semantically equivalent.

Two entry paths are tested for each of the 20 DBpedia shapes:

    ShEx  path : dataset/shex_dbpedia/<Name>.shex  → parse_shex_file
                 → convert_shex_to_shexje → ShexJESchema → normalise
    SHACL path : dataset/shacl_dbpedia/<Name>.ttl  → parse_shacl_file
                 → convert_shacl_to_shexje → ShexJESchema → normalise

Key normalisation difference vs. the YAGO suite
────────────────────────────────────────────────
DBpedia SHACL shapes combine sh:class with sh:nodeKind sh:IRI, which the
SHACL→ShExJE converter emits as ShapeAndE(shapeExprs=[<ref>, NodeConstraintE]).
The _resolve_constraint helper here unwraps ShapeAndE so the class comparison
is format-agnostic.

Known semantic gaps (xfail)
───────────────────────────
Four shapes use sh:alternativePath in SHACL to merge predicates that the ShEx
source treats as separate triple constraints:

  Company    : foundingDate | formationDate | openingDate → one combined TC
  Person     : occupation | profession                    → one combined TC
  SportsTeam : stadium | homeStadium                      → one combined TC
  WrittenWork: literaryGenre | genre                      → one combined TC

These shapes are xfail(strict=True) in TestDirectEquivalence; the predicate-set
tests are skipped for them.  All other 16 shapes must pass strictly.

Test coverage
─────────────
TestDirectEquivalence    20  Full normalised comparison per shape
TestSchemaStructure      16  targetClass present; predicate sets identical
                             (shapes without alternativePath divergence only)
TestCardinality          18  Required (+), optional (?), unbounded (*) semantics
TestClassConstraints      8  @ShapeRef ≡ sh:class for relational properties
TestNodeKind              4  IRI nodeKind for selected properties
TestDatatype             10  Literal datatype spot-checks
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, NamedTuple, Optional

import pytest

from shaclex_py.schema.shexje import (
    EachOfE,
    IriStemValue,
    NodeConstraintE,
    OneOfE,
    ShapeAndE,
    ShapeE,
    ShapeRefE,
    ShexJESchema,
    TripleConstraintE,
)

# ── Dataset paths ─────────────────────────────────────────────────────────────

_ROOT           = os.path.join(os.path.dirname(__file__), "..")
SHEX_DBPEDIA_DIR  = os.path.join(_ROOT, "dataset", "shex_dbpedia")
SHACL_DBPEDIA_DIR = os.path.join(_ROOT, "dataset", "shacl_dbpedia")

# ── IRI namespace prefixes ────────────────────────────────────────────────────

_DBO  = "http://dbpedia.org/ontology/"
_XSD  = "http://www.w3.org/2001/XMLSchema#"
_RDF  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
_FOAF  = "http://xmlns.com/foaf/0.1/"

# ── Shape name sets ───────────────────────────────────────────────────────────

DBPEDIA_NAMES: list[str] = sorted(
    os.path.splitext(f)[0]
    for f in os.listdir(SHEX_DBPEDIA_DIR)
    if f.endswith(".shex")
    and os.path.exists(os.path.join(SHACL_DBPEDIA_DIR, f.replace(".shex", ".ttl")))
)

# Shapes where SHACL uses sh:alternativePath to collapse predicates that ShEx
# keeps separate.  These diverge structurally and cannot be compared predicate-
# for-predicate; they are marked xfail in the full equivalence test.
_ALT_PATH_SHAPES: frozenset[str] = frozenset({
    "Company",      # foundingDate | formationDate | openingDate
    "Person",       # occupation | profession
    "SportsTeam",   # stadium | homeStadium
    "WrittenWork",  # literaryGenre | genre
})

_STRICT_NAMES: list[str] = [n for n in DBPEDIA_NAMES if n not in _ALT_PATH_SHAPES]

_ALTPATH_XFAIL = pytest.mark.xfail(
    reason=(
        "SHACL uses sh:alternativePath to merge predicates that ShEx keeps as "
        "separate triple constraints.  The two normalised schemas therefore have "
        "different predicate sets and cannot be compared 1:1."
    ),
    strict=True,
)


# ── PropSpec ──────────────────────────────────────────────────────────────────

class PropSpec(NamedTuple):
    min: Optional[int]
    max: Optional[int]
    constraint_type: str   # none|datatype|nodeKind|class|iriStem|pattern|values|ref
    constraint_value: Any


# ── Normalization helpers ─────────────────────────────────────────────────────

def _collect_tcs(expr) -> list[TripleConstraintE]:
    if isinstance(expr, TripleConstraintE):
        return [expr]
    if isinstance(expr, (EachOfE, OneOfE)):
        tcs: list[TripleConstraintE] = []
        for sub in expr.expressions:
            tcs.extend(_collect_tcs(sub))
        return tcs
    return []


def _companion_classes(shape: ShapeE) -> Optional[list[str]]:
    """Extract sorted class IRIs from a companion value shape, or None."""
    if shape.predicate is not None and shape.values is not None:
        iris = sorted(v for v in shape.values if isinstance(v, str))
        return iris if iris else None
    if isinstance(shape.expression, TripleConstraintE):
        ve = shape.expression.valueExpr
        if isinstance(ve, NodeConstraintE) and ve.values:
            iris = sorted(v for v in ve.values if isinstance(v, str))
            return iris if iris else None
    return None


def _resolve_constraint(value_expr, shape_map: dict) -> tuple[str, Any]:
    if value_expr is None:
        return ("none", None)
    if isinstance(value_expr, NodeConstraintE):
        if value_expr.datatype is not None:
            return ("datatype", value_expr.datatype)
        if value_expr.nodeKind is not None:
            return ("nodeKind", value_expr.nodeKind)
        if value_expr.values is not None:
            if len(value_expr.values) == 1 and isinstance(value_expr.values[0], IriStemValue):
                return ("iriStem", value_expr.values[0].stem)
            return ("values", sorted(str(v) for v in value_expr.values))
        if value_expr.pattern is not None:
            return ("pattern", value_expr.pattern)
        return ("none", None)
    if isinstance(value_expr, (str, ShapeRefE)):
        ref = value_expr if isinstance(value_expr, str) else value_expr.reference
        companion = shape_map.get(ref)
        if isinstance(companion, ShapeE):
            classes = _companion_classes(companion)
            if classes is not None:
                return ("class", classes)
        return ("ref", ref)
    # DBpedia SHACL combines sh:class + sh:nodeKind sh:IRI as ShapeAndE.
    # Unwrap the shape reference first; fall back to nodeKind if unresolvable.
    if isinstance(value_expr, ShapeAndE):
        for expr in value_expr.shapeExprs:
            if isinstance(expr, (str, ShapeRefE)):
                ref = expr if isinstance(expr, str) else expr.reference
                companion = shape_map.get(ref)
                if isinstance(companion, ShapeE):
                    classes = _companion_classes(companion)
                    if classes is not None:
                        return ("class", classes)
                return ("ref", ref)
        for expr in value_expr.shapeExprs:
            if isinstance(expr, NodeConstraintE) and expr.nodeKind is not None:
                return ("nodeKind", expr.nodeKind)
    return ("none", None)


def _normalize(schema: ShexJESchema) -> dict[str, dict[str, PropSpec]]:
    """Reduce a ShexJE schema to ``{targetClass: {predicate: PropSpec}}``."""
    shape_map = {s.id: s for s in schema.shapes if hasattr(s, "id") and s.id}
    result: dict[str, dict[str, PropSpec]] = {}
    for shape in schema.shapes:
        if not isinstance(shape, ShapeE) or shape.targetClass is None:
            continue
        tc_val = shape.targetClass
        target_class = tc_val[0] if isinstance(tc_val, list) else tc_val
        props: dict[str, PropSpec] = {}
        if shape.expression is not None:
            for tc in _collect_tcs(shape.expression):
                if tc.predicate is None:
                    continue
                ctype, cval = _resolve_constraint(tc.valueExpr, shape_map)
                props[tc.predicate] = PropSpec(tc.min, tc.max, ctype, cval)
        result[target_class] = props
    return result


# ── Conversion with caching ───────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _shex_norm(name: str) -> dict[str, dict[str, PropSpec]]:
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    return _normalize(convert_shex_to_shexje(
        parse_shex_file(os.path.join(SHEX_DBPEDIA_DIR, f"{name}.shex"))
    ))


@lru_cache(maxsize=None)
def _shacl_norm(name: str) -> dict[str, dict[str, PropSpec]]:
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    return _normalize(convert_shacl_to_shexje(
        parse_shacl_file(os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl"))
    ))


def _shex_props(name: str) -> dict[str, PropSpec]:
    norm = _shex_norm(name)
    assert len(norm) == 1, f"{name}: expected 1 targetClass in ShEx, got {list(norm)}"
    return next(iter(norm.values()))


def _shacl_props(name: str) -> dict[str, PropSpec]:
    norm = _shacl_norm(name)
    assert len(norm) == 1, f"{name}: expected 1 targetClass in SHACL, got {list(norm)}"
    return next(iter(norm.values()))


# ── Assertion helpers ─────────────────────────────────────────────────────────

def _assert_spec_equal(shex_spec: PropSpec, shacl_spec: PropSpec, label: str) -> None:
    assert shex_spec.min == shacl_spec.min, (
        f"{label}: min mismatch ShEx={shex_spec.min!r} SHACL={shacl_spec.min!r}"
    )
    assert shex_spec.max == shacl_spec.max, (
        f"{label}: max mismatch ShEx={shex_spec.max!r} SHACL={shacl_spec.max!r}"
    )
    assert shex_spec.constraint_type == shacl_spec.constraint_type, (
        f"{label}: constraint_type ShEx={shex_spec.constraint_type!r} "
        f"SHACL={shacl_spec.constraint_type!r}"
    )
    assert shex_spec.constraint_value == shacl_spec.constraint_value, (
        f"{label}: constraint_value ShEx={shex_spec.constraint_value!r} "
        f"SHACL={shacl_spec.constraint_value!r}"
    )


def _pred_spec(name: str, pred: str) -> tuple[PropSpec, PropSpec]:
    """Return (shex_spec, shacl_spec) for *pred* in shape *name*."""
    sp = _shex_props(name)
    hp = _shacl_props(name)
    assert pred in sp,  f"{name}: predicate {pred!r} missing from ShEx ShexJE"
    assert pred in hp,  f"{name}: predicate {pred!r} missing from SHACL ShexJE"
    return sp[pred], hp[pred]


# ── Parametrised test data ────────────────────────────────────────────────────

# (shape, predicate, expected_min, expected_max) cardinality spot-checks
_CARDINALITY_CASES: list[tuple[str, str, Optional[int], Optional[int]]] = [
    # rdfs:label: required + = min 1, max -1
    ("Airport",     f"{_RDFS}label",                         1,    -1),
    ("Artist",      f"{_RDFS}label",                         1,    -1),
    ("Astronaut",   f"{_RDFS}label",                         1,    -1),
    ("City",        f"{_RDFS}label",                         1,    -1),
    ("Film",        f"{_RDFS}label",                         1,    -1),
    # required exactly-one (min 1, max 1)
    ("Astronaut",   f"{_DBO}birthDate",                      1,     1),
    ("Artist",      f"{_DBO}birthPlace",                     1,     1),
    ("City",        f"{_DBO}country",                        1,     1),
    ("City",        f"{_DBO}populationTotal",                1,     1),
    # optional (?) = min 0, max 1
    ("Artist",      f"{_DBO}deathPlace",                     0,     1),
    ("Athlete",     f"{_DBO}deathDate",                      0,     1),
    ("Scientist",   f"{_DBO}birthPlace",                     0,     1),
    ("Scientist",   f"{_DBO}deathPlace",                     0,     1),
    ("University",  f"{_DBO}numberOfStudents",               0,     1),
    # required one-or-more (+) = min 1, max -1
    ("Airport",     f"{_DBO}runwayLength",                   1,    -1),
    ("Film",        f"{_DBO}director",                       1,    -1),
    ("Film",        f"{_DBO}starring",                       1,    -1),
    ("Athlete",     f"{_DBO}sport",                          1,    -1),
    # unbounded zero-or-more (*) = min None, max None
    ("Astronaut",   f"{_DBO}award",                          None, None),
    ("MusicalWork", f"{_DBO}award",                          None, None),
    ("Film",        f"{_DBO}runtime",                        None, None),
]

# (shape, predicate, expected_class_iris) class constraint spot-checks
_CLASS_CASES: list[tuple[str, str, list[str]]] = [
    ("Airport",   f"{_DBO}city",       [f"{_DBO}City"]),
    ("Airport",   f"{_DBO}location",   [f"{_DBO}Place"]),
    ("Athlete",   f"{_DBO}birthPlace", [f"{_DBO}Place"]),
    ("City",      f"{_DBO}country",    [f"{_DBO}Country"]),
    ("Film",      f"{_DBO}director",   [f"{_DBO}Person"]),
    ("Film",      f"{_DBO}starring",   [f"{_DBO}Person"]),
    ("Scientist", f"{_DBO}birthPlace", [f"{_DBO}Place"]),
    ("University",f"{_DBO}country",    [f"{_DBO}Country"]),
]

# (shape, predicate) pairs where both formats must normalise to nodeKind='IRI'
_IRI_NODEKIND_CASES: list[tuple[str, str]] = [
    ("Airport",    f"{_FOAF}homepage"),
    ("City",       f"{_DBO}namedAfter"),
    ("Person",     f"{_DBO}knownFor"),
    ("Politician", f"{_FOAF}homepage"),
]

# (shape, predicate, expected_datatype) literal datatype spot-checks
_DATATYPE_CASES: list[tuple[str, str, str]] = [
    ("Airport",     f"{_RDFS}label",                          f"{_RDF}langString"),
    ("Artist",      f"{_DBO}birthDate",                       f"{_XSD}date"),
    ("Astronaut",   f"{_DBO}birthDate",                       f"{_XSD}date"),
    ("Athlete",     f"{_DBO}activeYearsStartYear",            f"{_XSD}gYear"),
    ("Building",    f"{_DBO}floorCount",                      f"{_XSD}positiveInteger"),
    ("CelestialBody", f"{_DBO}mass",                          f"{_XSD}double"),
    ("City",        f"{_DBO}populationTotal",                 f"{_XSD}nonNegativeInteger"),
    ("Film",        f"{_DBO}runtime",                         f"{_XSD}double"),
    ("Person",      f"{_DBO}height",                          f"{_XSD}double"),
    ("University",  f"{_DBO}numberOfStudents",                f"{_XSD}nonNegativeInteger"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Test classes
# ═══════════════════════════════════════════════════════════════════════════════

class TestDirectEquivalence:
    """Full normalised comparison: ShEx→ShexJE ≡ SHACL→ShexJE for all 20 shapes.

    Four shapes that use sh:alternativePath in SHACL (collapsing predicates that
    ShEx keeps separate) are expected to fail.  The remaining 16 must pass.
    """

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param(n, marks=_ALTPATH_XFAIL) if n in _ALT_PATH_SHAPES else n
            for n in DBPEDIA_NAMES
        ],
    )
    def test_full_shexje_equivalence(self, name: str) -> None:
        sp = _shex_props(name)
        hp = _shacl_props(name)

        missing = set(sp) - set(hp)
        extra   = set(hp) - set(sp)
        assert not missing, (
            f"{name}: predicates in ShEx→ShexJE but not SHACL→ShexJE: {sorted(missing)}"
        )
        assert not extra, (
            f"{name}: predicates in SHACL→ShexJE but not ShEx→ShexJE: {sorted(extra)}"
        )

        for pred in sp:
            _assert_spec_equal(sp[pred], hp[pred], f"{name} [{pred}]")


class TestSchemaStructure:
    """Each converted ShexJE schema must have exactly one targetClass shape,
    and both representations must agree on which targetClass it is.

    Only tested for the 16 shapes without sh:alternativePath divergence.
    """

    @pytest.mark.parametrize("name", DBPEDIA_NAMES)
    def test_shex_schema_has_single_target_class(self, name: str) -> None:
        norm = _shex_norm(name)
        assert len(norm) == 1, (
            f"{name}: ShEx→ShexJE contains {len(norm)} targetClass shapes, "
            f"expected exactly 1: {list(norm)}"
        )

    @pytest.mark.parametrize("name", DBPEDIA_NAMES)
    def test_shacl_schema_has_single_target_class(self, name: str) -> None:
        norm = _shacl_norm(name)
        assert len(norm) == 1, (
            f"{name}: SHACL→ShexJE contains {len(norm)} targetClass shapes, "
            f"expected exactly 1: {list(norm)}"
        )

    @pytest.mark.parametrize("name", DBPEDIA_NAMES)
    def test_both_schemas_agree_on_target_class_iri(self, name: str) -> None:
        shex_class  = next(iter(_shex_norm(name)))
        shacl_class = next(iter(_shacl_norm(name)))
        assert shex_class == shacl_class, (
            f"{name}: targetClass IRI differs — "
            f"ShEx: {shex_class!r}, SHACL: {shacl_class!r}"
        )

    @pytest.mark.parametrize("name", _STRICT_NAMES)
    def test_predicate_sets_are_identical(self, name: str) -> None:
        shex_preds  = set(_shex_props(name))
        shacl_preds = set(_shacl_props(name))
        only_shex  = shex_preds  - shacl_preds
        only_shacl = shacl_preds - shex_preds
        assert not only_shex,  f"{name}: predicates only in ShEx→ShexJE:  {sorted(only_shex)}"
        assert not only_shacl, f"{name}: predicates only in SHACL→ShexJE: {sorted(only_shacl)}"

    @pytest.mark.parametrize("name", DBPEDIA_NAMES)
    def test_target_class_uses_dbo_namespace(self, name: str) -> None:
        shex_class  = next(iter(_shex_norm(name)))
        shacl_class = next(iter(_shacl_norm(name)))
        assert shex_class.startswith(_DBO), (
            f"{name}: ShEx targetClass not in dbo: namespace: {shex_class!r}"
        )
        assert shacl_class.startswith(_DBO), (
            f"{name}: SHACL targetClass not in dbo: namespace: {shacl_class!r}"
        )


class TestCardinality:
    """Cardinality semantics: ShEx quantifiers and SHACL sh:minCount/sh:maxCount
    must normalise to the same (min, max) pair in ShexJE.

    Conventions used by both converters:
      *  → (None, None)          zero-or-more (default)
      +  → (1, -1)               one-or-more
      ?  → (0, 1)                zero-or-one
     {1} → (1, 1)                exactly one
    """

    @pytest.mark.parametrize("name,pred,exp_min,exp_max", _CARDINALITY_CASES)
    def test_cardinality_agrees(
        self, name: str, pred: str, exp_min: Optional[int], exp_max: Optional[int]
    ) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.min == exp_min, (
            f"{name} {pred}: ShEx min={shex_spec.min!r}, expected {exp_min!r}"
        )
        assert shex_spec.max == exp_max, (
            f"{name} {pred}: ShEx max={shex_spec.max!r}, expected {exp_max!r}"
        )
        assert shacl_spec.min == exp_min, (
            f"{name} {pred}: SHACL min={shacl_spec.min!r}, expected {exp_min!r}"
        )
        assert shacl_spec.max == exp_max, (
            f"{name} {pred}: SHACL max={shacl_spec.max!r}, expected {exp_max!r}"
        )


class TestClassConstraints:
    """@ShapeRef in ShEx and sh:class in SHACL must both normalise to the same
    class IRI list in ShexJE.
    """

    @pytest.mark.parametrize("name,pred,expected_classes", _CLASS_CASES)
    def test_class_constraint_agrees(
        self, name: str, pred: str, expected_classes: list[str]
    ) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.constraint_type == "class", (
            f"{name} {pred}: ShEx constraint_type={shex_spec.constraint_type!r}, "
            f"expected 'class'"
        )
        assert shacl_spec.constraint_type == "class", (
            f"{name} {pred}: SHACL constraint_type={shacl_spec.constraint_type!r}, "
            f"expected 'class'"
        )
        assert shex_spec.constraint_value == sorted(expected_classes), (
            f"{name} {pred}: ShEx class list={shex_spec.constraint_value!r}"
        )
        assert shacl_spec.constraint_value == sorted(expected_classes), (
            f"{name} {pred}: SHACL class list={shacl_spec.constraint_value!r}"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} {pred}")


class TestNodeKind:
    """IRI-valued properties (ShEx ``IRI`` / SHACL ``sh:nodeKind sh:IRI`` without
    sh:class) must produce nodeKind='IRI' in both normalised ShexJE schemas.
    """

    @pytest.mark.parametrize("name,pred", _IRI_NODEKIND_CASES)
    def test_iri_nodekind_agrees(self, name: str, pred: str) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.constraint_type == "nodeKind", (
            f"{name} {pred}: ShEx constraint_type={shex_spec.constraint_type!r}, "
            f"expected 'nodeKind'"
        )
        assert shex_spec.constraint_value == "IRI", (
            f"{name} {pred}: ShEx nodeKind={shex_spec.constraint_value!r}, "
            f"expected 'IRI'"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} {pred}")


class TestDatatype:
    """Literal datatype constraints must be identical in both representations."""

    @pytest.mark.parametrize("name,pred,expected_dt", _DATATYPE_CASES)
    def test_datatype_agrees(self, name: str, pred: str, expected_dt: str) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.constraint_type == "datatype", (
            f"{name} {pred}: ShEx constraint_type={shex_spec.constraint_type!r}, "
            f"expected 'datatype'"
        )
        assert shex_spec.constraint_value == expected_dt, (
            f"{name} {pred}: ShEx datatype={shex_spec.constraint_value!r}, "
            f"expected {expected_dt!r}"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} {pred}")


class TestShapeSpotchecks:
    """Named per-property assertions for key DBpedia shapes.

    These tests pin concrete expected values and serve as regression anchors
    for the most representative shapes.
    """

    # ── Airport ───────────────────────────────────────────────────────────────

    def test_airport_target_class(self) -> None:
        target = f"{_DBO}Airport"
        assert next(iter(_shex_norm("Airport")))  == target
        assert next(iter(_shacl_norm("Airport"))) == target

    def test_airport_label_required_lang_string(self) -> None:
        shex_s, shacl_s = _pred_spec("Airport", f"{_RDFS}label")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_RDF}langString"
        assert shex_s.min == 1
        assert shacl_s == shex_s

    def test_airport_city_class_constraint(self) -> None:
        shex_s, shacl_s = _pred_spec("Airport", f"{_DBO}city")
        assert shex_s.constraint_type  == "class"
        assert shex_s.constraint_value == [f"{_DBO}City"]
        assert shacl_s == shex_s

    def test_airport_elevation_optional_double(self) -> None:
        shex_s, shacl_s = _pred_spec("Airport", f"{_DBO}elevation")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_XSD}double"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    # ── Artist ────────────────────────────────────────────────────────────────

    def test_artist_target_class(self) -> None:
        target = f"{_DBO}Artist"
        assert next(iter(_shex_norm("Artist")))  == target
        assert next(iter(_shacl_norm("Artist"))) == target

    def test_artist_birth_date_optional_date(self) -> None:
        shex_s, shacl_s = _pred_spec("Artist", f"{_DBO}birthDate")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_XSD}date"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_artist_birth_place_required_place(self) -> None:
        shex_s, shacl_s = _pred_spec("Artist", f"{_DBO}birthPlace")
        assert shex_s.constraint_type  == "class"
        assert shex_s.constraint_value == [f"{_DBO}Place"]
        assert shex_s.min == 1
        assert shex_s.max == 1
        assert shacl_s == shex_s

    # ── Film ──────────────────────────────────────────────────────────────────

    def test_film_target_class(self) -> None:
        target = f"{_DBO}Film"
        assert next(iter(_shex_norm("Film")))  == target
        assert next(iter(_shacl_norm("Film"))) == target

    def test_film_director_required_person(self) -> None:
        shex_s, shacl_s = _pred_spec("Film", f"{_DBO}director")
        assert shex_s.constraint_type  == "class"
        assert shex_s.constraint_value == [f"{_DBO}Person"]
        assert shex_s.min == 1
        assert shacl_s == shex_s

    def test_film_runtime_unbounded_double(self) -> None:
        shex_s, shacl_s = _pred_spec("Film", f"{_DBO}runtime")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_XSD}double"
        assert shex_s.min is None
        assert shex_s.max is None
        assert shacl_s == shex_s

    # ── City ──────────────────────────────────────────────────────────────────

    def test_city_target_class(self) -> None:
        target = f"{_DBO}City"
        assert next(iter(_shex_norm("City")))  == target
        assert next(iter(_shacl_norm("City"))) == target

    def test_city_population_required_nonneg_integer(self) -> None:
        shex_s, shacl_s = _pred_spec("City", f"{_DBO}populationTotal")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_XSD}nonNegativeInteger"
        assert shex_s.min == 1
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_city_country_required_country(self) -> None:
        shex_s, shacl_s = _pred_spec("City", f"{_DBO}country")
        assert shex_s.constraint_type  == "class"
        assert shex_s.constraint_value == [f"{_DBO}Country"]
        assert shex_s.min == 1
        assert shex_s.max == 1
        assert shacl_s == shex_s

    # ── Person ────────────────────────────────────────────────────────────────

    def test_person_target_class(self) -> None:
        target = f"{_DBO}Person"
        assert next(iter(_shex_norm("Person")))  == target
        assert next(iter(_shacl_norm("Person"))) == target

    def test_person_height_optional_double(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_DBO}height")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_XSD}double"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_person_abstract_required_lang_string(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_DBO}abstract")
        assert shex_s.constraint_type  == "datatype"
        assert shex_s.constraint_value == f"{_RDF}langString"
        assert shex_s.min == 1
        assert shacl_s == shex_s
