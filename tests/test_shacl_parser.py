"""Tests for SHACL parser."""
import os
import pytest
from shaclex_py.parser.shacl_parser import parse_shacl_file


YAGO_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")


def test_parse_language():
    schema = parse_shacl_file(os.path.join(YAGO_DIR, "Language.ttl"))
    assert len(schema.shapes) == 1
    shape = schema.shapes[0]
    assert shape.iri.value == "http://shaclshapes.org/LanguageShape"
    assert shape.target_class.value == "http://schema.org/Language"
    assert len(shape.properties) == 7


def test_parse_gender():
    schema = parse_shacl_file(os.path.join(YAGO_DIR, "Gender.ttl"))
    assert len(schema.shapes) == 1
    shape = schema.shapes[0]
    assert shape.target_class.value == "http://yago-knowledge.org/resource/Gender"
    assert len(shape.properties) == 7


def test_parse_event_or_constraints():
    schema = parse_shacl_file(os.path.join(YAGO_DIR, "Event.ttl"))
    shape = schema.shapes[0]
    or_props = [p for p in shape.properties if p.or_constraints]
    assert len(or_props) == 3  # organizer, sponsor, participant


def test_parse_person_class_references():
    schema = parse_shacl_file(os.path.join(YAGO_DIR, "Person.ttl"))
    shape = schema.shapes[0]
    class_props = [p for p in shape.properties if p.class_]
    assert len(class_props) >= 10  # Many sh:class references


def test_parse_event_has_value():
    schema = parse_shacl_file(os.path.join(YAGO_DIR, "Event.ttl"))
    shape = schema.shapes[0]
    hv_props = [p for p in shape.properties if p.has_value]
    assert len(hv_props) == 1  # rdf:type hasValue schema:Event


def test_parse_pattern():
    schema = parse_shacl_file(os.path.join(YAGO_DIR, "Language.ttl"))
    shape = schema.shapes[0]
    pattern_props = [p for p in shape.properties if p.pattern]
    assert len(pattern_props) == 1
    assert pattern_props[0].pattern == "^http://www.wikidata.org/entity/"


def test_parse_all_37_files():
    """Ensure all 37 YAGO files parse without error."""
    files = [f for f in os.listdir(YAGO_DIR) if f.endswith('.ttl')]
    assert len(files) == 37
    for f in files:
        schema = parse_shacl_file(os.path.join(YAGO_DIR, f))
        assert len(schema.shapes) >= 1, f"No shapes in {f}"
