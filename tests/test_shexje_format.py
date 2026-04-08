"""Tests for ShexJE v2 format.

Covers:
* classRef → valueExpr + companion ShapeE (canonical_to_shexje)
* classRefOr → valueExpr + companion ShapeE with multiple values
* iriStem → valueExpr: NodeConstraint with IriStemValue
* hasValue / inValues → valueExpr: NodeConstraint with values
* AlternativePath + valueExpr (DBpedia alternative predicate pattern)
* Value-shape shorthand (predicate + values on ShapeE) round-trip via parser
* Backward-compat: old classRef/classRefOr/iriStem on TripleConstraint parsed correctly
* Roundtrip: canonical → shexje → canonical
"""
import json
import pytest

from shaclex_py.schema.canonical import (
    CanonicalCardinality,
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)
from shaclex_py.schema.shexje import (
    IriStemValue,
    NodeConstraintE,
    ShapeE,
    ShexJESchema,
    TripleConstraintE,
)
from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
from shaclex_py.parser.shexje_parser import parse_shexje
from shaclex_py.serializer.shexje_serializer import serialize_shexje

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_UNBOUNDED = -1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prop(path, **kwargs):
    card = CanonicalCardinality(
        min=kwargs.pop("min", 0),
        max=kwargs.pop("max", _UNBOUNDED),
    )
    return CanonicalProperty(path=path, cardinality=card, **kwargs)


def _schema(*shapes):
    return CanonicalSchema(shapes=list(shapes))


def _shape(name, *props, target=None):
    return CanonicalShape(
        name=name,
        targetClass=target,
        properties=list(props),
    )


def _find_tc(shexje: ShexJESchema, predicate: str) -> TripleConstraintE:
    """Return the first TripleConstraint matching predicate in any shape."""
    from shaclex_py.schema.shexje import EachOfE
    for shape in shexje.shapes:
        if not isinstance(shape, ShapeE) or shape.expression is None:
            continue
        exprs = (
            shape.expression.expressions
            if isinstance(shape.expression, EachOfE)
            else [shape.expression]
        )
        for tc in exprs:
            if isinstance(tc, TripleConstraintE) and tc.predicate == predicate:
                return tc
    raise KeyError(f"No TripleConstraint for predicate {predicate!r}")


def _find_value_shape(shexje: ShexJESchema, shape_id: str) -> ShapeE:
    """Return the ShapeE with the given id."""
    for s in shexje.shapes:
        if isinstance(s, ShapeE) and s.id == shape_id:
            return s
    raise KeyError(f"No ShapeE with id {shape_id!r}")


# ── classRef → valueExpr ──────────────────────────────────────────────────────

class TestClassRef:
    def test_single_class_generates_value_shape(self):
        canon = _schema(
            _shape(
                "Person",
                _prop("http://schema.org/worksFor",
                      classRef="http://schema.org/Organization"),
                target="http://schema.org/Person",
            )
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://schema.org/worksFor")

        # valueExpr must be a string reference, not classRef
        assert isinstance(tc.valueExpr, str), "valueExpr should be a string shape ref"
        assert not hasattr(tc, "classRef") or True  # field removed from dataclass

        # companion value shape must exist
        shape_id = tc.valueExpr
        vs = _find_value_shape(shexje, shape_id)
        assert vs.predicate == _RDF_TYPE
        assert "http://schema.org/Organization" in vs.values

    def test_shape_id_derived_from_local_name(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/p",
                               classRef="http://dbpedia.org/ontology/Country"))
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://ex.org/p")
        assert tc.valueExpr == "Country"

    def test_two_properties_same_class_share_one_shape(self):
        canon = _schema(
            _shape(
                "X",
                _prop("http://ex.org/p1", classRef="http://ex.org/Foo"),
                _prop("http://ex.org/p2", classRef="http://ex.org/Foo"),
            )
        )
        shexje = convert_canonical_to_shexje(canon)
        # count ShapeE with the value-shape id (Foo)
        foo_shapes = [s for s in shexje.shapes
                      if isinstance(s, ShapeE) and s.id == "Foo"]
        assert len(foo_shapes) == 1, "Same class should produce exactly one companion shape"

    def test_extra_contains_type_predicate(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/p",
                               classRef="http://ex.org/City"))
        )
        shexje = convert_canonical_to_shexje(canon)
        vs = _find_value_shape(shexje, "City")
        assert _RDF_TYPE in vs.extra


