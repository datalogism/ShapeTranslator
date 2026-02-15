"""Tests for canonical JSON -> ShEx converter.

Strategy: parse original SHACL file, convert to canonical JSON, convert that
canonical to ShEx, then convert the ShEx back to canonical JSON and compare.
This roundtrip through canonical guarantees semantic equivalence.

We use the SHACL-derived canonical as the source of truth because the canonical
representation is language-neutral.
"""
import json
import os

import pytest

from shaclex_py.parser.shacl_parser import parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex_file
from shaclex_py.parser.json_parser import parse_canonical_file
from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
from shaclex_py.converter.canonical_to_shex import convert_canonical_to_shex
from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
from shaclex_py.serializer.shex_serializer import serialize_shex
from shaclex_py.serializer.json_serializer import serialize_json

SHACL_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")
SHEX_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")
SHACL_JSON_DIR = os.path.join(os.path.dirname(__file__), "..", "shacl_to_json")


def _roundtrip_canonical(name: str) -> tuple[dict, dict]:
    """SHACL -> canonical -> ShEx -> canonical roundtrip.

    Returns (original_canonical_dict, roundtrip_canonical_dict).
    """
    # Original SHACL -> canonical
    original_shacl = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
    original_canonical = convert_shacl_to_canonical(original_shacl)
    original_dict = original_canonical.to_dict()

    # canonical -> ShEx schema (with auxiliary shapes)
    shex = convert_canonical_to_shex(original_canonical)

    # ShEx -> canonical (resolves auxiliary shapes back)
    roundtrip_canonical = convert_shex_to_canonical(shex)
    roundtrip_dict = roundtrip_canonical.to_dict()

    return original_dict, roundtrip_dict


def _roundtrip_from_json_file(name: str) -> tuple[dict, dict]:
    """Load canonical JSON file -> ShEx -> canonical roundtrip.

    Returns (file_canonical_dict, roundtrip_canonical_dict).
    """
    json_path = os.path.join(SHACL_JSON_DIR, f"{name}.json")
    canonical = parse_canonical_file(json_path)
    file_dict = canonical.to_dict()

    # canonical -> ShEx -> canonical
    shex = convert_canonical_to_shex(canonical)
    roundtrip_canonical = convert_shex_to_canonical(shex)
    roundtrip_dict = roundtrip_canonical.to_dict()

    return file_dict, roundtrip_dict


# ── Structural tests ──────────────────────────────────────────────


class TestStructure:
    """Basic structural tests for canonical -> ShEx conversion."""

    def test_produces_valid_shex(self):
        original_shacl = parse_shacl_file(os.path.join(SHACL_DIR, "Language.ttl"))
        canonical = convert_shacl_to_canonical(original_shacl)
        shex = convert_canonical_to_shex(canonical)
        assert len(shex.shapes) >= 1

    def test_start_shape_set(self):
        original_shacl = parse_shacl_file(os.path.join(SHACL_DIR, "Language.ttl"))
        canonical = convert_shacl_to_canonical(original_shacl)
        shex = convert_canonical_to_shex(canonical)
        assert shex.start is not None
        assert shex.start.value == "Language"

    def test_target_class_becomes_rdf_type(self):
        original_shacl = parse_shacl_file(os.path.join(SHACL_DIR, "Language.ttl"))
        canonical = convert_shacl_to_canonical(original_shacl)
        shex = convert_canonical_to_shex(canonical)
        # The ShEx shape should have rdf:type constraint for targetClass
        output = serialize_shex(shex)
        assert "rdf:type" in output
        assert "schema:Language" in output

    def test_serializable(self):
        original_shacl = parse_shacl_file(os.path.join(SHACL_DIR, "Event.ttl"))
        canonical = convert_shacl_to_canonical(original_shacl)
        shex = convert_canonical_to_shex(canonical)
        output = serialize_shex(shex)
        assert "PREFIX" in output
        assert "EXTRA" in output

    def test_auxiliary_shapes_for_class_refs(self):
        original_shacl = parse_shacl_file(os.path.join(SHACL_DIR, "Event.ttl"))
        canonical = convert_shacl_to_canonical(original_shacl)
        shex = convert_canonical_to_shex(canonical)
        shape_names = {s.name.value for s in shex.shapes}
        assert "Place" in shape_names
        assert "Event" in shape_names


