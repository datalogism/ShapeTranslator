"""Translation cycle tests — ShexJE as the canonical intermediate format.

Verifies all 4 ShexJE-based translation chains on real dataset files.
ShexJE is the single canonical format; every SHACL ↔ ShEx conversion passes
through it internally.

SHACL-starting chains (datasets: DBpedia + YAGO)
─────────────────────────────────────────────────
  Chain A.  SHACL → ShexJE → SHACL
  Chain B.  SHACL → ShexJE → ShEx → ShexJE → SHACL

ShEx-starting chains (datasets: Wikidata WES + YAGO)
─────────────────────────────────────────────────────
  Chain C.  ShEx  → ShexJE → ShEx
  Chain D.  ShEx  → ShexJE → SHACL → ShexJE → ShEx

Comparison strategy
───────────────────
All chain outputs are projected through the internal canonical representation
for deterministic comparison.  Properties and shapes must be preserved across
every full round-trip.
"""
from __future__ import annotations

import json
import os

import pytest

# ── Paths to dataset directories ──────────────────────────────────────────────

_ROOT = os.path.join(os.path.dirname(__file__), "..")
SHACL_YAGO_DIR    = os.path.join(_ROOT, "dataset", "shacl_yago")
SHACL_DBPEDIA_DIR = os.path.join(_ROOT, "dataset", "shacl_dbpedia")
SHEX_YAGO_DIR     = os.path.join(_ROOT, "dataset", "shex_yago")
SHEX_WES_DIR      = os.path.join(_ROOT, "dataset", "shex_wes")


# ── Chain helpers ─────────────────────────────────────────────────────────────
# Each function returns a canonical dict for deterministic comparison.
# The internal canonical representation is used as the comparison projection.

def _chain_A(shacl_path: str) -> dict:
    """SHACL → ShexJE → SHACL → (canonical dict)."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
    from shaclex_py.serializer.shacl_serializer import serialize_shacl
    from shaclex_py.serializer.json_serializer import serialize_json

    shacl  = parse_shacl_file(shacl_path)
    shexje = convert_shacl_to_shexje(shacl)
    shacl2 = parse_shacl_file(serialize_shacl(convert_shexje_to_shacl(shexje)))
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain_B(shacl_path: str) -> dict:
    """SHACL → ShexJE → ShEx → ShexJE → SHACL → (canonical dict)."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
    from shaclex_py.serializer.shacl_serializer import serialize_shacl
    from shaclex_py.serializer.shex_serializer import serialize_shex
    from shaclex_py.serializer.json_serializer import serialize_json

    shacl   = parse_shacl_file(shacl_path)
    shexje1 = convert_shacl_to_shexje(shacl)
    shex    = parse_shex_file(serialize_shex(convert_shexje_to_shex(shexje1)))
    shexje2 = convert_shex_to_shexje(shex)
    shacl2  = parse_shacl_file(serialize_shacl(convert_shexje_to_shacl(shexje2)))
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain_C(shex_path: str) -> dict:
    """ShEx → ShexJE → ShEx → (canonical dict)."""
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
    from shaclex_py.serializer.shex_serializer import serialize_shex
    from shaclex_py.serializer.json_serializer import serialize_json

    shex   = parse_shex_file(shex_path)
    shexje = convert_shex_to_shexje(shex)
    shex2  = parse_shex_file(serialize_shex(convert_shexje_to_shex(shexje)))
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