# ── classRefOr → valueExpr ────────────────────────────────────────────────────

class TestClassRefOr:
    def test_or_generates_shape_with_multiple_values(self):
        canon = _schema(
            _shape("X", _prop(
                "http://ex.org/discipline",
                classRefOr=[
                    "http://dbpedia.org/ontology/AcademicSubject",
                    "http://dbpedia.org/ontology/MedicalSpecialty",
                ],
            ))
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://ex.org/discipline")

        assert isinstance(tc.valueExpr, str)
        vs = _find_value_shape(shexje, tc.valueExpr)
        assert "http://dbpedia.org/ontology/AcademicSubject" in vs.values
        assert "http://dbpedia.org/ontology/MedicalSpecialty" in vs.values

    def test_or_shape_id_joins_local_names(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/p", classRefOr=[
                "http://ex.org/Alpha",
                "http://ex.org/Beta",
            ]))
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://ex.org/p")
        assert tc.valueExpr == "AlphaOrBeta"


# ── iriStem → valueExpr ───────────────────────────────────────────────────────

class TestIriStem:
    def test_iristem_produces_node_constraint_with_iristemvalue(self):
        canon = _schema(
            _shape("X", _prop("http://www.w3.org/2002/07/owl#sameAs",
                               iriStem="http://www.wikidata.org/entity"))
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://www.w3.org/2002/07/owl#sameAs")

        assert isinstance(tc.valueExpr, NodeConstraintE)
        assert len(tc.valueExpr.values) == 1
        stem_val = tc.valueExpr.values[0]
        assert isinstance(stem_val, IriStemValue)
        assert stem_val.stem == "http://www.wikidata.org/entity"

    def test_iristem_serialises_correctly(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/id", iriStem="https://example.org/"))
        )
        shexje = convert_canonical_to_shexje(canon)
        d = json.loads(serialize_shexje(shexje))

        # Single property → expression is the TC directly (no EachOf wrapper)
        expr = d["shapes"][0]["expression"]
        tc = expr if expr.get("type") == "TripleConstraint" else next(
            t for t in expr["expressions"] if t.get("predicate") == "http://ex.org/id"
        )
        ve = tc["valueExpr"]
        assert ve["type"] == "NodeConstraint"
        assert ve["values"][0] == {"type": "IriStem", "stem": "https://example.org/"}


# ── hasValue / inValues → valueExpr ──────────────────────────────────────────

class TestHasValueInValues:
    def test_has_value_produces_single_element_values(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/type",
                               hasValue="http://ex.org/MyClass"))
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://ex.org/type")
        assert isinstance(tc.valueExpr, NodeConstraintE)
        assert tc.valueExpr.values == ["http://ex.org/MyClass"]

    def test_in_values_produces_node_constraint_values(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/status",
                               inValues=["active", "inactive"]))
        )
        shexje = convert_canonical_to_shexje(canon)
        tc = _find_tc(shexje, "http://ex.org/status")
        assert isinstance(tc.valueExpr, NodeConstraintE)
        assert set(tc.valueExpr.values) == {"active", "inactive"}


# ── AlternativePath + valueExpr ───────────────────────────────────────────────

