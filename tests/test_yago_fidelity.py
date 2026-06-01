"""YAGO translation-fidelity tests.

Verifies that the translator produces semantically equivalent shapes when
translating between SHACL and ShEx using the YAGO dataset, which provides
the same shapes in both formats as ground truth.

Two directions are tested for each of the 37 YAGO shapes:

  Direction A — SHACL → ShEx
    1. Parse original SHACL  → convert to ShexJE  (reference)
    2. Parse original ShEx   → convert to ShexJE  (ground truth)
    Both ShexJE schemas are normalised and compared property by property.

  Direction B — ShEx → SHACL
    1. Parse original ShEx   → convert to ShexJE  (reference)
    2. Parse original SHACL  → convert to ShexJE  (ground truth)
    Same normalised comparison.

Normalisation strategy
──────────────────────
Both schemas are reduced to a dict keyed by targetClass IRI, where the value
is a dict keyed by predicate IRI mapping to a ``PropSpec`` namedtuple:

    PropSpec(min, max, constraint_type, constraint_value)

Companion value shapes (rdf:type-only helper shapes) are resolved to their
class-IRI sets, making the comparison format-agnostic despite different
companion-shape naming conventions in SHACL vs ShEx.
"""
from __future__ import annotations

import os
from typing import Any, NamedTuple, Optional

import pytest

from shaclex_py.schema.shexje import (
    EachOfE,
    IriStemValue,
    NodeConstraintE,
    OneOfE,
    ShapeE,
    ShapeOrE,
    ShapeRefE,
    ShexJESchema,
    TripleConstraintE,
)

# ── Dataset paths ─────────────────────────────────────────────────────────────

_ROOT          = os.path.join(os.path.dirname(__file__), "..")
SHACL_YAGO_DIR = os.path.join(_ROOT, "dataset", "shacl_yago")
SHEX_YAGO_DIR  = os.path.join(_ROOT, "dataset", "shex_yago")

# All 37 shapes present in both datasets
YAGO_NAMES = sorted(
    os.path.splitext(f)[0]
    for f in os.listdir(SHACL_YAGO_DIR)
    if f.endswith(".ttl")
    and os.path.exists(os.path.join(SHEX_YAGO_DIR, f.replace(".ttl", ".shex")))
)


# ── Normalisation helpers ─────────────────────────────────────────────────────

class PropSpec(NamedTuple):
    min: Optional[int]
    max: Optional[int]
    constraint_type: str   # "none"|"datatype"|"nodeKind"|"class"|"iriStem"|"pattern"|"values"|"ref"
    constraint_value: Any  # IRI string, sorted list of IRIs, etc.


def _collect_tcs(expr) -> list[TripleConstraintE]:
    if isinstance(expr, TripleConstraintE):
        return [expr]
    if isinstance(expr, (EachOfE, OneOfE)):
        result: list[TripleConstraintE] = []
        for sub in expr.expressions:
            result.extend(_collect_tcs(sub))
        return result
    return []


def _companion_classes(shape: ShapeE) -> Optional[list[str]]:
    """Return sorted class IRIs if *shape* is a companion value shape, else None."""
    # Shorthand form: predicate + values
    if shape.predicate is not None and shape.values is not None:
        iris = sorted(v for v in shape.values if isinstance(v, str))
        return iris if iris else None
    # Full expression form: single TC rdf:type with NodeConstraint.values
    if isinstance(shape.expression, TripleConstraintE):
        ve = shape.expression.valueExpr
        if isinstance(ve, NodeConstraintE) and ve.values:
            iris = sorted(v for v in ve.values if isinstance(v, str))
            return iris if iris else None
    return None


def _resolve_constraint(value_expr, shape_map: dict) -> tuple[str, Any]:
    """Return (constraint_type, constraint_value) for a TripleConstraint valueExpr."""
    if value_expr is None:
        return ("none", None)

    if isinstance(value_expr, NodeConstraintE):
        if value_expr.datatype is not None:
            return ("datatype", value_expr.datatype)
        if value_expr.nodeKind is not None:
            return ("nodeKind", value_expr.nodeKind)
        if value_expr.values is not None:
            if len(value_expr.values) == 1 and isinstance(value_expr.values[0], IriStemValue):
                return ("iriStem", value_expr.values[0].stem)
            # Value set — normalise to sorted strings
            return ("values", sorted(str(v) for v in value_expr.values))
        if value_expr.pattern is not None:
            return ("pattern", value_expr.pattern)
        return ("none", None)

    if isinstance(value_expr, (str, ShapeRefE)):
        ref = value_expr if isinstance(value_expr, str) else value_expr.reference
        companion = shape_map.get(ref)
        if isinstance(companion, ShapeE):
            classes = _companion_classes(companion)
            if classes is not None:
                return ("class", classes)
        return ("ref", ref)

    return ("none", None)


def _normalize(shexje: ShexJESchema) -> dict[str, dict[str, PropSpec]]:
    """Reduce a ShexJE schema to ``{targetClass: {predicate: PropSpec}}``."""
    shape_map = {s.id: s for s in shexje.shapes if hasattr(s, "id") and s.id}

    result: dict[str, dict[str, PropSpec]] = {}
    for shape in shexje.shapes:
        if not isinstance(shape, ShapeE) or shape.targetClass is None:
            continue
        tc_val = shape.targetClass
        target_class = tc_val[0] if isinstance(tc_val, list) else tc_val

        props: dict[str, PropSpec] = {}
        if shape.expression is not None:
            for tc in _collect_tcs(shape.expression):
                pred = tc.predicate
                if pred is None:
                    continue
                ctype, cval = _resolve_constraint(tc.valueExpr, shape_map)
                props[pred] = PropSpec(
                    min=tc.min,
                    max=tc.max,
                    constraint_type=ctype,
                    constraint_value=cval,
                )
        result[target_class] = props
    return result


