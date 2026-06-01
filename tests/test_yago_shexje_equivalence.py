"""Comprehensive YAGO ShexJE equivalence test suite.

Translates every file in dataset/shex_yago/ and dataset/shacl_yago/ to ShexJE
and verifies the two representations are semantically equivalent.

Two entry paths are tested for each of the 37 YAGO shapes:

    ShEx  path : dataset/shex_yago/<Name>.shex  → parse_shex_file
                 → convert_shex_to_shexje  → ShexJESchema → normalise
    SHACL path : dataset/shacl_yago/<Name>.ttl  → parse_shacl_file
                 → convert_shacl_to_shexje → ShexJESchema → normalise

Test coverage
─────────────
TestDirectEquivalence       37  Full normalised comparison per shape
TestSchemaStructure         37  One targetClass per file; sets match
TestUniversalProperties    111  rdfs:label (min≥1), mainEntityOfPage (min≥1),
                                owl:sameAs Wikidata IRI stem — for all 37 shapes
TestLabelDatatype           37  Correct xsd:string / rdf:langString per shape family
TestDatetimeOptional        20  Selected xsd:dateTime predicates are optional (max=1)
TestGeoConstraints          10  geo:wktLiteral in geographic shapes
TestORClassConstraints       7  OR-of-classes (Org | Person) translates identically
TestIRINodeKind              9  sh:nodeKind sh:IRI ≡ ShEx IRI for specific predicates
TestCardinality             22  Required (+), optional (?), unbounded (*) semantics
TestShapeSpotchecks         17  Per-property assertions for Person, Movie, City,
                                Airline, Award, Election, Gender
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
    ShapeE,
    ShapeRefE,
    ShexJESchema,
    TripleConstraintE,
)

# ── Dataset paths ─────────────────────────────────────────────────────────────

_ROOT          = os.path.join(os.path.dirname(__file__), "..")
SHACL_YAGO_DIR = os.path.join(_ROOT, "dataset", "shacl_yago")
SHEX_YAGO_DIR  = os.path.join(_ROOT, "dataset", "shex_yago")

# ── IRI namespace prefixes ────────────────────────────────────────────────────

_S    = "http://schema.org/"
_XSD  = "http://www.w3.org/2001/XMLSchema#"
_RDF  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
_OWL  = "http://www.w3.org/2002/07/owl#"
_YAGO = "http://yago-knowledge.org/resource/"
_GEO  = "http://www.opengis.net/ont/geosparql#"
_WD   = "http://www.wikidata.org/entity/"

# ── Shape name sets ───────────────────────────────────────────────────────────

YAGO_NAMES: list[str] = sorted(
    os.path.splitext(f)[0]
    for f in os.listdir(SHACL_YAGO_DIR)
    if f.endswith(".ttl")
    and os.path.exists(os.path.join(SHEX_YAGO_DIR, f.replace(".ttl", ".shex")))
)

# rdfs:label datatype families (determined from source files)
_LANG_STRING_LABEL_SHAPES: frozenset[str] = frozenset({
    "AdministrativeArea", "Airline", "Airport", "AstronomicalObject", "Award",
    "BeliefSystem", "BodyOfWater", "Book", "City", "Continent", "Corporation",
    "Country", "FictionalEntity", "Gender", "HumanMadeGeographicalEntity",
    "Landform", "Language", "Movie", "MusicComposition", "MusicGroup",
    "Politician", "Scientist", "SportsPerson", "TVSeries", "Taxon", "Way", "Worker",
})

_XSD_STRING_LABEL_SHAPES: frozenset[str] = frozenset({
    "CreativeWork", "Creator", "EducationalOrganization", "Election",
    "Event", "Newspaper", "Organization", "PerformingGroup", "Person", "Product",
})

# Shapes containing schema:geo with geo:wktLiteral
_GEO_SHAPES: frozenset[str] = frozenset({
    "AdministrativeArea", "Airport", "BodyOfWater", "City", "Continent",
    "Country", "EducationalOrganization", "HumanMadeGeographicalEntity",
    "Landform", "Way",
})

# ── PropSpec ──────────────────────────────────────────────────────────────────

class PropSpec(NamedTuple):
    min: Optional[int]
    max: Optional[int]
    constraint_type: str   # none|datatype|nodeKind|class|iriStem|pattern|values|ref
    constraint_value: Any  # IRI str, sorted [IRI], stem str, etc.


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

def _raw_shex_to_shexje(path: str) -> ShexJESchema:
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    return convert_shex_to_shexje(parse_shex_file(path))


def _raw_shacl_to_shexje(path: str) -> ShexJESchema:
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    return convert_shacl_to_shexje(parse_shacl_file(path))


@lru_cache(maxsize=None)
def _shex_norm(name: str) -> dict[str, dict[str, PropSpec]]:
    return _normalize(_raw_shex_to_shexje(os.path.join(SHEX_YAGO_DIR, f"{name}.shex")))


@lru_cache(maxsize=None)
def _shacl_norm(name: str) -> dict[str, dict[str, PropSpec]]:
    return _normalize(_raw_shacl_to_shexje(os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")))


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
    assert pred in hp, f"{name}: predicate {pred!r} missing from SHACL ShexJE"
    return sp[pred], hp[pred]


# ── Parametrised test data ────────────────────────────────────────────────────

# (shape, predicate) pairs known to use xsd:dateTime, all optional (max=1)
_DATETIME_OPTIONAL_CASES: list[tuple[str, str]] = [
    ("Person",     f"{_S}birthDate"),
    ("Person",     f"{_S}deathDate"),
    ("City",       f"{_S}dateCreated"),
    ("Airline",    f"{_S}dateCreated"),
    ("Airline",    f"{_S}dissolutionDate"),
    ("Movie",      f"{_S}dateCreated"),
    ("Election",   f"{_S}startDate"),
    ("Election",   f"{_S}endDate"),
    ("Event",      f"{_S}startDate"),
    ("Event",      f"{_S}endDate"),
    ("MusicGroup", f"{_S}dateCreated"),
    ("MusicGroup", f"{_S}dissolutionDate"),
    ("Scientist",  f"{_S}birthDate"),
    ("Scientist",  f"{_S}deathDate"),
    ("Creator",    f"{_S}birthDate"),
    ("Creator",    f"{_S}deathDate"),
    ("SportsPerson", f"{_S}birthDate"),
    ("SportsPerson", f"{_S}deathDate"),
    ("Politician", f"{_S}birthDate"),
    ("Politician", f"{_S}deathDate"),
]

# (shape, predicate, sorted expected class IRIs) for OR-of-classes constraints
_OR_CLASS_CASES: list[tuple[str, str, list[str]]] = [
    ("Airline",  f"{_YAGO}ownedBy",    [f"{_S}Organization", f"{_S}Person"]),
    ("Movie",    f"{_S}musicBy",       [f"{_S}Organization", f"{_S}Person"]),
    ("Movie",    f"{_S}author",        [f"{_S}Organization", f"{_S}Person"]),
    ("Award",    f"{_YAGO}ownedBy",    [f"{_S}Organization", f"{_S}Person"]),
    ("Election", f"{_S}organizer",     [f"{_S}Organization", f"{_S}Person"]),
    ("Election", f"{_YAGO}participant",[f"{_S}Organization", f"{_S}Person"]),
    ("Book",     f"{_S}author",        [f"{_S}Organization", f"{_S}Person"]),
]

# (shape, predicate) pairs known to carry sh:nodeKind sh:IRI / ShEx IRI.
# Book:schema:about is excluded — the ShEx source uses `.` (any value, no
# constraint) and the SHACL source uses the non-standard `sh:classKind`
# keyword (ignored by the parser), so both normalise to constraint_type="none".
_IRI_NODEKIND_CASES: list[tuple[str, str]] = [
    ("Person",    f"{_S}owns"),
    ("Award",     f"{_S}about"),
    ("Movie",     f"{_S}about"),
    ("CreativeWork", f"{_S}about"),
    ("Creator",   f"{_S}owns"),
    ("Creator",   f"{_YAGO}influencedBy"),
    ("Politician", f"{_S}owns"),
    ("Newspaper", f"{_S}about"),
]

# (shape, predicate, expected_min, expected_max) cardinality spot checks
_CARDINALITY_CASES: list[tuple[str, str, Optional[int], Optional[int]]] = [
    # rdfs:label: required (+) = min 1, max -1 (unbounded)
    ("Person",  f"{_RDFS}label", 1, -1),
    ("Movie",   f"{_RDFS}label", 1, -1),
    ("City",    f"{_RDFS}label", 1, -1),
    ("Award",   f"{_RDFS}label", 1, -1),
    ("Gender",  f"{_RDFS}label", 1, -1),
    # rdfs:comment: optional/unbounded (*) = min None, max None
    ("Person",  f"{_RDFS}comment", None, None),
    ("Movie",   f"{_RDFS}comment", None, None),
    ("City",    f"{_RDFS}comment", None, None),
    # schema:birthDate/deathDate: optional (?) = min 0, max 1
    ("Person",  f"{_S}birthDate", 0, 1),
    ("Person",  f"{_S}deathDate", 0, 1),
    ("Person",  f"{_S}gender",    0, 1),
    ("Person",  f"{_S}birthPlace",0, 1),
    ("Movie",   f"{_S}duration",  0, 1),
    # schema:mainEntityOfPage: required+unbounded for most (+) = min 1, max -1
    ("Person",  f"{_S}mainEntityOfPage", 1, -1),
    ("Award",   f"{_S}mainEntityOfPage", 1, -1),
    ("Airline", f"{_S}mainEntityOfPage", 1, -1),
    # City uses exactly-one mainEntityOfPage = min 1, max 1
    ("City",    f"{_S}mainEntityOfPage", 1, 1),
    # schema:geo: optional in geo-shapes (?) = min 0, max 1
    ("City",    f"{_S}geo", 0, 1),
    ("Way",     f"{_S}geo", 0, 1),
    # owl:sameAs: unbounded (*) = min None, max None
    ("Person",  f"{_OWL}sameAs", None, None),
    ("Movie",   f"{_OWL}sameAs", None, None),
    ("City",    f"{_OWL}sameAs", None, None),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Test classes
# ═══════════════════════════════════════════════════════════════════════════════

class TestDirectEquivalence:
    """Full normalised comparison: ShEx→ShexJE ≡ SHACL→ShexJE for all 37 shapes.

    This is the primary equivalence assertion: both source formats must produce
    an identical normalised ShexJE when translated independently.
    """

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_full_shexje_equivalence(self, name: str) -> None:
        sp = _shex_props(name)
        hp = _shacl_props(name)

        missing = set(sp) - set(hp)
        extra   = set(hp) - set(sp)
        assert not missing, f"{name}: predicates in ShEx→ShexJE but not SHACL→ShexJE: {missing}"
        assert not extra,   f"{name}: predicates in SHACL→ShexJE but not ShEx→ShexJE: {extra}"

        for pred in sp:
            _assert_spec_equal(sp[pred], hp[pred], f"{name} [{pred}]")


class TestSchemaStructure:
    """Each converted ShexJE schema must have exactly one targetClass shape,
    and both representations must agree on which targetClass it is.
    """

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_shex_schema_has_single_target_class(self, name: str) -> None:
        norm = _shex_norm(name)
        assert len(norm) == 1, (
            f"{name}: ShEx→ShexJE contains {len(norm)} targetClass shapes, "
            f"expected exactly 1: {list(norm)}"
        )

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_shacl_schema_has_single_target_class(self, name: str) -> None:
        norm = _shacl_norm(name)
        assert len(norm) == 1, (
            f"{name}: SHACL→ShexJE contains {len(norm)} targetClass shapes, "
            f"expected exactly 1: {list(norm)}"
        )

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_both_schemas_agree_on_target_class_iri(self, name: str) -> None:
        shex_class  = next(iter(_shex_norm(name)))
        shacl_class = next(iter(_shacl_norm(name)))
        assert shex_class == shacl_class, (
            f"{name}: targetClass IRI differs — "
            f"ShEx: {shex_class!r}, SHACL: {shacl_class!r}"
        )

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_predicate_sets_are_identical(self, name: str) -> None:
        shex_preds  = set(_shex_props(name))
        shacl_preds = set(_shacl_props(name))
        only_shex  = shex_preds  - shacl_preds
        only_shacl = shacl_preds - shex_preds
        assert not only_shex,  f"{name}: predicates only in ShEx→ShexJE:  {only_shex}"
        assert not only_shacl, f"{name}: predicates only in SHACL→ShexJE: {only_shacl}"

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_no_duplicate_predicates_in_shex(self, name: str) -> None:
        from shaclex_py.parser.shex_parser import parse_shex_file
        from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
        schema = convert_shex_to_shexje(parse_shex_file(
            os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        ))
        for shape in schema.shapes:
            if not isinstance(shape, ShapeE) or shape.expression is None:
                continue
            preds = [tc.predicate for tc in _collect_tcs(shape.expression)
                     if tc.predicate is not None]
            assert len(preds) == len(set(preds)), (
                f"{name}: duplicate predicates in ShEx→ShexJE: "
                + str([p for p in preds if preds.count(p) > 1])
            )

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_no_duplicate_predicates_in_shacl(self, name: str) -> None:
        from shaclex_py.parser.shacl_parser import parse_shacl_file
        from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
        schema = convert_shacl_to_shexje(parse_shacl_file(
            os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        ))
        for shape in schema.shapes:
            if not isinstance(shape, ShapeE) or shape.expression is None:
                continue
            preds = [tc.predicate for tc in _collect_tcs(shape.expression)
                     if tc.predicate is not None]
            assert len(preds) == len(set(preds)), (
                f"{name}: duplicate predicates in SHACL→ShexJE: "
                + str([p for p in preds if preds.count(p) > 1])
            )


class TestUniversalProperties:
    """Every one of the 37 YAGO shapes must carry three universal properties
    that are defined consistently in both the ShEx and SHACL sources.

    * rdfs:label         — required (minCount ≥ 1), datatype constraint
    * schema:mainEntityOfPage — required (minCount ≥ 1), xsd:anyURI
    * owl:sameAs         — IRI stem restricted to Wikidata entities
    """

    # Corporation and Event use rdfs:label * (zero-or-more) in both ShEx and
    # SHACL, so min is None for those two shapes.  All other 35 shapes use +.
    _LABEL_REQUIRED_SHAPES = frozenset(YAGO_NAMES) - {"Corporation", "Event"}
    _LABEL_OPTIONAL_SHAPES = frozenset({"Corporation", "Event"})

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_rdfs_label_present_datatype_constraint(self, name: str) -> None:
        """rdfs:label is present and carries a datatype constraint in both representations."""
        pred = f"{_RDFS}label"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.constraint_type == "datatype", (
            f"{name}: ShEx rdfs:label constraint_type={shex_spec.constraint_type!r}"
        )
        assert shacl_spec.constraint_type == "datatype", (
            f"{name}: SHACL rdfs:label constraint_type={shacl_spec.constraint_type!r}"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} rdfs:label")

    @pytest.mark.parametrize("name", sorted(_LABEL_REQUIRED_SHAPES))
    def test_rdfs_label_is_required_in_shape(self, name: str) -> None:
        """35 of 37 YAGO shapes declare rdfs:label as required (min=1)."""
        pred = f"{_RDFS}label"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.min == 1, (
            f"{name}: ShEx→ShexJE rdfs:label min={shex_spec.min!r}, expected 1"
        )
        assert shacl_spec.min == 1, (
            f"{name}: SHACL→ShexJE rdfs:label min={shacl_spec.min!r}, expected 1"
        )

    @pytest.mark.parametrize("name", sorted(_LABEL_OPTIONAL_SHAPES))
    def test_rdfs_label_is_optional_unbounded_in_shape(self, name: str) -> None:
        """Corporation and Event use rdfs:label * (zero-or-more) in both sources."""
        pred = f"{_RDFS}label"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.min is None, (
            f"{name}: ShEx→ShexJE rdfs:label min={shex_spec.min!r}, expected None (*)"
        )
        assert shacl_spec.min is None, (
            f"{name}: SHACL→ShexJE rdfs:label min={shacl_spec.min!r}, expected None (*)"
        )

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_main_entity_of_page_present_and_required(self, name: str) -> None:
        pred = f"{_S}mainEntityOfPage"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.min == 1,  (
            f"{name}: ShEx→ShexJE mainEntityOfPage min={shex_spec.min!r}, expected 1"
        )
        assert shacl_spec.min == 1, (
            f"{name}: SHACL→ShexJE mainEntityOfPage min={shacl_spec.min!r}, expected 1"
        )
        assert shex_spec.constraint_type == "datatype", (
            f"{name}: ShEx mainEntityOfPage constraint_type={shex_spec.constraint_type!r}"
        )
        assert shex_spec.constraint_value == f"{_XSD}anyURI", (
            f"{name}: ShEx mainEntityOfPage datatype={shex_spec.constraint_value!r}"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} mainEntityOfPage")

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_wikidata_owl_same_as_iri_stem(self, name: str) -> None:
        pred = f"{_OWL}sameAs"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.constraint_type == "iriStem", (
            f"{name}: ShEx owl:sameAs constraint_type={shex_spec.constraint_type!r}, "
            f"expected 'iriStem'"
        )
        assert shacl_spec.constraint_type == "iriStem", (
            f"{name}: SHACL owl:sameAs constraint_type={shacl_spec.constraint_type!r}, "
            f"expected 'iriStem'"
        )
        assert "wikidata.org/entity" in shex_spec.constraint_value, (
            f"{name}: ShEx owl:sameAs iriStem={shex_spec.constraint_value!r}"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} owl:sameAs")


class TestLabelDatatype:
    """Each YAGO shape uses either xsd:string or rdf:langString for rdfs:label.
    Both representations must agree on which datatype a given shape uses.
    """

    @pytest.mark.parametrize("name", sorted(_LANG_STRING_LABEL_SHAPES))
    def test_rdf_lang_string_label(self, name: str) -> None:
        pred = f"{_RDFS}label"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        expected = f"{_RDF}langString"
        assert shex_spec.constraint_value == expected, (
            f"{name}: ShEx label datatype={shex_spec.constraint_value!r}, expected {expected!r}"
        )
        assert shacl_spec.constraint_value == expected, (
            f"{name}: SHACL label datatype={shacl_spec.constraint_value!r}, expected {expected!r}"
        )

    @pytest.mark.parametrize("name", sorted(_XSD_STRING_LABEL_SHAPES))
    def test_xsd_string_label(self, name: str) -> None:
        pred = f"{_RDFS}label"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        expected = f"{_XSD}string"
        assert shex_spec.constraint_value == expected, (
            f"{name}: ShEx label datatype={shex_spec.constraint_value!r}, expected {expected!r}"
        )
        assert shacl_spec.constraint_value == expected, (
            f"{name}: SHACL label datatype={shacl_spec.constraint_value!r}, expected {expected!r}"
        )


class TestDatetimeOptional:
    """All xsd:dateTime properties in YAGO shapes are optional (max cardinality 1).
    Both ShEx (?) and SHACL (sh:maxCount 1) must normalise to max=1.
    """

    @pytest.mark.parametrize("name,pred", _DATETIME_OPTIONAL_CASES)
    def test_datetime_property_is_optional(self, name: str, pred: str) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)
        assert shex_spec.constraint_type == "datatype", (
            f"{name} {pred}: ShEx constraint_type={shex_spec.constraint_type!r}"
        )
        assert shex_spec.constraint_value == f"{_XSD}dateTime", (
            f"{name} {pred}: ShEx datatype={shex_spec.constraint_value!r}"
        )
        assert shex_spec.max == 1, (
            f"{name} {pred}: ShEx max={shex_spec.max!r}, expected 1 (optional)"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} {pred}")


class TestGeoConstraints:
    """Geographic shapes carry schema:geo with datatype geo:wktLiteral.
    The constraint must be optional (max=1) and identical in both formats.
    """

    @pytest.mark.parametrize("name", sorted(_GEO_SHAPES))
    def test_geo_wkt_literal_optional(self, name: str) -> None:
        pred = f"{_S}geo"
        shex_spec, shacl_spec = _pred_spec(name, pred)
        expected_dt = f"{_GEO}wktLiteral"
        assert shex_spec.constraint_type == "datatype", (
            f"{name}: ShEx schema:geo constraint_type={shex_spec.constraint_type!r}"
        )
        assert shex_spec.constraint_value == expected_dt, (
            f"{name}: ShEx schema:geo datatype={shex_spec.constraint_value!r}"
        )
        assert shex_spec.max == 1, (
            f"{name}: ShEx schema:geo max={shex_spec.max!r}, expected 1 (optional)"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} schema:geo")


class TestORClassConstraints:
    """Predicates constrained to an OR of classes (e.g. schema:Organization | schema:Person)
    must produce identical normalised class lists in both representations.
    """

    @pytest.mark.parametrize("name,pred,expected_classes", _OR_CLASS_CASES)
    def test_or_class_constraint_agrees(
        self, name: str, pred: str, expected_classes: list[str]
    ) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)

        assert shex_spec.constraint_type == "class", (
            f"{name} {pred}: ShEx constraint_type={shex_spec.constraint_type!r}, expected 'class'"
        )
        assert shacl_spec.constraint_type == "class", (
            f"{name} {pred}: SHACL constraint_type={shacl_spec.constraint_type!r}, expected 'class'"
        )
        assert shex_spec.constraint_value == sorted(expected_classes), (
            f"{name} {pred}: ShEx class list={shex_spec.constraint_value!r}"
        )
        assert shacl_spec.constraint_value == sorted(expected_classes), (
            f"{name} {pred}: SHACL class list={shacl_spec.constraint_value!r}"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} {pred}")


class TestIRINodeKind:
    """Predicates accepting any IRI (ShEx ``IRI`` / SHACL ``sh:nodeKind sh:IRI``)
    must produce nodeKind='IRI' in both normalised ShexJE schemas.
    """

    @pytest.mark.parametrize("name,pred", _IRI_NODEKIND_CASES)
    def test_iri_nodekind_agrees(self, name: str, pred: str) -> None:
        shex_spec, shacl_spec = _pred_spec(name, pred)

        assert shex_spec.constraint_type == "nodeKind", (
            f"{name} {pred}: ShEx constraint_type={shex_spec.constraint_type!r}, expected 'nodeKind'"
        )
        assert shex_spec.constraint_value == "IRI", (
            f"{name} {pred}: ShEx nodeKind={shex_spec.constraint_value!r}, expected 'IRI'"
        )
        _assert_spec_equal(shex_spec, shacl_spec, f"{name} {pred}")


class TestCardinality:
    """Cardinality semantics: ShEx quantifiers and SHACL sh:minCount/sh:maxCount
    must normalise to the same (min, max) pair in ShexJE.

    Conventions used by both converters:
      *  → (None, None)          zero-or-more (default)
      +  → (1, -1)               one-or-more
      ?  → (0, 1)                zero-or-one
     {1} → (1, 1)                exactly one (ShEx default, or explicit)
    """

    @pytest.mark.parametrize("name,pred,exp_min,exp_max", _CARDINALITY_CASES)
    def test_cardinality_agrees(
        self,
        name: str,
        pred: str,
        exp_min: Optional[int],
        exp_max: Optional[int],
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


class TestShapeSpotchecks:
    """Named per-property assertions for selected shapes.  These tests document
    concrete expected values and serve as regression anchors for the most
    important YAGO shapes.
    """

    # ── Person ────────────────────────────────────────────────────────────────

    def test_person_target_class_is_schema_person(self) -> None:
        target = next(iter(_shex_norm("Person")))
        assert target == f"{_S}Person"
        assert next(iter(_shacl_norm("Person"))) == f"{_S}Person"

    def test_person_birth_date_optional_datetime(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_S}birthDate")
        assert shex_s.constraint_type == "datatype"
        assert shex_s.constraint_value == f"{_XSD}dateTime"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_person_death_date_optional_datetime(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_S}deathDate")
        assert shex_s.constraint_type == "datatype"
        assert shex_s.constraint_value == f"{_XSD}dateTime"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_person_gender_optional_class_ref(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_S}gender")
        assert shex_s.constraint_type == "class"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_person_birth_place_optional_class_place(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_S}birthPlace")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == [f"{_S}Place"]
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_person_affiliation_unbounded_class_org(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_S}affiliation")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == [f"{_S}Organization"]
        assert shex_s.min is None or shex_s.min == 0
        assert shacl_s == shex_s

    def test_person_owns_iri_nodekind_unbounded(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_S}owns")
        assert shex_s.constraint_type == "nodeKind"
        assert shex_s.constraint_value == "IRI"
        assert shacl_s == shex_s

    def test_person_label_required_xsd_string(self) -> None:
        shex_s, shacl_s = _pred_spec("Person", f"{_RDFS}label")
        assert shex_s.constraint_value == f"{_XSD}string"
        assert shex_s.min == 1
        assert shacl_s == shex_s

    # ── Movie ─────────────────────────────────────────────────────────────────

    def test_movie_target_class_is_schema_movie(self) -> None:
        target = next(iter(_shex_norm("Movie")))
        assert target == f"{_S}Movie"
        assert next(iter(_shacl_norm("Movie"))) == f"{_S}Movie"

    def test_movie_label_lang_string_required(self) -> None:
        shex_s, shacl_s = _pred_spec("Movie", f"{_RDFS}label")
        assert shex_s.constraint_value == f"{_RDF}langString"
        assert shex_s.min == 1
        assert shacl_s == shex_s

    def test_movie_music_by_or_class_org_person(self) -> None:
        shex_s, shacl_s = _pred_spec("Movie", f"{_S}musicBy")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == sorted([f"{_S}Organization", f"{_S}Person"])
        assert shacl_s == shex_s

    def test_movie_author_or_class_org_person(self) -> None:
        shex_s, shacl_s = _pred_spec("Movie", f"{_S}author")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == sorted([f"{_S}Organization", f"{_S}Person"])
        assert shacl_s == shex_s

    def test_movie_about_iri_nodekind(self) -> None:
        shex_s, shacl_s = _pred_spec("Movie", f"{_S}about")
        assert shex_s.constraint_type == "nodeKind"
        assert shex_s.constraint_value == "IRI"
        assert shacl_s == shex_s

    def test_movie_duration_optional_decimal(self) -> None:
        shex_s, shacl_s = _pred_spec("Movie", f"{_S}duration")
        assert shex_s.constraint_type == "datatype"
        assert shex_s.constraint_value == f"{_XSD}decimal"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    # ── City ──────────────────────────────────────────────────────────────────

    def test_city_target_class_is_schema_city(self) -> None:
        target = next(iter(_shex_norm("City")))
        assert target == f"{_S}City"
        assert next(iter(_shacl_norm("City"))) == f"{_S}City"

    def test_city_main_entity_of_page_exactly_one(self) -> None:
        shex_s, shacl_s = _pred_spec("City", f"{_S}mainEntityOfPage")
        assert shex_s.min == 1
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_city_geo_optional_wkt_literal(self) -> None:
        shex_s, shacl_s = _pred_spec("City", f"{_S}geo")
        assert shex_s.constraint_type == "datatype"
        assert shex_s.constraint_value == f"{_GEO}wktLiteral"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_city_replaces_class_administrative_area(self) -> None:
        shex_s, shacl_s = _pred_spec("City", f"{_YAGO}replaces")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == [f"{_S}AdministrativeArea"]
        assert shacl_s == shex_s

    # ── Airline ───────────────────────────────────────────────────────────────

    def test_airline_owned_by_or_class_org_person(self) -> None:
        shex_s, shacl_s = _pred_spec("Airline", f"{_YAGO}ownedBy")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == sorted([f"{_S}Organization", f"{_S}Person"])
        assert shacl_s == shex_s

    def test_airline_iata_code_optional_string(self) -> None:
        shex_s, shacl_s = _pred_spec("Airline", f"{_S}iataCode")
        assert shex_s.constraint_type == "datatype"
        assert shex_s.constraint_value == f"{_XSD}string"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    # ── Award ─────────────────────────────────────────────────────────────────

    def test_award_about_optional_iri_nodekind(self) -> None:
        shex_s, shacl_s = _pred_spec("Award", f"{_S}about")
        assert shex_s.constraint_type == "nodeKind"
        assert shex_s.constraint_value == "IRI"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    def test_award_owned_by_or_class_org_person(self) -> None:
        shex_s, shacl_s = _pred_spec("Award", f"{_YAGO}ownedBy")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == sorted([f"{_S}Organization", f"{_S}Person"])
        assert shacl_s == shex_s

    # ── Election ──────────────────────────────────────────────────────────────

    def test_election_organizer_or_class(self) -> None:
        shex_s, shacl_s = _pred_spec("Election", f"{_S}organizer")
        assert shex_s.constraint_type == "class"
        assert sorted([f"{_S}Organization", f"{_S}Person"]) == shex_s.constraint_value
        assert shacl_s == shex_s

    def test_election_participant_or_class(self) -> None:
        shex_s, shacl_s = _pred_spec("Election", f"{_YAGO}participant")
        assert shex_s.constraint_type == "class"
        assert shex_s.constraint_value == sorted([f"{_S}Organization", f"{_S}Person"])
        assert shacl_s == shex_s

    def test_election_start_date_optional_datetime(self) -> None:
        shex_s, shacl_s = _pred_spec("Election", f"{_S}startDate")
        assert shex_s.constraint_value == f"{_XSD}dateTime"
        assert shex_s.max == 1
        assert shacl_s == shex_s

    # ── Gender ────────────────────────────────────────────────────────────────

    def test_gender_target_class_is_yago_gender(self) -> None:
        target = next(iter(_shex_norm("Gender")))
        assert target == f"{_YAGO}Gender"
        assert next(iter(_shacl_norm("Gender"))) == f"{_YAGO}Gender"

    def test_gender_label_required_lang_string(self) -> None:
        shex_s, shacl_s = _pred_spec("Gender", f"{_RDFS}label")
        assert shex_s.constraint_value == f"{_RDF}langString"
        assert shex_s.min == 1
        assert shacl_s == shex_s