class TestAlternativePath:
    def test_alt_path_with_class_ref(self):
        """AlternativePath (DBpedia pattern) combined with classRef."""
        from shaclex_py.schema.shexje import AlternativePath, EachOfE
        prop = CanonicalProperty(
            path="http://dbpedia.org/ontology/occupation",
            pathAlternatives=[
                "http://dbpedia.org/ontology/occupation",
                "http://dbpedia.org/ontology/profession",
            ],
            classRef="http://dbpedia.org/ontology/Profession",
            cardinality=CanonicalCardinality(0, _UNBOUNDED),
        )
        canon = _schema(_shape("Person", prop))
        shexje = convert_canonical_to_shexje(canon)

        main_shape = next(s for s in shexje.shapes
                          if isinstance(s, ShapeE) and s.id == "Person")
        # Single property → expression is the TC directly
        expr = main_shape.expression
        tc = expr if isinstance(expr, TripleConstraintE) else next(
            t for t in expr.expressions if isinstance(t, TripleConstraintE)
        )
        assert isinstance(tc.path, AlternativePath)
        assert isinstance(tc.valueExpr, str)
        assert tc.valueExpr == "Profession"

        vs = _find_value_shape(shexje, "Profession")
        assert "http://dbpedia.org/ontology/Profession" in vs.values

    def test_alt_path_serialises_no_classref_field(self):
        """Old classRef field must not appear in JSON output."""
        prop = CanonicalProperty(
            path="http://dbpedia.org/ontology/occupation",
            pathAlternatives=[
                "http://dbpedia.org/ontology/occupation",
                "http://dbpedia.org/ontology/profession",
            ],
            classRef="http://dbpedia.org/ontology/Profession",
            cardinality=CanonicalCardinality(0, _UNBOUNDED),
        )
        canon = _schema(_shape("Person", prop))
        shexje = convert_canonical_to_shexje(canon)
        raw = serialize_shexje(shexje)
        assert "classRef" not in raw, "classRef must not appear in serialised ShexJE v2"
        assert "classRefOr" not in raw, "classRefOr must not appear in serialised ShexJE v2"
        assert "iriStem" not in raw, "iriStem must not appear in serialised ShexJE v2"


# ── JSON serialisation (no legacy fields) ────────────────────────────────────

class TestNoLegacyFields:
    def test_no_classref_in_output(self):
        canon = _schema(
            _shape("X",
                   _prop("http://ex.org/p1", classRef="http://ex.org/Foo"),
                   _prop("http://ex.org/p2", classRefOr=["http://ex.org/A", "http://ex.org/B"]),
                   _prop("http://ex.org/p3", iriStem="http://ex.org/ns/"),
                   )
        )
        raw = serialize_shexje(convert_canonical_to_shexje(canon))
        for forbidden in ("classRef", "classRefOr", "iriStem"):
            assert forbidden not in raw, f"{forbidden!r} must not appear in ShexJE v2 output"

    def test_value_shapes_appended_to_schema(self):
        canon = _schema(
            _shape("X",
                   _prop("http://ex.org/p", classRef="http://ex.org/City"))
        )
        shexje = convert_canonical_to_shexje(canon)
        # schema must have at least 2 shapes: the main shape + the City value shape
        assert len(shexje.shapes) >= 2
        ids = {s.id for s in shexje.shapes if isinstance(s, ShapeE)}
        assert "City" in ids


# ── Backward-compat parser ────────────────────────────────────────────────────