# ── Roundtrip canonical equality tests ────────────────────────────


class TestCanonicalRoundtrip:
    """SHACL -> canonical -> ShEx -> canonical must produce identical canonical."""

    def test_language_roundtrip(self):
        original, roundtrip = _roundtrip_canonical("Language")
        assert original == roundtrip, _diff_report("Language", original, roundtrip)

    def test_gender_roundtrip(self):
        original, roundtrip = _roundtrip_canonical("Gender")
        assert original == roundtrip, _diff_report("Gender", original, roundtrip)

    def test_event_roundtrip(self):
        original, roundtrip = _roundtrip_canonical("Event")
        assert original == roundtrip, _diff_report("Event", original, roundtrip)

    def test_person_roundtrip(self):
        original, roundtrip = _roundtrip_canonical("Person")
        assert original == roundtrip, _diff_report("Person", original, roundtrip)

    def test_belief_system_roundtrip(self):
        original, roundtrip = _roundtrip_canonical("BeliefSystem")
        assert original == roundtrip, _diff_report("BeliefSystem", original, roundtrip)


# ── JSON file roundtrip tests ─────────────────────────────────────


class TestFromJsonFile:
    """Load canonical JSON file -> ShEx -> canonical roundtrip."""

    def test_language_from_file(self):
        original, roundtrip = _roundtrip_from_json_file("Language")
        assert original == roundtrip, _diff_report("Language", original, roundtrip)

    def test_gender_from_file(self):
        original, roundtrip = _roundtrip_from_json_file("Gender")
        assert original == roundtrip, _diff_report("Gender", original, roundtrip)

    def test_event_from_file(self):
        original, roundtrip = _roundtrip_from_json_file("Event")
        assert original == roundtrip, _diff_report("Event", original, roundtrip)


# ── Batch tests ───────────────────────────────────────────────────


class TestBatch:
    """Ensure all 37 YAGO files roundtrip through canonical -> ShEx -> canonical."""

    def test_all_37_files_roundtrip(self):
        files = [f[:-4] for f in os.listdir(SHACL_DIR) if f.endswith(".ttl")]
        assert len(files) == 37
        for name in files:
            original, roundtrip = _roundtrip_canonical(name)
            assert original == roundtrip, (
                f"Roundtrip mismatch for {name}:\n"
                + _diff_report(name, original, roundtrip)
            )


# ── Helpers ───────────────────────────────────────────────────────


def _diff_report(name: str, original: dict, roundtrip: dict) -> str:
    """Generate a readable diff report for test failure messages."""
    lines = [f"\n{'='*60}", f"DIFF REPORT for {name}", f"{'='*60}"]

    orig_props = {
        p["path"]: p for p in original["shapes"][0]["properties"]
    } if original["shapes"] else {}
    rt_props = {
        p["path"]: p for p in roundtrip["shapes"][0]["properties"]
    } if roundtrip["shapes"] else {}

    all_paths = sorted(set(orig_props.keys()) | set(rt_props.keys()))
    for path in all_paths:
        op = orig_props.get(path)
        rp = rt_props.get(path)
        if op != rp:
            lines.append(f"\n  PATH: {path}")
            lines.append(f"  Original:  {json.dumps(op, indent=4)}")
            lines.append(f"  Roundtrip: {json.dumps(rp, indent=4)}")

    if original["shapes"] and roundtrip["shapes"]:
        o_shape = {k: v for k, v in original["shapes"][0].items() if k != "properties"}
        r_shape = {k: v for k, v in roundtrip["shapes"][0].items() if k != "properties"}
        if o_shape != r_shape:
            lines.append(f"\n  SHAPE METADATA DIFF:")
            lines.append(f"  Original:  {o_shape}")
            lines.append(f"  Roundtrip: {r_shape}")

    return "\n".join(lines)