# ── Assertion helper ──────────────────────────────────────────────────────────

def _assert_equivalent(
    norm_ref: dict,
    norm_got: dict,
    label: str,
) -> None:
    """Assert two normalised schemas are semantically equivalent."""
    ref_classes = set(norm_ref)
    got_classes = set(norm_got)

    missing = ref_classes - got_classes
    extra   = got_classes - ref_classes
    assert not missing, f"{label}: missing targetClass(es) in output: {missing}"
    assert not extra,   f"{label}: unexpected extra targetClass(es) in output: {extra}"

    for tc_iri in ref_classes:
        ref_props = norm_ref[tc_iri]
        got_props = norm_got[tc_iri]

        missing_preds = set(ref_props) - set(got_props)
        extra_preds   = set(got_props) - set(ref_props)
        assert not missing_preds, (
            f"{label} [{tc_iri}]: missing predicates in output: {missing_preds}"
        )
        assert not extra_preds, (
            f"{label} [{tc_iri}]: unexpected extra predicates in output: {extra_preds}"
        )

        for pred, ref_spec in ref_props.items():
            got_spec = got_props[pred]

            assert ref_spec.min == got_spec.min, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"min mismatch ref={ref_spec.min} got={got_spec.min}"
            )
            assert ref_spec.max == got_spec.max, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"max mismatch ref={ref_spec.max} got={got_spec.max}"
            )
            assert ref_spec.constraint_type == got_spec.constraint_type, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"constraint_type mismatch "
                f"ref={ref_spec.constraint_type!r} got={got_spec.constraint_type!r}"
            )
            assert ref_spec.constraint_value == got_spec.constraint_value, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"constraint_value mismatch "
                f"ref={ref_spec.constraint_value!r} got={got_spec.constraint_value!r}"
            )


# ── Conversion helpers ────────────────────────────────────────────────────────

def _shacl_to_shexje(path: str) -> ShexJESchema:
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    return convert_shacl_to_shexje(parse_shacl_file(path))


def _shex_to_shexje(path: str) -> ShexJESchema:
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    return convert_shex_to_shexje(parse_shex_file(path))


def _shacl_roundtrip_via_shex(shacl_path: str) -> ShexJESchema:
    """SHACL → ShexJE → ShEx → ShexJE."""
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.serializer.shex_serializer import serialize_shex
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje

    shexje = _shacl_to_shexje(shacl_path)
    shex_str = serialize_shex(convert_shexje_to_shex(shexje))
    return convert_shex_to_shexje(parse_shex_file(shex_str))


def _shex_roundtrip_via_shacl(shex_path: str) -> ShexJESchema:
    """ShEx → ShexJE → SHACL → ShexJE."""
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.serializer.shacl_serializer import serialize_shacl
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje

    shexje = _shex_to_shexje(shex_path)
    shacl_str = serialize_shacl(convert_shexje_to_shacl(shexje))
    return convert_shacl_to_shexje(parse_shacl_file(shacl_str))


# ── Test classes ──────────────────────────────────────────────────────────────

class TestYAGO_SHACL_to_ShEx:
    """Direction A: translate SHACL → ShEx and compare against original ShEx.

    The original SHACL and the original ShEx are each converted to ShexJE and
    normalised.  The test verifies that translating SHACL all the way through
    ShEx and back to ShexJE yields the same normalised form as the ShEx
    ground truth.
    """

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_shacl_translated_to_shex_matches_original(self, name: str):
        shacl_path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shex_path  = os.path.join(SHEX_YAGO_DIR,  f"{name}.shex")

        # Ground truth: original ShEx → ShexJE
        norm_shex_original = _normalize(_shex_to_shexje(shex_path))

        # Translated: original SHACL → ShexJE → ShEx → ShexJE
        norm_shacl_via_shex = _normalize(_shacl_roundtrip_via_shex(shacl_path))

        _assert_equivalent(
            norm_shex_original,
            norm_shacl_via_shex,
            label=f"SHACL→ShEx [{name}]",
        )

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_shacl_and_shex_originals_agree(self, name: str):
        """Both original files should normalise to the same ShexJE form."""
        shacl_path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shex_path  = os.path.join(SHEX_YAGO_DIR,  f"{name}.shex")

        norm_shacl = _normalize(_shacl_to_shexje(shacl_path))
        norm_shex  = _normalize(_shex_to_shexje(shex_path))

        _assert_equivalent(
            norm_shacl,
            norm_shex,
            label=f"originals agree [{name}]",
        )


class TestYAGO_ShEx_to_SHACL:
    """Direction B: translate ShEx → SHACL and compare against original SHACL.

    The original ShEx and the original SHACL are each converted to ShexJE and
    normalised.  The test verifies that translating ShEx all the way through
    SHACL and back to ShexJE yields the same normalised form as the SHACL
    ground truth.
    """

    @pytest.mark.parametrize("name", YAGO_NAMES)
    def test_shex_translated_to_shacl_matches_original(self, name: str):
        shacl_path = os.path.join(SHACL_YAGO_DIR, f"{name}.ttl")
        shex_path  = os.path.join(SHEX_YAGO_DIR,  f"{name}.shex")

        # Ground truth: original SHACL → ShexJE
        norm_shacl_original = _normalize(_shacl_to_shexje(shacl_path))

        # Translated: original ShEx → ShexJE → SHACL → ShexJE
        norm_shex_via_shacl = _normalize(_shex_roundtrip_via_shacl(shex_path))

        _assert_equivalent(
            norm_shacl_original,
            norm_shex_via_shacl,
            label=f"ShEx→SHACL [{name}]",
        )
