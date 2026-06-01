"""Verify every mapping rule documented in docs/mapping-rules.md.

Each test class corresponds to one section of the doc so that failures
trace directly to the violated rule.

Coverage:
  1.  Shape container and target class
  2.  Datatype constraint (sh:datatype)
  3.  Class reference (sh:class)
  4.  OR class constraint — property level (sh:or with sh:class)
  5.  Node kind (sh:nodeKind) — all six supported node kinds
  6.  Cardinality (sh:minCount / sh:maxCount) — all five table rows
  7.  Single-value constraint (sh:hasValue)
  8.  Enumerated values (sh:in)
  9.  IRI stem pattern (sh:pattern as sole constraint)
 10.  Combined datatype + pattern (sh:datatype + sh:pattern)
 11.  Non-standard sh:dataType (capital T, shexer compatibility)
 12a. Reusable value shapes — LangStringShape pattern (nodeKind + datatype)
 12b. Reusable value shapes — TimeZoneShape pattern (node-level value set)
 12c. Reusable value shapes — node-level nodeKind only
 13.  Named shape reference (sh:node)
 14.  Named value shapes — sh:or with datatype alternatives at NodeShape level
 15.  Property alternative groups — sh:or with sh:property items
 16.  Closed shapes
 17.  Alternative path (sh:alternativePath)
"""
from __future__ import annotations

import pytest

from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
from shaclex_py.parser.shacl_parser import parse_shacl
from shaclex_py.schema.common import UNBOUNDED, IriStem
from shaclex_py.schema.shex import (
    EachOf,
    NodeConstraint,
    NodeConstraintShape,
    OneOf,
    Shape,
    ShapeRef,
    TripleConstraint,
)
from shaclex_py.serializer.shex_serializer import serialize_shex

# ── Common prefixes prepended to every inline Turtle snippet ─────────────────

_PREFIXES = """\
@prefix sh:     <http://www.w3.org/ns/shacl#> .
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix schema: <http://schema.org/> .
@prefix dbo:    <http://dbpedia.org/ontology/> .
@prefix dbt:    <http://dbpedia.org/datatype/> .
@prefix dbr:    <http://dbpedia.org/resource/> .
@prefix shapes: <http://shaclshapes.org/> .
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_convert(ttl: str):
    """Parse inline Turtle SHACL and return the converted ShExSchema."""
    schema = parse_shacl(_PREFIXES + ttl)
    return convert_shacl_to_shex(schema)


def _shape(schema, name: str) -> Shape:
    """Return the shape with the given name; raise KeyError if absent."""
    for s in schema.shapes:
        if s.name.value == name:
            return s
    raise KeyError(f"Shape '{name}' not found; available: {[s.name.value for s in schema.shapes]}")


def _tcs(shape) -> list[TripleConstraint]:
    """Flatten all TripleConstraints out of a shape's expression."""
    return _flatten_expr(shape.expression)


def _flatten_expr(expr) -> list[TripleConstraint]:
    if expr is None:
        return []
    if isinstance(expr, TripleConstraint):
        return [expr]
    if isinstance(expr, (EachOf, OneOf)):
        result = []
        for sub in expr.expressions:
            result.extend(_flatten_expr(sub))
        return result
    return []


def _tc_by_pred(tcs: list[TripleConstraint], fragment: str) -> TripleConstraint:
    """Find the first TC whose predicate IRI contains *fragment*."""
    for tc in tcs:
        if fragment in tc.predicate.value:
            return tc
    raise KeyError(f"No TC with predicate containing '{fragment}' among {[t.predicate.value for t in tcs]}")


# ─────────────────────────────────────────────────────────────────────────────
# Rule 1 — Shape container and target class
# ─────────────────────────────────────────────────────────────────────────────

class TestShapeContainerAndTargetClass:
    TTL = """\
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:targetClass schema:Person .
"""

    def test_shape_name_strips_shape_suffix(self):
        """'PersonShape' IRI → ShEx shape named 'Person'."""
        schema = _parse_convert(self.TTL)
        assert any(s.name.value == "Person" for s in schema.shapes), (
            f"Expected shape 'Person'; got {[s.name.value for s in schema.shapes]}"
        )

    def test_target_class_becomes_rdf_type_triple_constraint(self):
        """sh:targetClass schema:Person → rdf:type [schema:Person] inside the shape body."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        all_tcs = _tcs(person)
        rdf_type_tcs = [t for t in all_tcs if "rdf-syntax-ns#type" in t.predicate.value]
        assert len(rdf_type_tcs) >= 1, "Expected an rdf:type triple constraint from sh:targetClass"

    def test_target_class_value_matches(self):
        """The value in the rdf:type constraint must be schema:Person."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "rdf-syntax-ns#type")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.values is not None and len(tc.constraint.values) >= 1
        val = tc.constraint.values[0].value
        assert hasattr(val, "value") and val.value == "http://schema.org/Person"

    def test_shape_has_extra_rdf_type(self):
        """Shape must carry EXTRA rdf:type."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        assert isinstance(person, Shape)
        extra_iris = [e.value for e in person.extra]
        assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in extra_iris, (
            f"EXTRA rdf:type missing; found EXTRA = {extra_iris}"
        )

    def test_serialised_output_contains_extra_rdf_type(self):
        """The serialised ShExC must contain 'EXTRA rdf:type'."""
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "EXTRA rdf:type" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — Datatype constraint (sh:datatype)
# ─────────────────────────────────────────────────────────────────────────────

class TestDatatypeConstraint:
    TTL = """\
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:birthDate ;
        sh:datatype xsd:date ;
        sh:maxCount 1 ;
    ] .
