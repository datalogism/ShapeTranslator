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
Chain outputs are returned as ShexJESchema objects and compared by counting
shapes and properties — ShexJE is the single source of truth.
"""
from __future__ import annotations

import os

import pytest

from shaclex_py.schema.shexje import ShexJESchema, ShapeE, EachOfE, TripleConstraintE

# ── Paths to dataset directories ──────────────────────────────────────────────

_ROOT = os.path.join(os.path.dirname(__file__), "..")
SHACL_YAGO_DIR    = os.path.join(_ROOT, "dataset", "shacl_yago")
SHACL_DBPEDIA_DIR = os.path.join(_ROOT, "dataset", "shacl_dbpedia")
SHEX_YAGO_DIR     = os.path.join(_ROOT, "dataset", "shex_yago")
SHEX_WES_DIR      = os.path.join(_ROOT, "dataset", "shex_wes")


# ── ShexJE counting helpers ───────────────────────────────────────────────────

def _shape_count(shexje: ShexJESchema) -> int:
    """Count top-level ShapeE declarations (main shapes with targetClass or expression)."""
    return sum(
        1 for s in shexje.shapes
        if isinstance(s, ShapeE) and (s.targetClass is not None or s.expression is not None)
    )


def _prop_count(shexje: ShexJESchema) -> int:
    """Count TripleConstraints across all shapes."""
    count = 0
    for s in shexje.shapes:
        if not isinstance(s, ShapeE):
            continue
        expr = s.expression
        if isinstance(expr, EachOfE):
            count += sum(1 for e in expr.expressions if isinstance(e, TripleConstraintE))
        elif isinstance(expr, TripleConstraintE):
            count += 1
    return count


# ── Chain helpers ─────────────────────────────────────────────────────────────
# Each function returns a ShexJESchema for shape/property counting.

def _chain_A(shacl_path: str) -> ShexJESchema:
    """SHACL → ShexJE → SHACL → ShexJE."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.serializer.shacl_serializer import serialize_shacl

    shacl  = parse_shacl_file(shacl_path)
    shexje = convert_shacl_to_shexje(shacl)
    shacl2 = parse_shacl_file(serialize_shacl(convert_shexje_to_shacl(shexje)))
    return convert_shacl_to_shexje(shacl2)


def _chain_B(shacl_path: str) -> ShexJESchema:
    """SHACL → ShexJE → ShEx → ShexJE → SHACL → ShexJE."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.serializer.shacl_serializer import serialize_shacl
    from shaclex_py.serializer.shex_serializer import serialize_shex

    shacl   = parse_shacl_file(shacl_path)
    shexje1 = convert_shacl_to_shexje(shacl)
    shex    = parse_shex_file(serialize_shex(convert_shexje_to_shex(shexje1)))
    shexje2 = convert_shex_to_shexje(shex)
    shacl2  = parse_shacl_file(serialize_shacl(convert_shexje_to_shacl(shexje2)))
    return convert_shacl_to_shexje(shacl2)


def _chain_C(shex_path: str) -> ShexJESchema:
    """ShEx → ShexJE → ShEx → ShexJE."""
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.serializer.shex_serializer import serialize_shex

    shex   = parse_shex_file(shex_path)
    shexje = convert_shex_to_shexje(shex)
    shex2  = parse_shex_file(serialize_shex(convert_shexje_to_shex(shexje)))
    return convert_shex_to_shexje(shex2)


def _chain_D(shex_path: str) -> ShexJESchema:
    """ShEx → ShexJE → SHACL → ShexJE → ShEx → ShexJE."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.serializer.shacl_serializer import serialize_shacl
    from shaclex_py.serializer.shex_serializer import serialize_shex

    shex    = parse_shex_file(shex_path)
    shexje1 = convert_shex_to_shexje(shex)
    shacl   = parse_shacl_file(serialize_shacl(convert_shexje_to_shacl(shexje1)))
    shexje2 = convert_shacl_to_shexje(shacl)
    shex2   = parse_shex_file(serialize_shex(convert_shexje_to_shex(shexje2)))
    return convert_shex_to_shexje(shex2)


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
