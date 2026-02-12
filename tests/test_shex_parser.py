"""Tests for ShEx parser."""
import os
import pytest
from parsers.shex_parser import parse_shex_file
from models.shex_model import EachOf, TripleConstraint, NodeConstraint, ShapeRef


YAGO_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "shex_yago")


def test_parse_gender():
    schema = parse_shex_file(os.path.join(YAGO_DIR, "Gender.shex"))
    assert schema.start.value == "Gender"
    assert len(schema.shapes) == 1
    shape = schema.shapes[0]
    assert shape.name.value == "Gender"
    assert len(shape.extra) == 1
    assert shape.extra[0].value == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def test_parse_gender_constraints():
    schema = parse_shex_file(os.path.join(YAGO_DIR, "Gender.shex"))
    shape = schema.shapes[0]
    assert isinstance(shape.expression, EachOf)
    tcs = shape.expression.expressions
    assert len(tcs) == 8
    # Check rdf:type value set
    rdf_type_tc = tcs[0]
    assert rdf_type_tc.predicate.value == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    assert isinstance(rdf_type_tc.constraint, NodeConstraint)
    assert rdf_type_tc.constraint.values is not None


def test_parse_event_auxiliary_shapes():
    schema = parse_shex_file(os.path.join(YAGO_DIR, "Event.shex"))
    assert len(schema.shapes) == 5  # Event + Organizer, Participant, Place, Sponsor
    shape_names = {s.name.value for s in schema.shapes}
    assert "Event" in shape_names
    assert "Place" in shape_names
    assert "Organizer" in shape_names


def test_parse_person_shape_refs():
    schema = parse_shex_file(os.path.join(YAGO_DIR, "Person.shex"))
    main_shape = schema.shapes[0]
    assert isinstance(main_shape.expression, EachOf)
    ref_tcs = [
        tc for tc in main_shape.expression.expressions
        if isinstance(tc, TripleConstraint) and isinstance(tc.constraint, ShapeRef)
    ]
    assert len(ref_tcs) >= 10


def test_parse_cardinality():
    schema = parse_shex_file(os.path.join(YAGO_DIR, "Gender.shex"))
    shape = schema.shapes[0]
    tcs = shape.expression.expressions
    # rdfs:label rdf:langString + → min=1, max=UNBOUNDED
    label_tc = [tc for tc in tcs if "label" in tc.predicate.value][0]
    assert label_tc.cardinality.min == 1
    assert label_tc.cardinality.max == -1  # UNBOUNDED
    # schema:image xsd:anyURI ? → min=0, max=1
    image_tc = [tc for tc in tcs if "image" in tc.predicate.value][0]
    assert image_tc.cardinality.min == 0
    assert image_tc.cardinality.max == 1


def test_parse_all_37_files():
    """Ensure all 37 YAGO files parse without error."""
    files = [f for f in os.listdir(YAGO_DIR) if f.endswith('.shex')]
    assert len(files) == 37
    for f in files:
        schema = parse_shex_file(os.path.join(YAGO_DIR, f))
        assert len(schema.shapes) >= 1, f"No shapes in {f}"