"""

    def test_tc_predicate_is_birth_date(self):
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "birthDate")
        assert "birthDate" in tc.predicate.value

    def test_datatype_is_xsd_date(self):
        """sh:datatype xsd:date → NodeConstraint(datatype=xsd:date)."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "birthDate")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.datatype is not None
        assert "XMLSchema#date" in tc.constraint.datatype.value

    def test_cardinality_is_optional_single(self):
        """sh:maxCount 1 (no minCount) → cardinality {0,1} → ShExC '?'."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "birthDate")
        assert tc.cardinality.effective_min == 0
        assert tc.cardinality.effective_max == 1
        assert tc.cardinality.to_shex_string() == " ?"

    def test_serialised_contains_question_mark(self):
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "?" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3 — Class reference (sh:class)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassReference:
    TTL = """\
<http://shaclshapes.org/CompanyShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:founder ;
        sh:class schema:Person ;
    ] .
"""

    def test_property_becomes_shape_ref(self):
        """sh:class schema:Person → @<Person> (a ShapeRef constraint)."""
        schema = _parse_convert(self.TTL)
        company = _shape(schema, "Company")
        tc = _tc_by_pred(_tcs(company), "founder")
        assert isinstance(tc.constraint, ShapeRef), (
            f"Expected ShapeRef constraint, got {type(tc.constraint)}"
        )

    def test_shape_ref_name_matches_class_local_name(self):
        """The ShapeRef name must be the local name of the class IRI."""
        schema = _parse_convert(self.TTL)
        company = _shape(schema, "Company")
        tc = _tc_by_pred(_tcs(company), "founder")
        assert isinstance(tc.constraint, ShapeRef)
        assert tc.constraint.name.value == "Person"

    def test_auxiliary_shape_created(self):
        """A companion 'Person' shape must appear in the output shapes."""
        schema = _parse_convert(self.TTL)
        shape_names = {s.name.value for s in schema.shapes}
        assert "Person" in shape_names, f"No 'Person' auxiliary shape; got {shape_names}"

    def test_auxiliary_shape_has_extra_rdf_type(self):
        """Auxiliary class shape must have EXTRA rdf:type."""
        schema = _parse_convert(self.TTL)
        person_aux = _shape(schema, "Person")
        assert isinstance(person_aux, Shape)
        extra_iris = [e.value for e in person_aux.extra]
        assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in extra_iris

    def test_auxiliary_shape_rdf_type_value_is_person(self):
        """Auxiliary shape body: rdf:type [ schema:Person ]."""
        schema = _parse_convert(self.TTL)
        person_aux = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person_aux), "rdf-syntax-ns#type")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.values is not None
        iris = [v.value.value for v in tc.constraint.values if hasattr(v.value, "value")]
        assert "http://schema.org/Person" in iris

    def test_multiple_properties_same_class_share_one_auxiliary_shape(self):
        """Two properties pointing to the same class must share one auxiliary shape (not two)."""
        ttl = """\
<http://shaclshapes.org/CompanyShape> a sh:NodeShape ;
    sh:property [ sh:path schema:founder ; sh:class schema:Person ] ;
    sh:property [ sh:path schema:employee ; sh:class schema:Person ] .
"""
        schema = _parse_convert(ttl)
        person_shapes = [s for s in schema.shapes if s.name.value == "Person"]
        assert len(person_shapes) == 1, (
            f"Expected exactly one 'Person' auxiliary shape; found {len(person_shapes)}"
        )

    def test_default_cardinality_is_star(self):
        """sh:class without min/maxCount → cardinality * (0 to unbounded)."""
        schema = _parse_convert(self.TTL)
        company = _shape(schema, "Company")
        tc = _tc_by_pred(_tcs(company), "founder")
        assert tc.cardinality.effective_min == 0
        assert tc.cardinality.effective_max is None  # unbounded
        assert tc.cardinality.to_shex_string() == " *"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 4 — OR class constraint — property level (sh:or with sh:class)
# ─────────────────────────────────────────────────────────────────────────────

class TestOrClassConstraint:
    TTL_STANDARD = """\
<http://shaclshapes.org/CompanyShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:founder ;
        sh:or ( [ sh:class schema:Organization ] [ sh:class schema:Person ] ) ;
    ] .
"""
    TTL_LEGACY = """\
<http://shaclshapes.org/CompanyShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:founder ;
        sh:class [ sh:or ( schema:Organization schema:Person ) ] ;
    ] .