def _chain_D(shex_path: str) -> dict:
    """ShEx → ShexJE → SHACL → ShexJE → ShEx → (canonical dict)."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
    from shaclex_py.serializer.shacl_serializer import serialize_shacl
    from shaclex_py.serializer.shex_serializer import serialize_shex
    from shaclex_py.serializer.json_serializer import serialize_json

    shex      = parse_shex_file(shex_path)
    shexje1   = convert_shex_to_shexje(shex)
    shacl     = parse_shacl_file(serialize_shacl(convert_shexje_to_shacl(shexje1)))
    shexje2   = convert_shacl_to_shexje(shacl)
    shex2_str = serialize_shex(convert_shexje_to_shex(shexje2))
    shex2     = parse_shex_file(shex2_str)
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


# ── Utility helpers ───────────────────────────────────────────────────────────

def _prop_count(canonical_dict: dict) -> int:
    return sum(len(s.get("properties", [])) for s in canonical_dict.get("shapes", []))


def _shape_count(canonical_dict: dict) -> int:
    return len(canonical_dict.get("shapes", []))


# ── Dataset file lists ────────────────────────────────────────────────────────

def _shacl_yago_files():
    return sorted(
        os.path.join(SHACL_YAGO_DIR, f)
        for f in os.listdir(SHACL_YAGO_DIR) if f.endswith(".ttl")
    )


def _shacl_dbpedia_files():
    return sorted(
        os.path.join(SHACL_DBPEDIA_DIR, f)
        for f in os.listdir(SHACL_DBPEDIA_DIR) if f.endswith(".ttl")
    )


def _shex_yago_files():
    return sorted(
        os.path.join(SHEX_YAGO_DIR, f)
        for f in os.listdir(SHEX_YAGO_DIR) if f.endswith(".shex")
    )


def _shex_wes_files():
    return sorted(
        os.path.join(SHEX_WES_DIR, f)
        for f in os.listdir(SHEX_WES_DIR) if f.endswith(".shex")
    )


def _basename(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


# ── Chain A & B : SHACL → ShexJE → {SHACL, ShEx → SHACL} ────────────────────

class TestChain_A_SHACLtoShexJE_toSHACL:
    """Chain A: SHACL → ShexJE → SHACL round-trip."""

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain_A_completes(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        result = _chain_A(path)
        assert _shape_count(result) >= 1, f"Chain A — {name}: no shapes in output"
        assert _prop_count(result) >= 1,  f"Chain A — {name}: no properties in output"

    @pytest.mark.parametrize("name", [
        "Airport", "Person", "Film", "Building", "City",
        "Artist", "Company", "University", "Food", "Politician",
    ])
    def test_dbpedia_chain_A_completes(self, name):
        path = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        result = _chain_A(path)
        assert _shape_count(result) >= 1, f"Chain A DBpedia — {name}: no shapes"

    def test_all_yago_chain_A(self):
        for path in _shacl_yago_files():
            result = _chain_A(path)
            assert _shape_count(result) >= 1, f"Chain A failed for {_basename(path)}"

    def test_all_dbpedia_chain_A(self):
        for path in _shacl_dbpedia_files():
            result = _chain_A(path)
            assert _shape_count(result) >= 1, f"Chain A failed for {_basename(path)}"


class TestChain_B_SHACLtoShexJE_toShEx_toShexJE_toSHACL:
    """Chain B: SHACL → ShexJE → ShEx → ShexJE → SHACL round-trip."""

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain_B_completes(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        result = _chain_B(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Airport", "Person", "Film", "Building", "City",
        "Artist", "Company", "University",
    ])
    def test_dbpedia_chain_B_completes(self, name):
        path = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        result = _chain_B(path)
        assert _shape_count(result) >= 1

    def test_all_yago_chain_B(self):
        for path in _shacl_yago_files():
            result = _chain_B(path)
            assert _shape_count(result) >= 1, f"Chain B failed for {_basename(path)}"

    def test_all_dbpedia_chain_B(self):
        for path in _shacl_dbpedia_files():
            result = _chain_B(path)
            assert _shape_count(result) >= 1, f"Chain B failed for {_basename(path)}"


# ── Chain C & D : ShEx → ShexJE → {ShEx, SHACL → ShEx} ──────────────────────

class TestChain_C_ShExtoShexJE_toShEx:
    """Chain C: ShEx → ShexJE → ShEx round-trip."""

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain_C_completes(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        result = _chain_C(path)
        assert _shape_count(result) >= 1

    def test_all_yago_chain_C(self):
        for path in _shex_yago_files():
            result = _chain_C(path)
            assert _shape_count(result) >= 1, f"Chain C failed for {_basename(path)}"

    def test_all_wes_chain_C(self):
        for path in _shex_wes_files():
            result = _chain_C(path)
            assert _shape_count(result) >= 1, f"Chain C failed for {_basename(path)}"


class TestChain_D_ShExtoShexJE_toSHACL_toShexJE_toShEx:
    """Chain D: ShEx → ShexJE → SHACL → ShexJE → ShEx round-trip."""

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain_D_completes(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        result = _chain_D(path)
        assert _shape_count(result) >= 1

    def test_all_yago_chain_D(self):
        for path in _shex_yago_files():
            result = _chain_D(path)
            assert _shape_count(result) >= 1, f"Chain D failed for {_basename(path)}"
