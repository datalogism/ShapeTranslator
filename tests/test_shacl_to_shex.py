"""Tests for SHACL -> ShEx converter."""
import os
import pytest
from shaclex_py.parser.shacl_parser import parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex_file
from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
from shaclex_py.serializer.shex_serializer import serialize_shex
from shaclex_py.schema.shex import EachOf, TripleConstraint, NodeConstraint, ShapeRef

SHACL_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shacl_yago")
SHEX_REF_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")


def _convert(name):
    shacl = parse_shacl_file(os.path.join(SHACL_DIR, f"{name}.ttl"))
    return convert_shacl_to_shex(shacl)


def _ref(name):
    return parse_shex_file(os.path.join(SHEX_REF_DIR, f"{name}.shex"))


def _get_tcs(schema, shape_idx=0):
    shape = schema.shapes[shape_idx]
    if isinstance(shape.expression, EachOf):
        return shape.expression.expressions
    elif isinstance(shape.expression, TripleConstraint):
        return [shape.expression]
    return []


def test_language_shape_count():
    result = _convert("Language")
    assert len(result.shapes) == 1


def test_language_has_rdf_type_constraint():
    result = _convert("Language")
    tcs = _get_tcs(result)
    rdf_type_tcs = [t for t in tcs if "rdf-syntax-ns#type" in t.predicate.value]
    assert len(rdf_type_tcs) == 1


def test_language_has_target_class_as_value_set():
    result = _convert("Language")
    tcs = _get_tcs(result)
    rdf_type_tc = [t for t in tcs if "rdf-syntax-ns#type" in t.predicate.value][0]
    assert isinstance(rdf_type_tc.constraint, NodeConstraint)
    assert rdf_type_tc.constraint.values[0].value.value == "http://schema.org/Language"


def test_language_owl_sameas_iri_stem():
    result = _convert("Language")
    tcs = _get_tcs(result)
    owl_tc = [t for t in tcs if "sameAs" in t.predicate.value and "owl" in t.predicate.value][0]
    assert isinstance(owl_tc.constraint, NodeConstraint)
    assert owl_tc.constraint.values is not None


def test_event_auxiliary_shapes():
    result = _convert("Event")
    shape_names = {s.name.value for s in result.shapes}
    assert "Event" in shape_names
    assert "Place" in shape_names
    # Should have auxiliary shapes for or-constraints
    assert len(result.shapes) >= 4


def test_event_organizer_shape_ref():
    result = _convert("Event")
    tcs = _get_tcs(result)
    org_tcs = [t for t in tcs if "organizer" in t.predicate.value]
    assert len(org_tcs) == 1
    assert isinstance(org_tcs[0].constraint, ShapeRef)


def test_person_many_shape_refs():
    result = _convert("Person")
    tcs = _get_tcs(result)
    ref_tcs = [t for t in tcs if isinstance(t.constraint, ShapeRef)]
    assert len(ref_tcs) >= 10


def test_cardinality_mapping():
    result = _convert("Language")
    tcs = _get_tcs(result)
    # rdfs:label has minCount=1 in SHACL → {1,*} in ShEx
    label_tc = [t for t in tcs if "label" in t.predicate.value][0]
    assert label_tc.cardinality.min == 1
    assert label_tc.cardinality.max == -1  # UNBOUNDED
    # schema:image has maxCount=1 → {0,1} in ShEx
    image_tc = [t for t in tcs if "image" in t.predicate.value][0]
    assert image_tc.cardinality.min == 0
    assert image_tc.cardinality.max == 1


def test_all_37_files_convert():
    """Ensure all 37 SHACL files convert without error."""
    files = [f for f in os.listdir(SHACL_DIR) if f.endswith('.ttl')]
    assert len(files) == 37
    for f in files:
        shacl = parse_shacl_file(os.path.join(SHACL_DIR, f))
        shex = convert_shacl_to_shex(shacl)
        assert len(shex.shapes) >= 1, f"No shapes in conversion of {f}"


def test_shape_count_comparison():
    """Compare shape counts between converted and reference."""
    files = [f.replace('.ttl', '') for f in os.listdir(SHACL_DIR) if f.endswith('.ttl')]
    for name in files:
        result = _convert(name)
        ref = _ref(name)
        # Allow some tolerance — auxiliary shapes may differ
        assert abs(len(result.shapes) - len(ref.shapes)) <= 3, (
            f"{name}: converted {len(result.shapes)} shapes vs ref {len(ref.shapes)}"
        )