"""

    def _companion_shape(self, schema):
        """Return the companion shape whose rdf:type TC has both class IRIs."""
        for s in schema.shapes:
            if s.name.value == "Company":
                continue
            tcs_list = _tcs(s)
            type_tcs = [t for t in tcs_list if "rdf-syntax-ns#type" in t.predicate.value]
            if type_tcs and isinstance(type_tcs[0].constraint, NodeConstraint):
                vals = type_tcs[0].constraint.values or []
                iris = {v.value.value for v in vals if hasattr(v.value, "value")}
                if "http://schema.org/Organization" in iris and "http://schema.org/Person" in iris:
                    return s
        return None

    def _assert_or_shape(self, schema):
        company = _shape(schema, "Company")
        founder_tc = _tc_by_pred(_tcs(company), "founder")

        # Must be a ShapeRef
        assert isinstance(founder_tc.constraint, ShapeRef), (
            f"Expected ShapeRef for sh:or, got {type(founder_tc.constraint)}"
        )

        # Companion shape must exist and contain both class IRIs
        companion = self._companion_shape(schema)
        assert companion is not None, "No companion shape found with both Organization and Person class IRIs"

        # Companion must have EXTRA rdf:type
        assert isinstance(companion, Shape)
        extra_iris = [e.value for e in companion.extra]
        assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in extra_iris

    def test_standard_form_creates_shape_ref(self):
        """Standard sh:or form → ShapeRef constraint."""
        schema = _parse_convert(self.TTL_STANDARD)
        self._assert_or_shape(schema)

    def test_legacy_form_creates_shape_ref(self):
        """Legacy sh:class [sh:or (...)] form → ShapeRef constraint (backwards compat)."""
        schema = _parse_convert(self.TTL_LEGACY)
        self._assert_or_shape(schema)

    def test_companion_shape_contains_both_class_iris(self):
        """Companion value shape must list both class IRIs in its rdf:type value set."""
        schema = _parse_convert(self.TTL_STANDARD)
        companion = self._companion_shape(schema)
        assert companion is not None
        type_tc = _tc_by_pred(_tcs(companion), "rdf-syntax-ns#type")
        vals = type_tc.constraint.values
        iris = {v.value.value for v in vals if hasattr(v.value, "value")}
        assert "http://schema.org/Organization" in iris
        assert "http://schema.org/Person" in iris

    def test_multiple_properties_same_classes_share_one_companion(self):
        """Two properties referencing the same OR-class combination share one companion shape."""
        ttl = """\
<http://shaclshapes.org/CompanyShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:founder ;
        sh:or ( [ sh:class schema:Organization ] [ sh:class schema:Person ] ) ;
    ] ;
    sh:property [
        sh:path schema:owner ;
        sh:or ( [ sh:class schema:Organization ] [ sh:class schema:Person ] ) ;
    ] .
"""
        schema = _parse_convert(ttl)
        companions = []
        for s in schema.shapes:
            if s.name.value == "Company":
                continue
            tcs_list = _tcs(s)
            type_tcs = [t for t in tcs_list if "rdf-syntax-ns#type" in t.predicate.value]
            if type_tcs and isinstance(type_tcs[0].constraint, NodeConstraint):
                vals = type_tcs[0].constraint.values or []
                iris = {v.value.value for v in vals if hasattr(v.value, "value")}
                if "http://schema.org/Organization" in iris and "http://schema.org/Person" in iris:
                    companions.append(s)
        assert len(companions) == 1, (
            f"Expected one shared companion shape, found {len(companions)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Rule 5 — Node kind (sh:nodeKind)
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeKind:
    _BASE = """\
<http://shaclshapes.org/SomeShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:url ;
        sh:nodeKind {kind} ;
    ] .
"""
    _KINDS = [
        ("sh:IRI",               "IRI"),
        ("sh:BlankNode",         "BlankNode"),
        ("sh:Literal",           "Literal"),
        ("sh:BlankNodeOrIRI",    "BlankNodeOrIRI"),
        ("sh:BlankNodeOrLiteral","BlankNodeOrLiteral"),
        ("sh:IRIOrLiteral",      "IRIOrLiteral"),
    ]

    @pytest.mark.parametrize("shacl_kind,expected_nk", _KINDS)
    def test_node_kind_mapped(self, shacl_kind, expected_nk):
        """sh:nodeKind {shacl_kind} → NodeConstraint(node_kind=NodeKind.{expected_nk})."""
        ttl = self._BASE.format(kind=shacl_kind)
        schema = _parse_convert(ttl)
        some = _shape(schema, "Some")
        tc = _tc_by_pred(_tcs(some), "url")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.node_kind is not None
        assert tc.constraint.node_kind.value == expected_nk, (
            f"Expected NodeKind.{expected_nk}, got {tc.constraint.node_kind}"
        )

    def test_iri_serialised_as_IRI_keyword(self):
        """sh:nodeKind sh:IRI serialises to 'IRI' in ShExC."""
        ttl = self._BASE.format(kind="sh:IRI")
        schema = _parse_convert(ttl)
        text = serialize_shex(schema)
        assert "IRI" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 6 — Cardinality
# ─────────────────────────────────────────────────────────────────────────────

class TestCardinality:
    """Verify all five cardinality table rows from the mapping-rules doc."""

    _BASE = """\
