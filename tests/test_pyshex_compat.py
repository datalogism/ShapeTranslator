"""Integration tests for PyShEx compatibility.

These tests verify that ShExC output_old produced by shaclex-py can be parsed
and used by PyShEx (https://github.com/hsolbrig/PyShEx) without errors.

PyShEx uses PyShExC (ANTLR-based) internally to compile ShExC to its AST.

Requires: pip install "shaclex-py[pyshex]"
Skip automatically when PyShEx is not installed.
"""
import os

import pytest

pyshex = pytest.importorskip("pyshex", reason="PyShEx not installed; run: pip install PyShEx")

from shaclex_py.parser.shacl_parser import parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex_file
from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
from shaclex_py.serializer.shex_serializer import serialize_shex

SHACL_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")
SHEX_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")

# Minimal Turtle RDF instances for smoke-test validation.
# The base URI <http://shex.example/> is used so that relative shape IRIs
# like <Language> resolve to <http://shex.example/Language>.
_BASE = "http://shex.example/"

_LANGUAGE_TTL = f"""
@base <{_BASE}> .
@prefix schema: <http://schema.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/lang/en> a schema:Language ;
    rdfs:label "English"^^xsd:string ;
    schema:mainEntityOfPage <http://example.org/en> .
"""


def _shexc(name: str) -> str:
    """Return ShExC produced from the named YAGO SHACL file."""
    schema = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
    shex = convert_shacl_to_shex(schema)
    return serialize_shex(shex)


def _dataset_shexc(name: str) -> str:
    """Return ShExC from the reference ShEx dataset file (original YAGO ShEx)."""
    shex = parse_shex_file(os.path.join(SHEX_DIR, f"{name}.shex"))
    return serialize_shex(shex)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_schema(shexc: str):
    """Parse a ShExC string with PyShEx and return the schema object."""
    from pyshex.shex_evaluator import ShExEvaluator
    evaluator = ShExEvaluator(schema=shexc)
    # Accessing evaluator._schema forces schema compilation/parsing.
    return evaluator._schema


# ---------------------------------------------------------------------------
# Schema loading: PyShExC must parse our ShExC without errors
# ---------------------------------------------------------------------------

class TestSchemaLoadable:
    """PyShEx must be able to compile the ShExC we produce."""

    def test_language_schema_loadable(self):
        shexc = _shexc("Language")
        _parse_schema(shexc)  # must not raise

    def test_person_schema_loadable(self):
        shexc = _shexc("Person")
        _parse_schema(shexc)

    def test_event_schema_loadable(self):
        shexc = _shexc("Event")
        _parse_schema(shexc)

    def test_airline_schema_loadable(self):
        shexc = _shexc("Airline")
        _parse_schema(shexc)

    def test_gender_schema_loadable(self):
        shexc = _shexc("Gender")
        _parse_schema(shexc)


# ---------------------------------------------------------------------------
# Dataset reference files: our serialized re-parse must be loadable
# ---------------------------------------------------------------------------

class TestDatasetSchemaLoadable:
    """ShExC from reference dataset, re-serialized through our model, must parse."""

    def test_language_dataset_loadable(self):
        shexc = _dataset_shexc("Language")
        _parse_schema(shexc)

    def test_person_dataset_loadable(self):
        shexc = _dataset_shexc("Person")
        _parse_schema(shexc)


# ---------------------------------------------------------------------------
# Validation smoke-test: ShExEvaluator can evaluate against RDF data
# ---------------------------------------------------------------------------

class TestEvaluator:
    """ShExEvaluator.evaluate() runs without errors on our ShExC output_old."""

    def test_language_evaluator_runs(self):
        from pyshex.shex_evaluator import ShExEvaluator
        shexc = _shexc("Language")
        evaluator = ShExEvaluator(
            rdf=_LANGUAGE_TTL,
            schema=shexc,
            rdf_format="turtle",
        )
        # evaluate() returns a list of EvaluationResult; we only check it runs
        results = evaluator.evaluate(
            focus="http://example.org/lang/en",
            start=f"{_BASE}Language",
        )
        assert isinstance(results, list)

    def test_empty_rdf_evaluator_runs(self):
        from pyshex.shex_evaluator import ShExEvaluator
        empty_ttl = "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        shexc = _shexc("Gender")
        evaluator = ShExEvaluator(rdf=empty_ttl, schema=shexc, rdf_format="turtle")
        # No focus nodes in empty graph → should return empty list
        results = evaluator.evaluate()
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Batch: every YAGO SHACL file produces PyShEx-parseable ShExC
# ---------------------------------------------------------------------------

class TestBatch:
    """All 37 YAGO files produce PyShEx-loadable ShExC."""

    def test_all_37_files_loadable(self):
        files = [f[:-4] for f in os.listdir(SHACL_DIR) if f.endswith(".ttl")]
        assert len(files) == 37
        for name in files:
            shexc = _shexc(name)
            try:
                _parse_schema(shexc)
            except Exception as exc:
                pytest.fail(f"PyShEx failed on {name}: {exc}")
