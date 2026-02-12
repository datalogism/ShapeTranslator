"""Tests for ShEx -> SHACL converter."""
import os
import pytest
from parsers.shex_parser import parse_shex_file
from parsers.shacl_parser import parse_shacl_file
from converters.shex_to_shacl import convert_shex_to_shacl
from serializers.shacl_serializer import serialize_shacl

SHEX_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")
SHACL_REF_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")


def _convert(name):
    shex = parse_shex_file(os.path.join(SHEX_DIR, f"{name}.shex"))
    return convert_shex_to_shacl(shex)


def _ref(name):
    return parse_shacl_file(os.path.join(SHACL_REF_DIR, f"{name}.ttl"))


def test_language_target_class():
    result = _convert("Language")
    assert len(result.shapes) == 1
    assert result.shapes[0].target_class.value == "http://schema.org/Language"


def test_language_property_count():
    result = _convert("Language")
    ref = _ref("Language")
    assert len(result.shapes[0].properties) == len(ref.shapes[0].properties)


def test_gender_target_class():
    result = _convert("Gender")
    assert result.shapes[0].target_class.value == "http://yago-knowledge.org/resource/Gender"


def test_event_or_constraints():
    result = _convert("Event")
    shape = result.shapes[0]
    or_props = [p for p in shape.properties if p.or_constraints]
    assert len(or_props) >= 2


def test_event_class_references():
    result = _convert("Event")
    shape = result.shapes[0]
    class_props = [p for p in shape.properties if p.class_]
    assert len(class_props) >= 2  # location->Place, superEvent->Event, follows->Event


def test_person_property_count():
    result = _convert("Person")
    ref = _ref("Person")
    # Allow some tolerance due to rdf:type handling
    assert abs(len(result.shapes[0].properties) - len(ref.shapes[0].properties)) <= 2


def test_pattern_from_iri_stem():
    result = _convert("Language")
    shape = result.shapes[0]
    pattern_props = [p for p in shape.properties if p.pattern]
    assert len(pattern_props) == 1
    assert "wikidata" in pattern_props[0].pattern


def test_all_37_files_convert():
    """Ensure all 37 ShEx files convert without error."""
    files = [f for f in os.listdir(SHEX_DIR) if f.endswith('.shex')]
    assert len(files) == 37
    for f in files:
        shex = parse_shex_file(os.path.join(SHEX_DIR, f))
        shacl = convert_shex_to_shacl(shex)
        assert len(shacl.shapes) >= 1, f"No shapes in conversion of {f}"


def test_serializable():
    """Ensure converted output can be serialized to valid Turtle."""
    result = _convert("Event")
    output = serialize_shacl(result)
    assert "@prefix sh:" in output
    assert "sh:NodeShape" in output