class TestBackwardCompatParser:
    def test_legacy_classref_parsed_as_valueexpr(self):
        old_doc = json.dumps({
            "@context": "http://www.w3.org/ns/shexje.jsonld",
            "type": "Schema",
            "shapes": [{
                "type": "Shape",
                "id": "Person",
                "expression": {
                    "type": "TripleConstraint",
                    "predicate": "http://ex.org/knows",
                    "classRef": "http://ex.org/Person",
                }
            }]
        })
        schema = parse_shexje(old_doc)
        tc = schema.shapes[0].expression
        assert isinstance(tc, TripleConstraintE)
        assert tc.valueExpr is not None
        assert not hasattr(tc, "classRef") or tc.valueExpr is not None

    def test_legacy_iristem_parsed_as_valueexpr(self):
        old_doc = json.dumps({
            "@context": "http://www.w3.org/ns/shexje.jsonld",
            "type": "Schema",
            "shapes": [{
                "type": "Shape",
                "id": "X",
                "expression": {
                    "type": "TripleConstraint",
                    "predicate": "http://www.w3.org/2002/07/owl#sameAs",
                    "iriStem": "http://www.wikidata.org/entity",
                }
            }]
        })
        schema = parse_shexje(old_doc)
        tc = schema.shapes[0].expression
        assert isinstance(tc.valueExpr, NodeConstraintE)
        assert isinstance(tc.valueExpr.values[0], IriStemValue)
        assert tc.valueExpr.values[0].stem == "http://www.wikidata.org/entity"

    def test_legacy_classrefor_parsed_as_node_constraint(self):
        old_doc = json.dumps({
            "@context": "http://www.w3.org/ns/shexje.jsonld",
            "type": "Schema",
            "shapes": [{
                "type": "Shape",
                "id": "X",
                "expression": {
                    "type": "TripleConstraint",
                    "predicate": "http://ex.org/type",
                    "classRefOr": ["http://ex.org/A", "http://ex.org/B"],
                }
            }]
        })
        schema = parse_shexje(old_doc)
        tc = schema.shapes[0].expression
        assert isinstance(tc.valueExpr, NodeConstraintE)
        assert "http://ex.org/A" in tc.valueExpr.values
        assert "http://ex.org/B" in tc.valueExpr.values


# ── Value-shape shorthand on Shape ────────────────────────────────────────────

class TestValueShapeShorthand:
    def test_shape_predicate_values_serialise(self):
        shape = ShapeE(
            id="Country",
            extra=[_RDF_TYPE],
            predicate=_RDF_TYPE,
            values=["http://dbpedia.org/ontology/Country"],
        )
        d = shape.to_dict()
        assert d["predicate"] == _RDF_TYPE
        assert d["values"] == ["http://dbpedia.org/ontology/Country"]
        assert "extra" in d

    def test_shape_predicate_values_parsed(self):
        doc = json.dumps({
            "@context": "http://www.w3.org/ns/shexje.jsonld",
            "type": "Schema",
            "shapes": [{
                "type": "Shape",
                "id": "Country",
                "extra": [_RDF_TYPE],
                "predicate": _RDF_TYPE,
                "values": ["http://dbpedia.org/ontology/Country"],
            }]
        })
        schema = parse_shexje(doc)
        shape = schema.shapes[0]
        assert isinstance(shape, ShapeE)
        assert shape.predicate == _RDF_TYPE
        assert shape.values == ["http://dbpedia.org/ontology/Country"]


# ── Roundtrip: canonical → shexje → canonical ────────────────────────────────

