"""Integration tests for pySHACL compatibility.

These tests verify that SHACL output produced by shaclex-py can be loaded
and used by pySHACL (https://github.com/RDFLib/pySHACL) without errors.

Requires: pip install "shaclex-py[pyshacl]"
Skip automatically when pyshacl is not installed.
"""
import os

import pytest

pyshacl = pytest.importorskip("pyshacl", reason="pyshacl not installed; run: pip install pyshacl")

from shaclex_py.parser.shacl_parser import parse_shacl_file
from shaclex_py.parser.json_parser import parse_canonical_file
from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
from shaclex_py.converter.canonical_to_shacl import convert_canonical_to_shacl
from shaclex_py.serializer.shacl_serializer import serialize_shacl

SHACL_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")
SHACL_JSON_DIR = os.path.join(os.path.dirname(__file__), "..", "shacl_to_json")

# Minimal RDF instances used as data graphs for validation smoke-tests.
# These are intentionally simple; the goal is to confirm pyshacl can *use*
# our shapes graph, not to exhaustively check constraint evaluation.
_LANGUAGE_DATA = """
@prefix schema: <http://schema.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/lang/en> a schema:Language ;
    rdfs:label "English"@en ;
    schema:mainEntityOfPage <http://example.org/en> .
"""

_AIRLINE_DATA = """
@prefix schema: <http://schema.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/airline/1> a schema:Airline ;
    rdfs:label "Test Airline"@en ;
    schema:mainEntityOfPage <http://example.org/airline/1/page> .
"""


def _shapes_turtle(name: str) -> str:
    """Return serialised Turtle for the named YAGO SHACL shape."""
    schema = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
    return serialize_shacl(schema)


def _roundtrip_shapes_turtle(name: str) -> str:
    """Return Turtle after a canonical roundtrip (exercises canonical_to_shacl)."""
    schema = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
    canonical = convert_shacl_to_canonical(schema)
    roundtrip = convert_canonical_to_shacl(canonical)
    return serialize_shacl(roundtrip)


def _json_shapes_turtle(name: str) -> str:
    """Return Turtle converted from a canonical JSON file."""
    canonical = parse_canonical_file(os.path.join(SHACL_JSON_DIR, f"{name}.json"))
    schema = convert_canonical_to_shacl(canonical)
    return serialize_shacl(schema)


# ---------------------------------------------------------------------------
# Helper: run pyshacl without raising on non-conformance
# ---------------------------------------------------------------------------

def _validate(data: str, shapes: str) -> tuple[bool, str]:
    """Run pyshacl.validate and return (conforms, report_text).

    The test only asserts that the call succeeds (no parse/runtime errors).
    Conformance failures are expected for minimal dummy data.
    """
    conforms, _graph, text = pyshacl.validate(
        data_graph=data,
        data_graph_format="turtle",
        shacl_graph=shapes,
        shacl_graph_format="turtle",
    )
    return conforms, text


# ---------------------------------------------------------------------------
# Shapes loading: verify pyshacl can parse our shapes output without errors
# ---------------------------------------------------------------------------

class TestShapesLoadable:
    """pyshacl must be able to parse the Turtle we produce as a shapes graph."""

    def test_language_shapes_loadable(self):
        turtle = _shapes_turtle("Language")
        _validate(_LANGUAGE_DATA, turtle)  # just must not raise

    def test_airline_shapes_loadable(self):
        turtle = _shapes_turtle("Airline")
        _validate(_AIRLINE_DATA, turtle)

    def test_person_shapes_loadable(self):
        turtle = _shapes_turtle("Person")
        _validate(_LANGUAGE_DATA, turtle)

    def test_event_shapes_loadable(self):
        turtle = _shapes_turtle("Event")
        _validate(_LANGUAGE_DATA, turtle)


# ---------------------------------------------------------------------------
# sh:or compatibility: the or_constraints use pySHACL's sh:or form
# ---------------------------------------------------------------------------

class TestOrConstraints:
    """Shapes containing sh:or ([sh:class …] …) are accepted by pyshacl."""

    def test_airline_or_class_loadable(self):
        """Airline has sh:class [ sh:or (schema:Organization schema:Person) ]."""
        turtle = _shapes_turtle("Airline")
        assert "sh:or" in turtle, "Expected sh:or in serialized Airline shapes"
        _validate(_AIRLINE_DATA, turtle)

    def test_roundtrip_or_class_loadable(self):
        """Roundtrip through canonical preserves or_constraints as sh:or."""
        turtle = _roundtrip_shapes_turtle("Airline")
        assert "sh:or" in turtle
        _validate(_AIRLINE_DATA, turtle)

    def test_json_roundtrip_or_class_loadable(self):
        """canonical JSON -> SHACL with classRefOr produces valid sh:or."""
        turtle = _json_shapes_turtle("Airline")
        assert "sh:or" in turtle
        _validate(_AIRLINE_DATA, turtle)


# ---------------------------------------------------------------------------
# Conformance: well-formed data should pass, bad data should fail
# ---------------------------------------------------------------------------

class TestConformance:
    """Smoke-test that basic validation logic is reachable through our shapes."""

    def test_valid_language_conforms(self):
        turtle = _shapes_turtle("Language")
        conforms, report = _validate(_LANGUAGE_DATA, turtle)
        # Language requires rdfs:label (minCount 1) and mainEntityOfPage
        # (minCount 1); our dummy data satisfies both.
        assert conforms, f"Expected conformance for valid Language data.\n{report}"

    def test_missing_required_prop_fails(self):
        """Data missing a required property should not conform."""
        missing_label = """
        @prefix schema: <http://schema.org/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        <http://example.org/lang/en> a schema:Language .
        """
        turtle = _shapes_turtle("Language")
        conforms, _ = _validate(missing_label, turtle)
        assert not conforms, "Expected violation for missing required property"


# ---------------------------------------------------------------------------
# Batch: every YAGO file produces a shapes graph that pyshacl can parse
# ---------------------------------------------------------------------------

class TestBatch:
    """All 37 YAGO SHACL files produce pyshacl-loadable shapes graphs."""

    def test_all_37_files_loadable(self):
        files = [f[:-4] for f in os.listdir(SHACL_DIR) if f.endswith(".ttl")]
        assert len(files) == 37
        for name in files:
            turtle = _shapes_turtle(name)
            try:
                _validate(_LANGUAGE_DATA, turtle)
            except Exception as exc:
                pytest.fail(f"pyshacl failed on {name}: {exc}")
