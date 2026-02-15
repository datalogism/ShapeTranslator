"""Roundtrip tests: SHACL -> ShEx -> SHACL and ShEx -> SHACL -> ShEx."""
import os
import pytest
from shaclex_py.parser.shacl_parser import parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex_file
from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
from shaclex_py.converter.shex_to_shacl import convert_shex_to_shacl
from shaclex_py.serializer.shacl_serializer import serialize_shacl
from shaclex_py.serializer.shex_serializer import serialize_shex

SHACL_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")
SHEX_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")


def test_shacl_shex_shacl_language():
    """SHACL -> ShEx -> SHACL roundtrip for Language."""
    original = parse_shacl_file(os.path.join(SHACL_DIR, "Language.ttl"))
    shex = convert_shacl_to_shex(original)
    shex_str = serialize_shex(shex)
    shex_parsed = parse_shex_file(shex_str)
    roundtrip = convert_shex_to_shacl(shex_parsed)

    # Same number of shapes
    assert len(roundtrip.shapes) == len(original.shapes)
    # Same target class
    assert roundtrip.shapes[0].target_class.value == original.shapes[0].target_class.value


def test_shex_shacl_shex_gender():
    """ShEx -> SHACL -> ShEx roundtrip for Gender."""
    original = parse_shex_file(os.path.join(SHEX_DIR, "Gender.shex"))
    shacl = convert_shex_to_shacl(original)
    shacl_str = serialize_shacl(shacl)
    shacl_parsed = parse_shacl_file(shacl_str)
    roundtrip = convert_shacl_to_shex(shacl_parsed)

    # Same start shape should exist
    assert roundtrip.start is not None
    # Should have at least one shape
    assert len(roundtrip.shapes) >= 1


def test_roundtrip_property_count():
    """Check property count is preserved in roundtrip."""
    files = ["Language", "Gender", "BeliefSystem", "Taxon", "AstronomicalObject"]
    for name in files:
        original = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
        shex = convert_shacl_to_shex(original)
        shex_str = serialize_shex(shex)
        shex_parsed = parse_shex_file(shex_str)
        roundtrip = convert_shex_to_shacl(shex_parsed)

        orig_props = len(original.shapes[0].properties)
        rt_props = len(roundtrip.shapes[0].properties)
        # Allow small tolerance for rdf:type handling
        assert abs(orig_props - rt_props) <= 2, (
            f"{name}: original {orig_props} props, roundtrip {rt_props} props"
        )


def test_roundtrip_all_shacl_files():
    """SHACL -> ShEx -> SHACL roundtrip for all 37 files."""
    files = [f.replace('.ttl', '') for f in os.listdir(SHACL_DIR) if f.endswith('.ttl')]
    for name in files:
        original = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
        shex = convert_shacl_to_shex(original)
        shex_str = serialize_shex(shex)
        # This should parse successfully
        shex_parsed = parse_shex_file(shex_str)
        roundtrip = convert_shex_to_shacl(shex_parsed)
        assert len(roundtrip.shapes) >= 1, f"No shapes in roundtrip for {name}"


def test_roundtrip_all_shex_files():
    """ShEx -> SHACL -> ShEx roundtrip for all 37 files."""
    files = [f.replace('.shex', '') for f in os.listdir(SHEX_DIR) if f.endswith('.shex')]
    for name in files:
        original = parse_shex_file(os.path.join(SHEX_DIR, f"{name}.shex"))
        shacl = convert_shex_to_shacl(original)
        shacl_str = serialize_shacl(shacl)
        shacl_parsed = parse_shacl_file(shacl_str)
        roundtrip = convert_shacl_to_shex(shacl_parsed)
        assert len(roundtrip.shapes) >= 1, f"No shapes in roundtrip for {name}"
