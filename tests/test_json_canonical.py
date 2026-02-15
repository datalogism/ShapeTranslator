"""Tests for canonical JSON intermediate representation.

Verifies that semantically equivalent SHACL and ShEx shapes produce
identical canonical JSON output.
"""
import json
import os

import pytest

from shaclex_py.parser.shacl_parser import parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex_file
from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
from shaclex_py.serializer.json_serializer import serialize_json

SHACL_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")
SHEX_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")


def _shacl_json(name: str) -> str:
    """Parse SHACL file and return canonical JSON string."""
    shacl = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
    return serialize_json(convert_shacl_to_canonical(shacl))


def _shex_json(name: str) -> str:
    """Parse ShEx file and return canonical JSON string."""
    shex = parse_shex_file(os.path.join(SHEX_DIR, f"{name}.shex"))
    return serialize_json(convert_shex_to_canonical(shex))


# ── Structural tests ──────────────────────────────────────────────


class TestStructure:
    """Basic structural tests for canonical JSON output."""

    def test_shacl_produces_valid_json(self):
        result = _shacl_json("Language")
        data = json.loads(result)
        assert "shapes" in data
        assert len(data["shapes"]) >= 1

    def test_shex_produces_valid_json(self):
        result = _shex_json("Language")
        data = json.loads(result)
        assert "shapes" in data
        assert len(data["shapes"]) >= 1

    def test_shape_has_required_fields(self):
        data = json.loads(_shacl_json("Language"))
        shape = data["shapes"][0]
        assert "name" in shape
        assert "closed" in shape
        assert "properties" in shape

    def test_property_has_required_fields(self):
        data = json.loads(_shacl_json("Language"))
        prop = data["shapes"][0]["properties"][0]
        assert "path" in prop
        assert "cardinality" in prop
        assert "min" in prop["cardinality"]
        assert "max" in prop["cardinality"]

    def test_target_class_present(self):
        data = json.loads(_shacl_json("Language"))
        shape = data["shapes"][0]
        assert shape["targetClass"] == "http://schema.org/Language"

    def test_shex_target_class(self):
        data = json.loads(_shex_json("Language"))
        shape = data["shapes"][0]
        assert shape["targetClass"] == "http://schema.org/Language"


# ── Determinism tests ─────────────────────────────────────────────


class TestDeterminism:
    """Verify that output is deterministic (same input → same output)."""

    def test_shacl_deterministic(self):
        a = _shacl_json("Language")
        b = _shacl_json("Language")
        assert a == b

    def test_shex_deterministic(self):
        a = _shex_json("Gender")
        b = _shex_json("Gender")
        assert a == b

    def test_properties_sorted_by_path(self):
        data = json.loads(_shacl_json("Language"))
        paths = [p["path"] for p in data["shapes"][0]["properties"]]
        assert paths == sorted(paths)

    def test_shapes_sorted_by_name(self):
        data = json.loads(_shex_json("Person"))
        names = [s["name"] for s in data["shapes"]]
        assert names == sorted(names)


# ── Normalization tests ───────────────────────────────────────────


class TestNormalization:
    """Test specific normalization rules."""

    def test_shacl_cardinality_defaults(self):
        """SHACL default {0,*} should be explicit."""
        data = json.loads(_shacl_json("Language"))
        # rdfs:comment has no min/maxCount → default {0,*}
        comment_prop = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://www.w3.org/2000/01/rdf-schema#comment"
        )
        assert comment_prop["cardinality"] == {"min": 0, "max": -1}

    def test_shex_cardinality_star(self):
        """ShEx * → {0,-1}."""
        data = json.loads(_shex_json("Language"))
        comment_prop = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://www.w3.org/2000/01/rdf-schema#comment"
        )
        assert comment_prop["cardinality"] == {"min": 0, "max": -1}

    def test_shacl_rdf_type_skipped(self):
        """rdf:type + hasValue should be skipped when targetClass is present."""
        data = json.loads(_shacl_json("Event"))
        paths = [p["path"] for p in data["shapes"][0]["properties"]]
        assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" not in paths

    def test_shex_rdf_type_skipped(self):
        """rdf:type [Class] should be skipped when it maps to targetClass."""
        data = json.loads(_shex_json("Event"))
        paths = [p["path"] for p in data["shapes"][0]["properties"]]
        assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" not in paths

    def test_shacl_pattern_to_iri_stem(self):
        """sh:pattern '^http://...' should become iriStem."""
        data = json.loads(_shacl_json("Language"))
        sameas_prop = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://www.w3.org/2002/07/owl#sameAs"
        )
        assert "iriStem" in sameas_prop
        assert sameas_prop["iriStem"] == "http://www.wikidata.org/entity"

    def test_shex_iri_stem(self):
        """ShEx IriStem should become iriStem field."""
        data = json.loads(_shex_json("Language"))
        sameas_prop = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://www.w3.org/2002/07/owl#sameAs"
        )
        assert "iriStem" in sameas_prop
        assert sameas_prop["iriStem"] == "http://www.wikidata.org/entity"

    def test_shacl_class_ref(self):
        """sh:class should become classRef."""
        data = json.loads(_shacl_json("Person"))
        birth_place = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://schema.org/birthPlace"
        )
        assert birth_place["classRef"] == "http://schema.org/Place"

    def test_shex_shape_ref_resolved_to_class_ref(self):
        """@<Place> auxiliary shape should resolve to classRef."""
        data = json.loads(_shex_json("Person"))
        birth_place = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://schema.org/birthPlace"
        )
        assert birth_place["classRef"] == "http://schema.org/Place"

    def test_shacl_or_constraints(self):
        """sh:or class list should become classRefOr (sorted)."""
        data = json.loads(_shacl_json("Event"))
        organizer = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://schema.org/organizer"
        )
        assert "classRefOr" in organizer
        assert organizer["classRefOr"] == sorted(organizer["classRefOr"])

    def test_shex_multi_class_resolved(self):
        """Multi-class auxiliary shape should become classRefOr."""
        data = json.loads(_shex_json("Event"))
        organizer = next(
            p for p in data["shapes"][0]["properties"]
            if p["path"] == "http://schema.org/organizer"
        )
        assert "classRefOr" in organizer