<http://shaclshapes.org/SomeShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:name ;
        sh:datatype xsd:string ;
        {card}
    ] .
"""

    def _tc(self, card_snippet: str) -> TripleConstraint:
        ttl = self._BASE.format(card=card_snippet)
        schema = _parse_convert(ttl)
        some = _shape(schema, "Some")
        return _tc_by_pred(_tcs(some), "name")

    def test_no_count_maps_to_star(self):
        """(none) → {0,*} → ShExC '*'."""
        tc = self._tc("")
        assert tc.cardinality.effective_min == 0
        assert tc.cardinality.effective_max is None
        assert tc.cardinality.to_shex_string() == " *"

    def test_min0_max1_maps_to_question_mark(self):
        """sh:minCount 0 ; sh:maxCount 1 → {0,1} → ShExC '?'."""
        tc = self._tc("sh:minCount 0 ; sh:maxCount 1 ;")
        assert tc.cardinality.effective_min == 0
        assert tc.cardinality.effective_max == 1
        assert tc.cardinality.to_shex_string() == " ?"

    def test_min1_maps_to_plus(self):
        """sh:minCount 1 (no maxCount) → {1,*} → ShExC '+'."""
        tc = self._tc("sh:minCount 1 ;")
        assert tc.cardinality.effective_min == 1
        assert tc.cardinality.effective_max is None
        assert tc.cardinality.to_shex_string() == " +"

    def test_min1_max1_maps_to_empty_suffix(self):
        """sh:minCount 1 ; sh:maxCount 1 → {1,1} → ShExC '' (no suffix)."""
        tc = self._tc("sh:minCount 1 ; sh:maxCount 1 ;")
        assert tc.cardinality.effective_min == 1
        assert tc.cardinality.effective_max == 1
        assert tc.cardinality.to_shex_string() == ""

    def test_explicit_range_preserved(self):
        """sh:minCount 2 ; sh:maxCount 5 → {2,5} → ShExC '{2,5}'."""
        tc = self._tc("sh:minCount 2 ; sh:maxCount 5 ;")
        assert tc.cardinality.effective_min == 2
        assert tc.cardinality.effective_max == 5
        assert tc.cardinality.to_shex_string() == " {2,5}"

    def test_serialised_cardinalities(self):
        """All five cardinality variants are present in separate shapes."""
        cases = [
            ("", " *"),
            ("sh:minCount 0 ; sh:maxCount 1 ;", " ?"),
            ("sh:minCount 1 ;", " +"),
            ("sh:minCount 1 ; sh:maxCount 1 ;", ""),
            ("sh:minCount 2 ; sh:maxCount 5 ;", " {2,5}"),
        ]
        for snippet, expected_shex in cases:
            tc = self._tc(snippet)
            assert tc.cardinality.to_shex_string() == expected_shex, (
                f"Cardinality snippet '{snippet}' → expected '{expected_shex}', "
                f"got '{tc.cardinality.to_shex_string()}'"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Rule 7 — Single-value constraint (sh:hasValue)
# ─────────────────────────────────────────────────────────────────────────────

class TestHasValue:
    TTL = """\
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:property [
        sh:path rdf:type ;
        sh:hasValue schema:Person ;
    ] .
"""

    def test_has_value_becomes_value_set(self):
        """sh:hasValue schema:Person → NodeConstraint with value set [schema:Person]."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "rdf-syntax-ns#type")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.values is not None and len(tc.constraint.values) == 1

    def test_has_value_value_is_correct_iri(self):
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "rdf-syntax-ns#type")
        val = tc.constraint.values[0].value
        assert hasattr(val, "value") and val.value == "http://schema.org/Person"

    def test_default_cardinality_is_star(self):
        """sh:hasValue without min/maxCount → '*' (SHACL default {0,*})."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "rdf-syntax-ns#type")
        assert tc.cardinality.to_shex_string() == " *"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 8 — Enumerated values (sh:in)
# ─────────────────────────────────────────────────────────────────────────────

class TestEnumeratedValues:
    TTL = """\
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:gender ;
        sh:in ( schema:Male schema:Female ) ;
    ] .
"""

    def test_in_becomes_value_set(self):
        """sh:in (v1 v2) → NodeConstraint with two-element value set."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "gender")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.values is not None and len(tc.constraint.values) == 2

    def test_in_values_contain_correct_iris(self):
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "gender")
        iris = {v.value.value for v in tc.constraint.values if hasattr(v.value, "value")}
        assert "http://schema.org/Male" in iris
        assert "http://schema.org/Female" in iris

    def test_serialised_as_value_set_brackets(self):
        """ShExC output must contain '[ schema:Male schema:Female ]' (or equivalent)."""
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "schema:Male" in text and "schema:Female" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 9 — IRI stem pattern (sh:pattern as sole constraint)
# ─────────────────────────────────────────────────────────────────────────────