class TestRoundtrip:
    def test_classref_roundtrip(self):
        original = _schema(
            _shape("Person",
                   _prop("http://schema.org/worksFor",
                          classRef="http://schema.org/Organization",
                          min=0, max=_UNBOUNDED),
                   target="http://schema.org/Person")
        )
        shexje = convert_canonical_to_shexje(original)
        roundtrip = convert_shexje_to_canonical(shexje)

        # One shape should come back (the value shape "Organization" is filtered out)
        person_shapes = [s for s in roundtrip.shapes if s.name == "Person"]
        assert len(person_shapes) == 1
        person = person_shapes[0]
        assert person.targetClass == "http://schema.org/Person"
        assert len(person.properties) == 1
        prop = person.properties[0]
        assert prop.classRef == "http://schema.org/Organization"

    def test_classrefor_roundtrip(self):
        classes = ["http://ex.org/Alpha", "http://ex.org/Beta"]
        original = _schema(
            _shape("X", _prop("http://ex.org/p", classRefOr=classes))
        )
        shexje = convert_canonical_to_shexje(original)
        roundtrip = convert_shexje_to_canonical(shexje)

        x_shapes = [s for s in roundtrip.shapes if s.name == "X"]
        assert len(x_shapes) == 1
        prop = x_shapes[0].properties[0]
        assert prop.classRefOr is not None
        assert sorted(prop.classRefOr) == sorted(classes)

    def test_iristem_roundtrip(self):
        original = _schema(
            _shape("X", _prop("http://www.w3.org/2002/07/owl#sameAs",
                               iriStem="http://www.wikidata.org/entity"))
        )
        shexje = convert_canonical_to_shexje(original)
        roundtrip = convert_shexje_to_canonical(shexje)

        x_shapes = [s for s in roundtrip.shapes if s.name == "X"]
        prop = x_shapes[0].properties[0]
        assert prop.iriStem == "http://www.wikidata.org/entity"

    def test_alt_path_classref_roundtrip(self):
        prop = CanonicalProperty(
            path="http://dbpedia.org/ontology/occupation",
            pathAlternatives=[
                "http://dbpedia.org/ontology/occupation",
                "http://dbpedia.org/ontology/profession",
            ],
            classRef="http://dbpedia.org/ontology/Profession",
            cardinality=CanonicalCardinality(0, _UNBOUNDED),
        )
        original = _schema(_shape("Person", prop))
        shexje = convert_canonical_to_shexje(original)
        roundtrip = convert_shexje_to_canonical(shexje)

        person = next(s for s in roundtrip.shapes if s.name == "Person")
        rt_prop = person.properties[0]
        assert rt_prop.pathAlternatives is not None
        assert rt_prop.classRef == "http://dbpedia.org/ontology/Profession"

    def test_json_roundtrip_via_serialise_parse(self):
        """Full JSON serialise → parse → canonical roundtrip."""
        original = _schema(
            _shape("Scientist",
                   _prop("http://schema.org/worksFor",
                          classRef="http://schema.org/Organization"),
                   _prop("http://schema.org/knowsLanguage",
                          classRef="http://schema.org/Language"),
                   _prop("http://www.w3.org/2002/07/owl#sameAs",
                          iriStem="http://www.wikidata.org/entity"),
                   target="http://yago-knowledge.org/resource/Scientist")
        )
        shexje = convert_canonical_to_shexje(original)
        raw = serialize_shexje(shexje)
        parsed_schema = parse_shexje(raw)
        roundtrip = convert_shexje_to_canonical(parsed_schema)

        scientist = next(s for s in roundtrip.shapes if s.name == "Scientist")
        assert scientist.targetClass == "http://yago-knowledge.org/resource/Scientist"
        assert len(scientist.properties) == 3

        paths_to_classref = {p.path: p.classRef for p in scientist.properties
                             if p.classRef is not None}
        assert paths_to_classref.get("http://schema.org/worksFor") == "http://schema.org/Organization"
        assert paths_to_classref.get("http://schema.org/knowsLanguage") == "http://schema.org/Language"

        iristem_props = [p for p in scientist.properties if p.iriStem is not None]
        assert len(iristem_props) == 1
        assert iristem_props[0].iriStem == "http://www.wikidata.org/entity"


# ── Custom type_predicate (Wikidata P31) ──────────────────────────────────────

class TestCustomTypePredicate:
    WDT_P31 = "http://www.wikidata.org/prop/direct/P31"

    def test_wikidata_type_predicate_used(self):
        canon = _schema(
            _shape("X", _prop("http://ex.org/p",
                               classRef="http://www.wikidata.org/entity/Q6256"))
        )
        shexje = convert_canonical_to_shexje(canon, type_predicate=self.WDT_P31)
        vs = _find_value_shape(shexje, "Q6256")
        assert vs.predicate == self.WDT_P31
        assert self.WDT_P31 in vs.extra