# ── Exact-match tests ─────────────────────────────────────────────


class TestExactMatch:
    """Test that SHACL and ShEx produce identical canonical JSON."""

    def test_gender_exact_match(self):
        shacl = _shacl_json("Gender")
        shex = _shex_json("Gender")
        assert shacl == shex, _diff_report("Gender", shacl, shex)

    def test_language_exact_match(self):
        shacl = _shacl_json("Language")
        shex = _shex_json("Language")
        assert shacl == shex, _diff_report("Language", shacl, shex)

    def test_event_exact_match(self):
        shacl = _shacl_json("Event")
        shex = _shex_json("Event")
        assert shacl == shex, _diff_report("Event", shacl, shex)

    def test_person_exact_match(self):
        shacl = _shacl_json("Person")
        shex = _shex_json("Person")
        assert shacl == shex, _diff_report("Person", shacl, shex)


# ── Batch conversion tests ───────────────────────────────────────


class TestBatchConversion:
    """Ensure all YAGO files convert without error."""

    def test_all_shacl_files_convert(self):
        files = [f[:-4] for f in os.listdir(SHACL_DIR) if f.endswith(".ttl")]
        for name in files:
            result = _shacl_json(name)
            data = json.loads(result)
            assert "shapes" in data, f"Failed for {name}"

    def test_all_shex_files_convert(self):
        files = [f[:-5] for f in os.listdir(SHEX_DIR) if f.endswith(".shex")]
        for name in files:
            result = _shex_json(name)
            data = json.loads(result)
            assert "shapes" in data, f"Failed for {name}"


def _diff_report(name: str, shacl_json: str, shex_json: str) -> str:
    """Generate a readable diff report for test failure messages."""
    shacl_data = json.loads(shacl_json)
    shex_data = json.loads(shex_json)

    lines = [f"\n{'='*60}", f"DIFF REPORT for {name}", f"{'='*60}"]

    shacl_props = {
        p["path"]: p for p in shacl_data["shapes"][0]["properties"]
    } if shacl_data["shapes"] else {}
    shex_props = {
        p["path"]: p for p in shex_data["shapes"][0]["properties"]
    } if shex_data["shapes"] else {}

    all_paths = sorted(set(shacl_props.keys()) | set(shex_props.keys()))
    for path in all_paths:
        sp = shacl_props.get(path)
        xp = shex_props.get(path)
        if sp != xp:
            lines.append(f"\n  PATH: {path}")
            lines.append(f"  SHACL: {json.dumps(sp, indent=4)}")
            lines.append(f"  ShEx:  {json.dumps(xp, indent=4)}")

    # Compare top-level shape fields
    if shacl_data["shapes"] and shex_data["shapes"]:
        s_shape = {k: v for k, v in shacl_data["shapes"][0].items() if k != "properties"}
        x_shape = {k: v for k, v in shex_data["shapes"][0].items() if k != "properties"}
        if s_shape != x_shape:
            lines.append(f"\n  SHAPE METADATA DIFF:")
            lines.append(f"  SHACL: {s_shape}")
            lines.append(f"  ShEx:  {x_shape}")

    return "\n".join(lines)