class TestIriStemPattern:
    TTL = """\
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:property [
        sh:path schema:sameAs ;
        sh:pattern "^http://www.wikidata.org/entity/" ;
    ] .
"""

    def test_url_pattern_becomes_iri_stem(self):
        """sh:pattern '^http://...' (sole constraint) → IriStem value in value set."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "sameAs")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.values is not None and len(tc.constraint.values) == 1
        val = tc.constraint.values[0].value
        assert isinstance(val, IriStem), f"Expected IriStem, got {type(val)}"

    def test_iri_stem_value_strips_trailing_slash(self):
        """The stem value must not include the trailing '/' from the pattern."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        tc = _tc_by_pred(_tcs(person), "sameAs")
        stem = tc.constraint.values[0].value
        assert isinstance(stem, IriStem)
        assert stem.stem == "http://www.wikidata.org/entity"

    def test_serialised_as_iri_stem_tilde(self):
        """ShExC serialisation must use the '<stem>~' notation."""
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "wikidata.org/entity>~" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 10 — Combined datatype + pattern (sh:datatype + sh:pattern)
# ─────────────────────────────────────────────────────────────────────────────

class TestCombinedDatatypeAndPattern:
    TTL = """\
<http://shaclshapes.org/SomeShape> a sh:NodeShape ;
    sh:property [
        sh:path dbo:wikiPageRedirects ;
        sh:datatype xsd:anyURI ;
        sh:pattern "^http://dbpedia.org/resource/" ;
    ] .
"""

    def test_datatype_preserved(self):
        """sh:datatype xsd:anyURI is present in the NodeConstraint."""
        schema = _parse_convert(self.TTL)
        some = _shape(schema, "Some")
        tc = _tc_by_pred(_tcs(some), "wikiPageRedirects")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.datatype is not None
        assert "anyURI" in tc.constraint.datatype.value

    def test_pattern_preserved_alongside_datatype(self):
        """When both sh:datatype and sh:pattern are present, pattern is additive."""
        schema = _parse_convert(self.TTL)
        some = _shape(schema, "Some")
        tc = _tc_by_pred(_tcs(some), "wikiPageRedirects")
        assert isinstance(tc.constraint, NodeConstraint)
        assert tc.constraint.pattern is not None, "Pattern must be preserved alongside datatype"
        assert "dbpedia.org" in tc.constraint.pattern

    def test_serialised_contains_datatype_and_pattern_facet(self):
        """ShExC output must contain both the datatype and /regex/ pattern facet.

        The pattern facet is serialised immediately after the datatype, e.g.:
            dbo:wikiPageRedirects xsd:anyURI /^http:\\/\\/dbpedia.org\\/resource\\// *

        The key indicator is that the datatype is followed by ' /' (start of
        pattern facet).  'dbpedia.org' alone is insufficient because it also
        appears in the PREFIX declarations.
        """
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "anyURI" in text
        # The pattern facet must follow the datatype — 'anyURI /' only appears
        # in the shape body when the pattern is correctly preserved.
        assert "anyURI /" in text, (
            "Pattern facet missing from serialised output: the combined "
            "sh:datatype + sh:pattern constraint must emit 'dtype /regex/' in ShExC"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Rule 11 — Non-standard sh:dataType (capital T) — shexer compatibility
# ─────────────────────────────────────────────────────────────────────────────

class TestNonStandardDatatypeCapitalT:
    TTL = """\
<http://shaclshapes.org/SomeShape> a sh:NodeShape ;
    sh:property [
        sh:path dbo:populationTotal ;
        <http://www.w3.org/ns/shacl#dataType> xsd:integer ;
    ] .
"""

    def test_capital_T_datatype_accepted_and_normalised(self):
        """sh:dataType (capital T) must be normalised to the same canonical datatype field."""
        schema = _parse_convert(self.TTL)
        some = _shape(schema, "Some")
        tc = _tc_by_pred(_tcs(some), "populationTotal")
        assert isinstance(tc.constraint, NodeConstraint), (
            "sh:dataType (capital T) must produce a NodeConstraint with a datatype"
        )
        assert tc.constraint.datatype is not None
        assert "integer" in tc.constraint.datatype.value


# ─────────────────────────────────────────────────────────────────────────────
# Rule 12a — Reusable value shapes: LangStringShape (nodeKind + datatype)
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeLevelLangStringShape:
    TTL = """\
shapes:LangStringShape a sh:NodeShape ;
    sh:nodeKind sh:Literal ;
    sh:datatype rdf:langString .

shapes:ArticleShape a sh:NodeShape ;
    sh:targetClass schema:Article ;
    sh:property [
        sh:path dbo:abstract ;
        sh:node shapes:LangStringShape ;
        sh:minCount 1 ;
    ] .
"""

    def test_lang_string_shape_parsed_as_node_constraint_shape(self):
        """LangStringShape (nodeKind + datatype at NodeShape level) → NodeConstraintShape."""
        schema = _parse_convert(self.TTL)
        ncs = [s for s in schema.shapes if isinstance(s, NodeConstraintShape)]
        names = {s.name.value for s in ncs}
        assert "LangString" in names, (
            f"Expected NodeConstraintShape 'LangString'; found {names}"
        )

    def test_lang_string_shape_datatype_is_langstring(self):
        """LangStringShape datatype → rdf:langString."""
        schema = _parse_convert(self.TTL)
        lang = next(
            (s for s in schema.shapes
             if isinstance(s, NodeConstraintShape) and s.name.value == "LangString"),
            None,
        )
        assert lang is not None
        assert lang.datatype is not None
        assert "langString" in lang.datatype.value

    def test_article_abstract_references_lang_string_shape(self):
        """sh:node shapes:LangStringShape → @<LangString> shape reference."""
        schema = _parse_convert(self.TTL)
        article = _shape(schema, "Article")
        tc = _tc_by_pred(_tcs(article), "abstract")
        assert isinstance(tc.constraint, ShapeRef), (
            f"Expected ShapeRef to LangStringShape, got {type(tc.constraint)}"
        )
        assert "LangString" in tc.constraint.name.value


# ─────────────────────────────────────────────────────────────────────────────
# Rule 12b — Reusable value shapes: TimeZoneShape (node-level value set)
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeLevelTimeZoneShape:
    TTL = """\
shapes:TimeZoneShape a sh:NodeShape ;
    sh:in ( dbr:Eastern_Time_Zone dbr:Indian_Standard_Time dbr:Central_Time_Zone ) .

shapes:CityShape a sh:NodeShape ;
    sh:property [
        sh:path dbo:timeZone ;
        sh:node shapes:TimeZoneShape ;
    ] .
"""

    def test_timezone_shape_parsed_as_node_constraint_shape(self):
        """TimeZoneShape (sh:in at NodeShape level) → NodeConstraintShape."""
        schema = _parse_convert(self.TTL)
        ncs = [s for s in schema.shapes if isinstance(s, NodeConstraintShape)]
        names = {s.name.value for s in ncs}
        assert "TimeZone" in names, (
            f"Expected NodeConstraintShape 'TimeZone'; found {names}"
        )

    def test_timezone_shape_has_three_values(self):
        schema = _parse_convert(self.TTL)
        tz = next(
            (s for s in schema.shapes
             if isinstance(s, NodeConstraintShape) and s.name.value == "TimeZone"),
            None,
        )
        assert tz is not None
        assert tz.values is not None and len(tz.values) == 3

    def test_timezone_shape_value_iris_correct(self):
        schema = _parse_convert(self.TTL)
        tz = next(
            (s for s in schema.shapes
             if isinstance(s, NodeConstraintShape) and s.name.value == "TimeZone"),
            None,
        )
        iris = {v.value.value for v in tz.values if hasattr(v.value, "value")}
        assert "http://dbpedia.org/resource/Eastern_Time_Zone" in iris
        assert "http://dbpedia.org/resource/Indian_Standard_Time" in iris
        assert "http://dbpedia.org/resource/Central_Time_Zone" in iris


# ─────────────────────────────────────────────────────────────────────────────
# Rule 12c — Reusable value shapes: node-level nodeKind only
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeLevelNodeKindOnly:
    TTL = """\
shapes:IRIShape a sh:NodeShape ;
    sh:nodeKind sh:IRI .
"""

    def test_iri_shape_parsed_as_node_constraint_shape(self):
        """sh:nodeKind sh:IRI at NodeShape level → NodeConstraintShape with IRI kind.

        The 'Shape' suffix is stripped from the IRI local name ('IRIShape' → 'IRI'),
        consistent with the stripping applied to LangStringShape → 'LangString', etc.
        """
        schema = _parse_convert(self.TTL)
        ncs = [s for s in schema.shapes if isinstance(s, NodeConstraintShape)]
        names = {s.name.value for s in ncs}
        assert "IRI" in names, f"Expected NodeConstraintShape 'IRI' (Shape suffix stripped); found {names}"

    def test_iri_shape_node_kind_is_iri(self):
        from shaclex_py.schema.common import NodeKind
        schema = _parse_convert(self.TTL)
        iri_shape = next(
            (s for s in schema.shapes
             if isinstance(s, NodeConstraintShape) and s.name.value == "IRI"),
            None,
        )
        assert iri_shape is not None, "No NodeConstraintShape named 'IRI' found"
        assert iri_shape.node_kind == NodeKind.IRI

    def test_iri_shape_serialised_as_IRI_keyword(self):
        """<IRI> IRI must appear in the serialised ShExC (Shape suffix stripped)."""
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "<IRI> IRI" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 13 — Named shape reference (sh:node)
# ─────────────────────────────────────────────────────────────────────────────

class TestNamedShapeReference:
    TTL = """\
shapes:costValueShape a sh:NodeShape ;
    sh:datatype dbt:usDollar .

shapes:FilmShape a sh:NodeShape ;
    sh:property [
        sh:path dbo:cost ;
        sh:node shapes:costValueShape ;
    ] .
"""

    def test_sh_node_becomes_shape_ref(self):
        """sh:node shapes:costValueShape → @<costValue> ShapeRef."""
        schema = _parse_convert(self.TTL)
        film = _shape(schema, "Film")
        tc = _tc_by_pred(_tcs(film), "cost")
        assert isinstance(tc.constraint, ShapeRef), (
            f"Expected ShapeRef for sh:node, got {type(tc.constraint)}"
        )

    def test_shape_ref_name_strips_shape_suffix(self):
        """The referenced shape name has 'Shape' stripped from the local name."""
        schema = _parse_convert(self.TTL)
        film = _shape(schema, "Film")
        tc = _tc_by_pred(_tcs(film), "cost")
        assert isinstance(tc.constraint, ShapeRef)
        assert "costValue" in tc.constraint.name.value

    def test_default_cardinality_is_star(self):
        """sh:node without min/maxCount → '*' (SHACL default {0,*})."""
        schema = _parse_convert(self.TTL)
        film = _shape(schema, "Film")
        tc = _tc_by_pred(_tcs(film), "cost")
        assert tc.cardinality.to_shex_string() == " *"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 14 — Named value shapes: sh:or with datatype alternatives at NodeShape level
# ─────────────────────────────────────────────────────────────────────────────

class TestOrDatatypeAlternativesAtNodeShapeLevel:
    TTL = """\
shapes:costValueShape a sh:NodeShape ;
    sh:or (
        [ sh:datatype dbt:usDollar ]
        [ sh:datatype dbt:euro ]
        [ sh:datatype dbt:poundSterling ]
    ) .

shapes:FilmShape a sh:NodeShape ;
    sh:property [
        sh:path dbo:cost ;
        sh:node shapes:costValueShape ;
    ] .
"""

    def test_or_datatypes_shape_is_node_constraint_shape(self):
        """sh:or of sh:datatype alternatives → NodeConstraintShape (OR-of-datatypes)."""
        schema = _parse_convert(self.TTL)
        ncs = [s for s in schema.shapes if isinstance(s, NodeConstraintShape)]
        names = {s.name.value for s in ncs}
        assert "costValue" in names, (
            f"Expected NodeConstraintShape 'costValue'; found {names}"
        )

    def test_three_datatypes_present(self):
        """All three datatype IRIs are preserved in declaration order."""
        schema = _parse_convert(self.TTL)
        cost = next(
            (s for s in schema.shapes
             if isinstance(s, NodeConstraintShape) and s.name.value == "costValue"),
            None,
        )
        assert cost is not None
        assert len(cost.datatypes) == 3

    def test_datatype_order_preserved(self):
        """Declaration order must be preserved (not sorted alphabetically)."""
        schema = _parse_convert(self.TTL)
        cost = next(
            (s for s in schema.shapes
             if isinstance(s, NodeConstraintShape) and s.name.value == "costValue"),
            None,
        )
        names = [dt.value.rsplit("/", 1)[-1] for dt in cost.datatypes]
        assert names == ["usDollar", "euro", "poundSterling"], (
            f"Order not preserved; got {names}"
        )

    def test_serialised_as_or_of_datatypes(self):
        """ShExC must contain 'dbt:usDollar OR dbt:euro OR dbt:poundSterling' (or similar)."""
        schema = _parse_convert(self.TTL)
        text = serialize_shex(schema)
        assert "OR" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 15 — Property alternative groups (sh:or with sh:property items)
# ─────────────────────────────────────────────────────────────────────────────

class TestPropertyAlternativeGroups:
    TTL = """\
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:or (
        [
            sh:property [
                sh:path dbo:height ;
                sh:datatype dbt:centimetre ;
                sh:maxCount 1 ;
            ]
        ]
        [
            sh:property [
                sh:path <http://dbpedia.org/ontology/Person/height> ;
                sh:datatype dbt:centimetre ;
                sh:maxCount 1 ;
            ]
        ]
    ) .
"""

    def test_both_properties_present_in_converted_shape(self):
        """Both alternative property paths appear in the converted ShEx shape."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        all_tcs = _tcs(person)
        pred_iris = {tc.predicate.value for tc in all_tcs}
        assert "http://dbpedia.org/ontology/height" in pred_iris, (
            f"dbo:height missing from {pred_iris}"
        )
        assert "http://dbpedia.org/ontology/Person/height" in pred_iris, (
            f"dbo:Person/height missing from {pred_iris}"
        )

    def test_datatype_preserved_for_both_alternatives(self):
        """Both alternative TCs carry the correct datatype."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        for tc in _tcs(person):
            if "height" in tc.predicate.value:
                assert isinstance(tc.constraint, NodeConstraint)
                assert tc.constraint.datatype is not None
                assert "centimetre" in tc.constraint.datatype.value

    def test_max_count_preserved(self):
        """sh:maxCount 1 is preserved for both alternatives."""
        schema = _parse_convert(self.TTL)
        person = _shape(schema, "Person")
        for tc in _tcs(person):
            if "height" in tc.predicate.value:
                assert tc.cardinality.effective_max == 1


# ─────────────────────────────────────────────────────────────────────────────
# Rule 16 — Closed shapes
# ─────────────────────────────────────────────────────────────────────────────

class TestClosedShapes:
    TTL_CLOSED = """\
<http://shaclshapes.org/UserShape> a sh:NodeShape ;
    sh:closed true ;
    sh:property [ sh:path schema:name ; sh:datatype xsd:string ] .
"""
    TTL_OPEN = """\
<http://shaclshapes.org/UserShape> a sh:NodeShape ;
    sh:property [ sh:path schema:name ; sh:datatype xsd:string ] .
"""

    def test_closed_true_maps_to_closed_flag(self):
        """sh:closed true → Shape(closed=True)."""
        schema = _parse_convert(self.TTL_CLOSED)
        user = _shape(schema, "User")
        assert isinstance(user, Shape)
        assert user.closed is True

    def test_no_closed_maps_to_not_closed(self):
        """Absent sh:closed → Shape(closed=False)."""
        schema = _parse_convert(self.TTL_OPEN)
        user = _shape(schema, "User")
        assert isinstance(user, Shape)
        assert user.closed is False

    def test_closed_shape_has_extra_rdf_type(self):
        """Closed shape still carries EXTRA rdf:type."""
        schema = _parse_convert(self.TTL_CLOSED)
        user = _shape(schema, "User")
        extra_iris = [e.value for e in user.extra]
        assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in extra_iris

    def test_serialised_contains_closed_keyword(self):
        """ShExC must contain the 'CLOSED' keyword."""
        schema = _parse_convert(self.TTL_CLOSED)
        text = serialize_shex(schema)
        assert "CLOSED" in text

    def test_serialised_has_extra_rdf_type_and_closed(self):
        """ShExC must contain both 'EXTRA rdf:type' and 'CLOSED'."""
        schema = _parse_convert(self.TTL_CLOSED)
        text = serialize_shex(schema)
        assert "EXTRA rdf:type" in text
        assert "CLOSED" in text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 17 — Alternative path (sh:alternativePath)
# ─────────────────────────────────────────────────────────────────────────────

class TestAlternativePath:
    TTL = """\
<http://shaclshapes.org/OrganizationShape> a sh:NodeShape ;
    sh:property [
        sh:path [ sh:alternativePath ( dbo:foundingDate dbo:formationDate dbo:openingDate ) ] ;
        sh:datatype xsd:date ;
        sh:minCount 1 ;
    ] .
"""

    def test_alternative_path_expands_to_multiple_tcs(self):
        """sh:alternativePath (p1 p2 p3) → at least three separate TCs (one per path)."""
        schema = _parse_convert(self.TTL)
        org = _shape(schema, "Organization")
        all_tcs = _tcs(org)
        # Each alternative path becomes its own TC
        date_tcs = [tc for tc in all_tcs if "Date" in tc.predicate.value or "date" in tc.predicate.value]
        assert len(date_tcs) >= 3, (
            f"Expected >=3 TCs for 3 alternative paths, got {len(date_tcs)}: "
            f"{[tc.predicate.value for tc in date_tcs]}"
        )

    def test_all_alternative_path_predicates_present(self):
        """Each alternative path predicate must be represented."""
        schema = _parse_convert(self.TTL)
        org = _shape(schema, "Organization")
        pred_iris = {tc.predicate.value for tc in _tcs(org)}
        assert "http://dbpedia.org/ontology/foundingDate" in pred_iris, f"foundingDate missing from {pred_iris}"
        assert "http://dbpedia.org/ontology/formationDate" in pred_iris, f"formationDate missing from {pred_iris}"
        assert "http://dbpedia.org/ontology/openingDate" in pred_iris, f"openingDate missing from {pred_iris}"

    def test_alternative_path_datatype_preserved_for_each(self):
        """All alternative-path TCs carry the same datatype (xsd:date)."""
        schema = _parse_convert(self.TTL)
        org = _shape(schema, "Organization")
        date_preds = {
            "http://dbpedia.org/ontology/foundingDate",
            "http://dbpedia.org/ontology/formationDate",
            "http://dbpedia.org/ontology/openingDate",
        }
        for tc in _tcs(org):
            if tc.predicate.value in date_preds:
                assert isinstance(tc.constraint, NodeConstraint), (
                    f"Expected NodeConstraint for {tc.predicate.value}"
                )
                assert tc.constraint.datatype is not None
                assert "XMLSchema#date" in tc.constraint.datatype.value

    def test_alternative_path_cardinality_preserved(self):
        """sh:minCount 1 is preserved for each alternative-path TC."""
        schema = _parse_convert(self.TTL)
        org = _shape(schema, "Organization")
        date_preds = {
            "http://dbpedia.org/ontology/foundingDate",
            "http://dbpedia.org/ontology/formationDate",
            "http://dbpedia.org/ontology/openingDate",
        }
        for tc in _tcs(org):
            if tc.predicate.value in date_preds:
                assert tc.cardinality.effective_min == 1, (
                    f"Expected min=1 for {tc.predicate.value}, got {tc.cardinality.effective_min}"
                )

    def test_expression_uses_oneof_for_alternatives(self):
        """The triple expression must use OneOf (|) to represent alternatives."""
        schema = _parse_convert(self.TTL)
        org = _shape(schema, "Organization")
        assert isinstance(org.expression, OneOf), (
            f"Expected OneOf expression for sh:alternativePath, got {type(org.expression)}"
        )
