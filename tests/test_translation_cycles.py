"""Translation cycle tests — Canonical JSON vs ShexJE as intermediate format.

Verifies all 8 translation chains on real dataset files and compares the
Canonical-JSON-based and ShexJE-based pipelines for information equivalence.

SHACL-starting chains (datasets: DBpedia + YAGO)
─────────────────────────────────────────────────
  Chain 1.  SHACL → CanonicalJSON → SHACL
  Chain 2.  SHACL → ShexJE        → SHACL
  Chain 3.  SHACL → CanonicalJSON → ShEx → CanonicalJSON → SHACL
  Chain 4.  SHACL → ShexJE        → ShEx → ShexJE        → SHACL

ShEx-starting chains (datasets: Wikidata WES + YAGO)
─────────────────────────────────────────────────────
  Chain 5.  ShEx  → CanonicalJSON → ShEx
  Chain 6.  ShEx  → ShexJE        → ShEx
  Chain 7.  ShEx  → CanonicalJSON → SHACL → CanonicalJSON → ShEx
  Chain 8.  ShEx  → ShexJE        → SHACL → ShexJE        → ShEx

Comparison strategy
───────────────────
All chain outputs are projected onto Canonical JSON for comparison.
Parallel chains (1 vs 2, 3 vs 4, 5 vs 6, 7 vs 8) are expected to produce
identical canonical JSON because CanonicalJSON ↔ ShexJE is a lossless
round-trip for every construct in the canonical model.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pytest

# ── Paths to dataset directories ──────────────────────────────────────────────

_ROOT = os.path.join(os.path.dirname(__file__), "..")
SHACL_YAGO_DIR   = os.path.join(_ROOT, "dataset", "shacl_yago")
SHACL_DBPEDIA_DIR = os.path.join(_ROOT, "dataset", "shacl_dbpedia")
SHEX_YAGO_DIR    = os.path.join(_ROOT, "dataset", "shex_yago")
SHEX_WES_DIR     = os.path.join(_ROOT, "dataset", "shex_wes")


# ── Lazy imports (avoid heavy top-level loading in collection phase) ───────────

def _imports():
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.parser.shexje_parser       import parse_shexje
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
    from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.shexje_serializer  import serialize_shexje
    from shaclex_py.serializer.json_serializer    import serialize_json
    return (
        parse_shacl_file, parse_shex_file, parse_shexje,
        convert_shacl_to_canonical, convert_shex_to_canonical,
        convert_canonical_to_shacl, convert_canonical_to_shex,
        convert_canonical_to_shexje, convert_shexje_to_canonical,
        serialize_shacl, serialize_shex, serialize_shexje, serialize_json,
    )


# ── Chain helpers ─────────────────────────────────────────────────────────────
# Each function returns a canonical JSON *dict* so results are directly
# comparable regardless of formatting differences.

def _chain1(shacl_path: str) -> dict:
    """SHACL → CanonicalJSON → SHACL → (canonical JSON)."""
    (parse_shacl_file, _, _,
     convert_shacl_to_canonical, _,
     convert_canonical_to_shacl, _,
     _, _,
     serialize_shacl, _, _, serialize_json) = _imports()

    shacl        = parse_shacl_file(shacl_path)
    canonical    = convert_shacl_to_canonical(shacl)
    shacl2_str   = serialize_shacl(convert_canonical_to_shacl(canonical))
    shacl2       = parse_shacl_file(shacl2_str)
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain2(shacl_path: str) -> dict:
    """SHACL → ShexJE → SHACL → (canonical JSON)."""
    (parse_shacl_file, _, _,
     convert_shacl_to_canonical, _,
     convert_canonical_to_shacl, _,
     convert_canonical_to_shexje, convert_shexje_to_canonical,
     serialize_shacl, _, _, serialize_json) = _imports()

    shacl       = parse_shacl_file(shacl_path)
    shexje      = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
    canonical2  = convert_shexje_to_canonical(shexje)
    shacl2_str  = serialize_shacl(convert_canonical_to_shacl(canonical2))
    shacl2      = parse_shacl_file(shacl2_str)
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain3(shacl_path: str) -> dict:
    """SHACL → CanonicalJSON → ShEx → CanonicalJSON → SHACL → (canonical JSON)."""
    (parse_shacl_file, parse_shex_file, _,
     convert_shacl_to_canonical, convert_shex_to_canonical,
     convert_canonical_to_shacl, convert_canonical_to_shex,
     _, _,
     serialize_shacl, serialize_shex, _, serialize_json) = _imports()

    shacl        = parse_shacl_file(shacl_path)
    shex_str     = serialize_shex(convert_canonical_to_shex(convert_shacl_to_canonical(shacl)))
    shex         = parse_shex_file(shex_str)
    canonical2   = convert_shex_to_canonical(shex)
    shacl2_str   = serialize_shacl(convert_canonical_to_shacl(canonical2))
    shacl2       = parse_shacl_file(shacl2_str)
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain4(shacl_path: str) -> dict:
    """SHACL → ShexJE → ShEx → ShexJE → SHACL → (canonical JSON)."""
    (parse_shacl_file, parse_shex_file, _,
     convert_shacl_to_canonical, convert_shex_to_canonical,
     convert_canonical_to_shacl, convert_canonical_to_shex,
     convert_canonical_to_shexje, convert_shexje_to_canonical,
     serialize_shacl, serialize_shex, _, serialize_json) = _imports()

    shacl        = parse_shacl_file(shacl_path)
    shexje1      = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
    shex_str     = serialize_shex(convert_canonical_to_shex(convert_shexje_to_canonical(shexje1)))
    shex         = parse_shex_file(shex_str)
    shexje2      = convert_canonical_to_shexje(convert_shex_to_canonical(shex))
    canonical3   = convert_shexje_to_canonical(shexje2)
    shacl2_str   = serialize_shacl(convert_canonical_to_shacl(canonical3))
    shacl2       = parse_shacl_file(shacl2_str)
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain5(shex_path: str) -> dict:
    """ShEx → CanonicalJSON → ShEx → (canonical JSON)."""
    (_, parse_shex_file, _,
     _, convert_shex_to_canonical,
     _, convert_canonical_to_shex,
     _, _,
     _, serialize_shex, _, serialize_json) = _imports()

    shex      = parse_shex_file(shex_path)
    shex2_str = serialize_shex(convert_canonical_to_shex(convert_shex_to_canonical(shex)))
    shex2     = parse_shex_file(shex2_str)
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


def _chain6(shex_path: str) -> dict:
    """ShEx → ShexJE → ShEx → (canonical JSON)."""
    (_, parse_shex_file, _,
     _, convert_shex_to_canonical,
     _, convert_canonical_to_shex,
     convert_canonical_to_shexje, convert_shexje_to_canonical,
     _, serialize_shex, _, serialize_json) = _imports()

    shex      = parse_shex_file(shex_path)
    shexje    = convert_canonical_to_shexje(convert_shex_to_canonical(shex))
    shex2_str = serialize_shex(convert_canonical_to_shex(convert_shexje_to_canonical(shexje)))
    shex2     = parse_shex_file(shex2_str)
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


def _chain7(shex_path: str) -> dict:
    """ShEx → CanonicalJSON → SHACL → CanonicalJSON → ShEx → (canonical JSON)."""
    (parse_shacl_file, parse_shex_file, _,
     convert_shacl_to_canonical, convert_shex_to_canonical,
     convert_canonical_to_shacl, convert_canonical_to_shex,
     _, _,
     serialize_shacl, serialize_shex, _, serialize_json) = _imports()

    shex      = parse_shex_file(shex_path)
    shacl_str = serialize_shacl(convert_canonical_to_shacl(convert_shex_to_canonical(shex)))
    shacl     = parse_shacl_file(shacl_str)
    shex2_str = serialize_shex(convert_canonical_to_shex(convert_shacl_to_canonical(shacl)))
    shex2     = parse_shex_file(shex2_str)
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


def _chain8(shex_path: str) -> dict:
    """ShEx → ShexJE → SHACL → ShexJE → ShEx → (canonical JSON)."""
    (parse_shacl_file, parse_shex_file, _,
     convert_shacl_to_canonical, convert_shex_to_canonical,
     convert_canonical_to_shacl, convert_canonical_to_shex,
     convert_canonical_to_shexje, convert_shexje_to_canonical,
     serialize_shacl, serialize_shex, _, serialize_json) = _imports()

    shex       = parse_shex_file(shex_path)
    shexje1    = convert_canonical_to_shexje(convert_shex_to_canonical(shex))
    shacl_str  = serialize_shacl(convert_canonical_to_shacl(convert_shexje_to_canonical(shexje1)))
    shacl      = parse_shacl_file(shacl_str)
    shexje2    = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
    shex2_str  = _imports()[10](  # serialize_shex
        _imports()[6](convert_shexje_to_canonical(shexje2))  # convert_canonical_to_shex
    )
    # redo cleanly to avoid index confusion
    (_, parse_shex_file2, _,
     _, convert_shex_to_canonical2,
     _, _,
     _, _,
     _, _, _, serialize_json2) = _imports()
    shex2 = parse_shex_file2(shex2_str)
    return json.loads(serialize_json2(convert_shex_to_canonical2(shex2)))


# Cleaner version of chain8 without the indexing issue
def _chain8(shex_path: str) -> dict:  # noqa: F811 (intentional re-definition)
    """ShEx → ShexJE → SHACL → ShexJE → ShEx → (canonical JSON)."""
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
    from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.json_serializer    import serialize_json

    shex      = parse_shex_file(shex_path)
    shexje1   = convert_canonical_to_shexje(convert_shex_to_canonical(shex))
    shacl_str = serialize_shacl(convert_canonical_to_shacl(convert_shexje_to_canonical(shexje1)))
    shacl     = parse_shacl_file(shacl_str)
    shexje2   = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
    shex2_str = serialize_shex(convert_canonical_to_shex(convert_shexje_to_canonical(shexje2)))
    shex2     = parse_shex_file(shex2_str)
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


# Fix chain1–7 the same clean way so test files are self-consistent
def _chain1(shacl_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.json_serializer    import serialize_json

    shacl      = parse_shacl_file(shacl_path)
    canonical  = convert_shacl_to_canonical(shacl)
    shacl2     = parse_shacl_file(serialize_shacl(convert_canonical_to_shacl(canonical)))
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain2(shacl_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
    from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.json_serializer    import serialize_json

    shacl      = parse_shacl_file(shacl_path)
    shexje     = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
    canonical2 = convert_shexje_to_canonical(shexje)
    shacl2     = parse_shacl_file(serialize_shacl(convert_canonical_to_shacl(canonical2)))
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain3(shacl_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.json_serializer    import serialize_json

    shacl      = parse_shacl_file(shacl_path)
    shex       = parse_shex_file(serialize_shex(convert_canonical_to_shex(convert_shacl_to_canonical(shacl))))
    canonical2 = convert_shex_to_canonical(shex)
    shacl2     = parse_shacl_file(serialize_shacl(convert_canonical_to_shacl(canonical2)))
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain4(shacl_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
    from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.json_serializer    import serialize_json

    shacl   = parse_shacl_file(shacl_path)
    shexje1 = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
    shex    = parse_shex_file(serialize_shex(convert_canonical_to_shex(convert_shexje_to_canonical(shexje1))))
    shexje2 = convert_canonical_to_shexje(convert_shex_to_canonical(shex))
    shacl2  = parse_shacl_file(serialize_shacl(convert_canonical_to_shacl(convert_shexje_to_canonical(shexje2))))
    return json.loads(serialize_json(convert_shacl_to_canonical(shacl2)))


def _chain5(shex_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.json_serializer    import serialize_json

    shex  = parse_shex_file(shex_path)
    shex2 = parse_shex_file(serialize_shex(convert_canonical_to_shex(convert_shex_to_canonical(shex))))
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


def _chain6(shex_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
    from shaclex_py.converter.shexje_to_canonical import convert_shexje_to_canonical
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.json_serializer    import serialize_json

    shex   = parse_shex_file(shex_path)
    shexje = convert_canonical_to_shexje(convert_shex_to_canonical(shex))
    shex2  = parse_shex_file(serialize_shex(convert_canonical_to_shex(convert_shexje_to_canonical(shexje))))
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


def _chain7(shex_path: str) -> dict:  # noqa: F811
    from shaclex_py.parser.shacl_parser        import parse_shacl_file
    from shaclex_py.parser.shex_parser         import parse_shex_file
    from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
    from shaclex_py.converter.shex_to_canonical   import convert_shex_to_canonical
    from shaclex_py.converter.canonical_to_shacl  import convert_canonical_to_shacl
    from shaclex_py.converter.canonical_to_shex   import convert_canonical_to_shex
    from shaclex_py.serializer.shacl_serializer   import serialize_shacl
    from shaclex_py.serializer.shex_serializer    import serialize_shex
    from shaclex_py.serializer.json_serializer    import serialize_json

    shex   = parse_shex_file(shex_path)
    shacl  = parse_shacl_file(serialize_shacl(convert_canonical_to_shacl(convert_shex_to_canonical(shex))))
    shex2  = parse_shex_file(serialize_shex(convert_canonical_to_shex(convert_shacl_to_canonical(shacl))))
    return json.loads(serialize_json(convert_shex_to_canonical(shex2)))


# ── Utility: property count from canonical dict ───────────────────────────────

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


# ── Chain 1 & 2 : SHACL → X → SHACL ─────────────────────────────────────────

class TestChain1And2_SHACLtoX_toSHACL:
    """Compare chain 1 (via Canonical JSON) vs chain 2 (via ShexJE).

    Both end in SHACL; final outputs are compared as canonical JSON.
    Expected: identical output for all files in both YAGO and DBpedia datasets.
    """

    # ── Named YAGO tests ───────────────────────────────────────────────────

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain1_completes(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        result = _chain1(path)
        assert _shape_count(result) >= 1, f"Chain 1 — {name}: no shapes in output"
        assert _prop_count(result) >= 1,  f"Chain 1 — {name}: no properties in output"

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain2_completes(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        result = _chain2(path)
        assert _shape_count(result) >= 1, f"Chain 2 — {name}: no shapes in output"
        assert _prop_count(result) >= 1,  f"Chain 2 — {name}: no properties in output"

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain1_equals_chain2(self, name):
        """Canonical JSON and ShexJE intermediates must produce identical SHACL."""
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        c1 = _chain1(path)
        c2 = _chain2(path)
        assert c1 == c2, (
            f"Chain 1 vs Chain 2 differ for {name}:\n"
            f"  Chain 1 shapes: {_shape_count(c1)}, props: {_prop_count(c1)}\n"
            f"  Chain 2 shapes: {_shape_count(c2)}, props: {_prop_count(c2)}"
        )

    # ── Named DBpedia tests ────────────────────────────────────────────────

    @pytest.mark.parametrize("name", [
        "Airport", "Person", "Film", "Building", "City",
        "Artist", "Company", "University", "Food", "Politician",
    ])
    def test_dbpedia_chain1_completes(self, name):
        path = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        result = _chain1(path)
        assert _shape_count(result) >= 1, f"Chain 1 DBpedia — {name}: no shapes"

    @pytest.mark.parametrize("name", [
        "Airport", "Person", "Film", "Building", "City",
        "Artist", "Company", "University", "Food", "Politician",
    ])
    def test_dbpedia_chain2_completes(self, name):
        path = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        result = _chain2(path)
        assert _shape_count(result) >= 1, f"Chain 2 DBpedia — {name}: no shapes"

    @pytest.mark.parametrize("name", [
        "Airport", "Person", "Film", "Building", "City",
        "Artist", "Company", "University", "Food", "Politician",
    ])
    def test_dbpedia_chain1_equals_chain2(self, name):
        path = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        c1 = _chain1(path)
        c2 = _chain2(path)
        assert c1 == c2, f"Chain 1 vs Chain 2 differ for DBpedia/{name}"

    # ── Full batch tests ────────────────────────────────────────────────────

    def test_all_yago_chain1(self):
        for path in _shacl_yago_files():
            result = _chain1(path)
            assert _shape_count(result) >= 1, f"Chain 1 failed for {_basename(path)}"

    def test_all_yago_chain2(self):
        for path in _shacl_yago_files():
            result = _chain2(path)
            assert _shape_count(result) >= 1, f"Chain 2 failed for {_basename(path)}"

    def test_all_yago_chains_1_2_equivalent(self):
        """All 37 YAGO SHACL files: chain 1 and chain 2 must agree."""
        for path in _shacl_yago_files():
            c1 = _chain1(path)
            c2 = _chain2(path)
            assert c1 == c2, f"Chain 1 ≠ Chain 2 for {_basename(path)}"

    def test_all_dbpedia_chain1(self):
        for path in _shacl_dbpedia_files():
            result = _chain1(path)
            assert _shape_count(result) >= 1, f"Chain 1 failed for {_basename(path)}"

    def test_all_dbpedia_chain2(self):
        for path in _shacl_dbpedia_files():
            result = _chain2(path)
            assert _shape_count(result) >= 1, f"Chain 2 failed for {_basename(path)}"

    def test_all_dbpedia_chains_1_2_equivalent(self):
        """All 20 DBpedia SHACL files: chain 1 and chain 2 must agree."""
        for path in _shacl_dbpedia_files():
            c1 = _chain1(path)
            c2 = _chain2(path)
            assert c1 == c2, f"Chain 1 ≠ Chain 2 for DBpedia/{_basename(path)}"


# ── Chain 3 & 4 : SHACL → X → ShEx → X → SHACL ──────────────────────────────

class TestChain3And4_SHACLtoX_toShEx_toX_toSHACL:
    """Compare chain 3 (via Canonical JSON) vs chain 4 (via ShexJE).

    Both go through ShEx as the middle format.
    """

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain3_completes(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        result = _chain3(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain4_completes(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        result = _chain4(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain3_equals_chain4(self, name):
        path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        c3 = _chain3(path)
        c4 = _chain4(path)
        assert c3 == c4, f"Chain 3 vs Chain 4 differ for {name}"

    @pytest.mark.parametrize("name", [
        "Airport", "Person", "Film", "Building", "City",
        "Artist", "Company", "University",
    ])
    def test_dbpedia_chain3_equals_chain4(self, name):
        path = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        c3 = _chain3(path)
        c4 = _chain4(path)
        assert c3 == c4, f"Chain 3 vs Chain 4 differ for DBpedia/{name}"

    def test_all_yago_chains_3_4_equivalent(self):
        for path in _shacl_yago_files():
            c3 = _chain3(path)
            c4 = _chain4(path)
            assert c3 == c4, f"Chain 3 ≠ Chain 4 for {_basename(path)}"

    def test_all_dbpedia_chains_3_4_equivalent(self):
        for path in _shacl_dbpedia_files():
            c3 = _chain3(path)
            c4 = _chain4(path)
            assert c3 == c4, f"Chain 3 ≠ Chain 4 for DBpedia/{_basename(path)}"


# ── Chain 5 & 6 : ShEx → X → ShEx ────────────────────────────────────────────

class TestChain5And6_ShExtoX_toShEx:
    """Compare chain 5 (via Canonical JSON) vs chain 6 (via ShexJE).

    Both end in ShEx; final outputs are compared as canonical JSON.
    """

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain5_completes(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        result = _chain5(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain6_completes(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        result = _chain6(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject", "Book", "Movie",
    ])
    def test_yago_chain5_equals_chain6(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        c5 = _chain5(path)
        c6 = _chain6(path)
        assert c5 == c6, f"Chain 5 vs Chain 6 differ for {name}"

    # ── Wikidata WES ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("qid", [
        "Q198", "Q175263", "Q12136", "Q130003", "Q186516",
        "Q193424", "Q194188", "Q1172284", "Q174989", "Q142714",
    ])
    def test_wes_chain5_completes(self, qid):
        path = os.path.join(SHEX_WES_DIR, f"{qid}.shex")
        result = _chain5(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("qid", [
        "Q198", "Q175263", "Q12136", "Q130003", "Q186516",
        "Q193424", "Q194188", "Q1172284", "Q174989", "Q142714",
    ])
    def test_wes_chain6_completes(self, qid):
        path = os.path.join(SHEX_WES_DIR, f"{qid}.shex")
        result = _chain6(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("qid", [
        "Q198", "Q175263", "Q12136", "Q130003", "Q186516",
        "Q193424", "Q194188", "Q1172284", "Q174989", "Q142714",
    ])
    def test_wes_chain5_equals_chain6(self, qid):
        path = os.path.join(SHEX_WES_DIR, f"{qid}.shex")
        c5 = _chain5(path)
        c6 = _chain6(path)
        assert c5 == c6, f"Chain 5 vs Chain 6 differ for WES/{qid}"

    # ── Full batch tests ────────────────────────────────────────────────────

    def test_all_yago_chains_5_6_equivalent(self):
        for path in _shex_yago_files():
            c5 = _chain5(path)
            c6 = _chain6(path)
            assert c5 == c6, f"Chain 5 ≠ Chain 6 for {_basename(path)}"

    def test_all_wes_chains_5_6_equivalent(self):
        for path in _shex_wes_files():
            c5 = _chain5(path)
            c6 = _chain6(path)
            assert c5 == c6, f"Chain 5 ≠ Chain 6 for WES/{_basename(path)}"


# ── Chain 7 & 8 : ShEx → X → SHACL → X → ShEx ───────────────────────────────

class TestChain7And8_ShExtoX_toSHACL_toX_toShEx:
    """Compare chain 7 (via Canonical JSON) vs chain 8 (via ShexJE).

    Both go through SHACL as the middle format.
    """

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain7_completes(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        result = _chain7(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain8_completes(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        result = _chain8(path)
        assert _shape_count(result) >= 1

    @pytest.mark.parametrize("name", [
        "Language", "Gender", "Person", "Event", "Airport",
        "BeliefSystem", "Taxon", "AstronomicalObject",
    ])
    def test_yago_chain7_equals_chain8(self, name):
        path = os.path.join(SHEX_YAGO_DIR, f"{name}.shex")
        c7 = _chain7(path)
        c8 = _chain8(path)
        assert c7 == c8, f"Chain 7 vs Chain 8 differ for {name}"

    @pytest.mark.parametrize("qid", [
        "Q198", "Q175263", "Q12136", "Q130003", "Q186516",
        "Q193424", "Q194188", "Q1172284", "Q174989", "Q142714",
    ])
    def test_wes_chain7_equals_chain8(self, qid):
        path = os.path.join(SHEX_WES_DIR, f"{qid}.shex")
        c7 = _chain7(path)
        c8 = _chain8(path)
        assert c7 == c8, f"Chain 7 vs Chain 8 differ for WES/{qid}"

    def test_all_yago_chains_7_8_equivalent(self):
        for path in _shex_yago_files():
            c7 = _chain7(path)
            c8 = _chain8(path)
            assert c7 == c8, f"Chain 7 ≠ Chain 8 for {_basename(path)}"

    def test_all_wes_chains_7_8_equivalent(self):
        for path in _shex_wes_files():
            c7 = _chain7(path)
            c8 = _chain8(path)
            assert c7 == c8, f"Chain 7 ≠ Chain 8 for WES/{_basename(path)}"


# ── ShexJE-specific structural tests ─────────────────────────────────────────

class TestShexJEStructure:
    """Verify that the ShexJE intermediate has the correct structure."""

    @pytest.mark.parametrize("name", ["Language", "Person", "Event", "Airport"])
    def test_yago_shexje_has_context(self, name):
        from shaclex_py.parser.shacl_parser        import parse_shacl_file
        from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
        from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
        from shaclex_py.serializer.shexje_serializer  import serialize_shexje

        path   = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shacl  = parse_shacl_file(path)
        shexje = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
        d      = json.loads(serialize_shexje(shexje))
        assert d["@context"] == "http://www.w3.org/ns/shexje.jsonld"
        assert d["type"] == "Schema"
        assert "shapes" in d

    @pytest.mark.parametrize("name", ["Language", "Person", "Event", "Airport"])
    def test_yago_shexje_shapes_have_type_and_id(self, name):
        from shaclex_py.parser.shacl_parser        import parse_shacl_file
        from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
        from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
        from shaclex_py.serializer.shexje_serializer  import serialize_shexje

        path   = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shacl  = parse_shacl_file(path)
        shexje = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
        d      = json.loads(serialize_shexje(shexje))
        for shape in d["shapes"]:
            assert "type" in shape, f"{name}: shape missing 'type'"
            assert "id" in shape,   f"{name}: shape missing 'id'"

    @pytest.mark.parametrize("name", ["Language", "Person", "Event", "Airport"])
    def test_yago_shexje_target_class_preserved(self, name):
        from shaclex_py.parser.shacl_parser        import parse_shacl_file
        from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
        from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
        from shaclex_py.serializer.shexje_serializer  import serialize_shexje

        path   = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shacl  = parse_shacl_file(path)
        canon  = convert_shacl_to_canonical(shacl)
        shexje = convert_canonical_to_shexje(canon)
        d      = json.loads(serialize_shexje(shexje))
        # Main shape should carry targetClass
        main_shape = next(
            (s for s in d["shapes"] if s.get("type") == "Shape"), None
        )
        assert main_shape is not None
        assert "targetClass" in main_shape, f"{name}: targetClass missing in ShexJE"
        assert main_shape["targetClass"] == canon.shapes[0].targetClass

    @pytest.mark.parametrize("name", ["Language", "Person", "Event", "Airport"])
    def test_yago_shexje_triple_constraints_have_predicate(self, name):
        from shaclex_py.parser.shacl_parser        import parse_shacl_file
        from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
        from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
        from shaclex_py.serializer.shexje_serializer  import serialize_shexje

        path   = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shacl  = parse_shacl_file(path)
        shexje = convert_canonical_to_shexje(convert_shacl_to_canonical(shacl))
        d      = json.loads(serialize_shexje(shexje))
        # Collect all TripleConstraints from EachOf / direct expression
        tcs = []
        for shape in d["shapes"]:
            expr = shape.get("expression", {})
            if expr.get("type") == "EachOf":
                tcs.extend(expr.get("expressions", []))
            elif expr.get("type") == "TripleConstraint":
                tcs.append(expr)
        for tc in tcs:
            assert "predicate" in tc, f"{name}: TripleConstraint missing predicate: {tc}"

    @pytest.mark.parametrize("name", ["Film", "Building", "Person"])
    def test_dbpedia_shexje_datatypeor_shape(self, name):
        """DBpedia datatypeOr shapes must be serialised as ShapeOr in ShexJE."""
        from shaclex_py.parser.shacl_parser        import parse_shacl_file
        from shaclex_py.converter.shacl_to_canonical  import convert_shacl_to_canonical
        from shaclex_py.converter.canonical_to_shexje import convert_canonical_to_shexje
        from shaclex_py.serializer.shexje_serializer  import serialize_shexje

        path   = os.path.join(SHACL_DBPEDIA_DIR, f"{name}.ttl")
        shacl  = parse_shacl_file(path)
        canon  = convert_shacl_to_canonical(shacl)
        # Only test if there are datatypeOr shapes
        has_datatype_or = any(s.datatypeOr for s in canon.shapes)
        if not has_datatype_or:
            pytest.skip(f"{name} has no datatypeOr shapes")
        shexje = convert_canonical_to_shexje(canon)
        d      = json.loads(serialize_shexje(shexje))
        shape_or_shapes = [s for s in d["shapes"] if s.get("type") == "ShapeOr"]
        assert len(shape_or_shapes) >= 1, f"{name}: expected ShapeOr for datatypeOr in ShexJE"


# ── Cross-dataset preservation statistics (used for documentation) ────────────

def _collect_preservation_stats(chain_fn, file_list, ref_fn=None):
    """Run chain_fn on each file and return aggregate stats.

    Returns:
        dict with keys: files_ok, files_fail, shapes_in, shapes_out,
                        props_in, props_out, failures
    """
    from shaclex_py.serializer.json_serializer import serialize_json

    if ref_fn is None:
        ref_fn = chain_fn   # compare to itself (just checks completion)

    stats = {
        "files_ok": 0, "files_fail": 0,
        "shapes_in": 0, "shapes_out": 0,
        "props_in": 0, "props_out": 0,
        "failures": [],
    }
    for path in file_list:
        try:
            out = chain_fn(path)
            stats["files_ok"] += 1
            stats["shapes_out"] += _shape_count(out)
            stats["props_out"]  += _prop_count(out)
        except Exception as exc:
            stats["files_fail"] += 1
            stats["failures"].append((_basename(path), str(exc)))
    return stats


class TestStatisticsCollection:
    """Collect and print statistics across all 8 chains for all datasets.

    These tests always pass; they are used to generate the documentation
    table in docs/evaluation.md.  Run with -s to see the printed output.
    """

    def _print_stats(self, label, stats):
        print(f"\n  {label}")
        print(f"    Files OK:   {stats['files_ok']}")
        print(f"    Files fail: {stats['files_fail']}")
        print(f"    Shapes out: {stats['shapes_out']}")
        print(f"    Props out:  {stats['props_out']}")
        if stats["failures"]:
            for f, e in stats["failures"]:
                print(f"    FAIL {f}: {e}")

    def test_shacl_chain1_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain1, _shacl_yago_files())
        self._print_stats("Chain 1 (SHACL→JSON→SHACL) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shacl_chain2_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain2, _shacl_yago_files())
        self._print_stats("Chain 2 (SHACL→ShexJE→SHACL) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shacl_chain1_stats_dbpedia(self, capsys):
        stats = _collect_preservation_stats(_chain1, _shacl_dbpedia_files())
        self._print_stats("Chain 1 (SHACL→JSON→SHACL) — DBpedia", stats)
        assert stats["files_fail"] == 0

    def test_shacl_chain2_stats_dbpedia(self, capsys):
        stats = _collect_preservation_stats(_chain2, _shacl_dbpedia_files())
        self._print_stats("Chain 2 (SHACL→ShexJE→SHACL) — DBpedia", stats)
        assert stats["files_fail"] == 0

    def test_shacl_chain3_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain3, _shacl_yago_files())
        self._print_stats("Chain 3 (SHACL→JSON→ShEx→JSON→SHACL) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shacl_chain4_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain4, _shacl_yago_files())
        self._print_stats("Chain 4 (SHACL→ShexJE→ShEx→ShexJE→SHACL) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain5_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain5, _shex_yago_files())
        self._print_stats("Chain 5 (ShEx→JSON→ShEx) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain6_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain6, _shex_yago_files())
        self._print_stats("Chain 6 (ShEx→ShexJE→ShEx) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain5_stats_wes(self, capsys):
        stats = _collect_preservation_stats(_chain5, _shex_wes_files())
        self._print_stats("Chain 5 (ShEx→JSON→ShEx) — Wikidata WES", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain6_stats_wes(self, capsys):
        stats = _collect_preservation_stats(_chain6, _shex_wes_files())
        self._print_stats("Chain 6 (ShEx→ShexJE→ShEx) — Wikidata WES", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain7_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain7, _shex_yago_files())
        self._print_stats("Chain 7 (ShEx→JSON→SHACL→JSON→ShEx) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain8_stats_yago(self, capsys):
        stats = _collect_preservation_stats(_chain8, _shex_yago_files())
        self._print_stats("Chain 8 (ShEx→ShexJE→SHACL→ShexJE→ShEx) — YAGO", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain7_stats_wes(self, capsys):
        stats = _collect_preservation_stats(_chain7, _shex_wes_files())
        self._print_stats("Chain 7 (ShEx→JSON→SHACL→JSON→ShEx) — Wikidata WES", stats)
        assert stats["files_fail"] == 0

    def test_shex_chain8_stats_wes(self, capsys):
        stats = _collect_preservation_stats(_chain8, _shex_wes_files())
        self._print_stats("Chain 8 (ShEx→ShexJE→SHACL→ShexJE→ShEx) — Wikidata WES", stats)
        assert stats["files_fail"] == 0
