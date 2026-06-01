"""InterShexJE translation roundtrip test suite.

Verifies that, for every schema file across all datasets, translating the
original format X1 through ShexJE and back to X2 yields a strictly equivalent
schema:

    normalize(X1 → ShexJE)  ≡  normalize(X2 → ShexJE)

where X2 is produced by serialising the intermediate ShexJE back to the
original surface syntax and re-parsing it:

    X1 → ShexJE → re-serialise → X2 → ShexJE

Three translation paths are exercised:

  ShEx roundtrip :  .shex → ShexJE → .shex → ShexJE
      dataset/shex_yago/            37 files
      dataset/shex_wes/             53 files

  SHACL roundtrip:  .ttl  → ShexJE → .ttl  → ShexJE
      dataset/shacl_yago/           37 files
      dataset/shacl_dbpedia/        16 files
      dataset/shacl_shexer/         16 files

  ShexJE roundtrip: .shexje → serialize JSON → parse → ShexJE
      dataset/deepseek_dbpedia_shexje/   6 files

Total: 165 roundtrip tests.

Normalisation
─────────────
Both ShexJE schemas (before and after the roundtrip) are reduced to a dict

    { targetClass IRI : { predicate IRI : PropSpec } }

using the same normalisation logic as test_yago_shexje_equivalence.py so that
companion-shape naming differences do not cause spurious failures.
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
    ShapeRefE,
    ShexJESchema,
    TripleConstraintE,
)

# ── Dataset directories ───────────────────────────────────────────────────────

_ROOT = os.path.join(os.path.dirname(__file__), "..")

SHEX_YAGO_DIR    = os.path.join(_ROOT, "dataset", "shex_yago")
SHEX_WES_DIR     = os.path.join(_ROOT, "dataset", "shex_wes")
SHACL_YAGO_DIR   = os.path.join(_ROOT, "dataset", "shacl_yago")
SHACL_DBPEDIA_DIR= os.path.join(_ROOT, "dataset", "shacl_dbpedia")
SHACL_SHEXER_DIR = os.path.join(_ROOT, "dataset", "shacl_shexer")
SHEXJE_DEEPSEEK_DIR = os.path.join(_ROOT, "dataset", "deepseek_dbpedia_shexje")


# ── File collection helpers ───────────────────────────────────────────────────

def _collect(directory: str, ext: str, tag: str, extra_marks=()) -> list:
    """Return pytest.param entries for all *ext* files in *directory*."""
    params = []
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(ext):
            name = os.path.splitext(fname)[0]
            path = os.path.join(directory, fname)
            marks = list(extra_marks)
            params.append(pytest.param(name, path, id=f"{tag}/{name}", marks=marks))
    return params


# SHeXer-generated SHACL uses non-standard patterns that do not roundtrip
# cleanly:
#   1. sh:in (ClassName) for rdf:type — converted to sh:class after roundtrip,
#      changing constraint_type from 'values' to 'class' in the normaliser.
#   2. sh:dataType (capital T) — non-standard keyword, ignored by the parser,
#      so those property constraints are absent after roundtrip.
_SHEXER_XFAIL = pytest.mark.xfail(
    reason=(
        "SHeXer SHACL uses sh:in for rdf:type and sh:dataType (capital T). "
        "After roundtrip, sh:in becomes sh:class (constraint_type 'values' → "
        "'class') and sh:dataType properties are lost.  These are known "
        "non-standard patterns that the converter does not preserve losslessly."
    ),
    strict=True,
)

_SHEX_YAGO_PARAMS   = _collect(SHEX_YAGO_DIR,     ".shex",   "yago_shex")
_SHEX_WES_PARAMS    = _collect(SHEX_WES_DIR,      ".shex",   "wes")
_SHACL_YAGO_PARAMS  = _collect(SHACL_YAGO_DIR,    ".ttl",    "yago_shacl")
_SHACL_DBPEDIA_PARAMS = _collect(SHACL_DBPEDIA_DIR, ".ttl",  "dbpedia")
_SHACL_SHEXER_PARAMS  = _collect(SHACL_SHEXER_DIR,  ".ttl",  "shexer",
                                  extra_marks=[_SHEXER_XFAIL])
_SHEXJE_DEEPSEEK_PARAMS = _collect(SHEXJE_DEEPSEEK_DIR, ".shexje", "deepseek")

_ALL_SHEX_PARAMS   = _SHEX_YAGO_PARAMS + _SHEX_WES_PARAMS
_ALL_SHACL_PARAMS  = _SHACL_YAGO_PARAMS + _SHACL_DBPEDIA_PARAMS + _SHACL_SHEXER_PARAMS


# ── PropSpec ──────────────────────────────────────────────────────────────────

class PropSpec(NamedTuple):
    min: Optional[int]
    max: Optional[int]
    constraint_type: str   # none|datatype|nodeKind|class|iriStem|pattern|values|ref
    constraint_value: Any


# ── Normalisation helpers (format-agnostic) ───────────────────────────────────

def _collect_tcs(expr) -> list[TripleConstraintE]:
    if isinstance(expr, TripleConstraintE):
        return [expr]
    if isinstance(expr, (EachOfE, OneOfE)):
        tcs: list[TripleConstraintE] = []
        for sub in expr.expressions:
            tcs.extend(_collect_tcs(sub))
        return tcs
    return []


def _companion_classes(shape: ShapeE) -> Optional[list[str]]:
    if shape.predicate is not None and shape.values is not None:
        iris = sorted(v for v in shape.values if isinstance(v, str))
        return iris if iris else None
    if isinstance(shape.expression, TripleConstraintE):
        ve = shape.expression.valueExpr
        if isinstance(ve, NodeConstraintE) and ve.values:
            iris = sorted(v for v in ve.values if isinstance(v, str))
            return iris if iris else None
    return None


def _resolve_constraint(value_expr, shape_map: dict) -> tuple[str, Any]:
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


def _normalize(schema: ShexJESchema) -> dict[str, dict[str, PropSpec]]:
    """Reduce ShexJE schema to ``{targetClass: {predicate: PropSpec}}``.

    Shapes without ``targetClass`` are ignored; companion value-shapes are
    resolved inline so that the comparison is naming-convention-independent.
    """
    shape_map = {s.id: s for s in schema.shapes if hasattr(s, "id") and s.id}
    result: dict[str, dict[str, PropSpec]] = {}
    for shape in schema.shapes:
        if not isinstance(shape, ShapeE) or shape.targetClass is None:
            continue
        tc_val = shape.targetClass
        target_class = tc_val[0] if isinstance(tc_val, list) else tc_val
        props: dict[str, PropSpec] = {}
        if shape.expression is not None:
            for tc in _collect_tcs(shape.expression):
                if tc.predicate is None:
                    continue
                ctype, cval = _resolve_constraint(tc.valueExpr, shape_map)
                props[tc.predicate] = PropSpec(tc.min, tc.max, ctype, cval)
        result[target_class] = props
    return result


# ── Roundtrip pipeline functions ──────────────────────────────────────────────

def _shex_roundtrip_norms(path: str) -> tuple[dict, dict]:
    """ShEx → ShexJE → ShEx → ShexJE; return (norm_before, norm_after)."""
    from shaclex_py.parser.shex_parser import parse_shex_file
    from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
    from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
    from shaclex_py.serializer.shex_serializer import serialize_shex

    shexje_1 = convert_shex_to_shexje(parse_shex_file(path))
    norm_before = _normalize(shexje_1)

    shex_2_str = serialize_shex(convert_shexje_to_shex(shexje_1))
    shexje_2 = convert_shex_to_shexje(parse_shex_file(shex_2_str))
    norm_after = _normalize(shexje_2)

    return norm_before, norm_after


def _shacl_roundtrip_norms(path: str) -> tuple[dict, dict]:
    """SHACL → ShexJE → SHACL → ShexJE; return (norm_before, norm_after)."""
    from shaclex_py.parser.shacl_parser import parse_shacl_file
    from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
    from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
    from shaclex_py.serializer.shacl_serializer import serialize_shacl

    shexje_1 = convert_shacl_to_shexje(parse_shacl_file(path))
    norm_before = _normalize(shexje_1)

    shacl_2_str = serialize_shacl(convert_shexje_to_shacl(shexje_1))
    shexje_2 = convert_shacl_to_shexje(parse_shacl_file(shacl_2_str))
    norm_after = _normalize(shexje_2)

    return norm_before, norm_after


def _shexje_roundtrip_norms(path: str) -> tuple[dict, dict]:
    """ShexJE → serialize JSON → parse ShexJE; return (norm_before, norm_after)."""
    from shaclex_py.parser.shexje_parser import parse_shexje_file
    from shaclex_py.serializer.shexje_serializer import serialize_shexje

    shexje_1 = parse_shexje_file(path)
    norm_before = _normalize(shexje_1)

    shexje_2_str = serialize_shexje(shexje_1)
    shexje_2 = parse_shexje_file(shexje_2_str)
    norm_after = _normalize(shexje_2)

    return norm_before, norm_after


# ── Core assertion ────────────────────────────────────────────────────────────

def _assert_roundtrip_equivalent(
    norm_before: dict[str, dict[str, PropSpec]],
    norm_after:  dict[str, dict[str, PropSpec]],
    label: str,
) -> None:
    """Assert that two normalised ShexJE schemas are identical after a roundtrip.

    Provides targeted diff messages so the source of divergence is immediately
    visible when a test fails.
    """
    if not norm_before and not norm_after:
        pytest.skip(f"{label}: no targetClass shapes in either side of roundtrip")

    lost_classes   = set(norm_before) - set(norm_after)
    gained_classes = set(norm_after)  - set(norm_before)
    assert not lost_classes, (
        f"{label}: targetClass(es) present before roundtrip but lost after: {lost_classes}"
    )
    assert not gained_classes, (
        f"{label}: unexpected targetClass(es) appeared after roundtrip: {gained_classes}"
    )

    for tc_iri in norm_before:
        before = norm_before[tc_iri]
        after  = norm_after[tc_iri]

        lost_preds   = set(before) - set(after)
        gained_preds = set(after)  - set(before)
        assert not lost_preds, (
            f"{label} [{tc_iri}]: predicates lost in roundtrip: {lost_preds}"
        )
        assert not gained_preds, (
            f"{label} [{tc_iri}]: unexpected predicates after roundtrip: {gained_preds}"
        )

        for pred in before:
            b, a = before[pred], after[pred]
            assert b.min == a.min, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"min changed {b.min!r} → {a.min!r}"
            )
            assert b.max == a.max, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"max changed {b.max!r} → {a.max!r}"
            )
            assert b.constraint_type == a.constraint_type, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"constraint_type changed {b.constraint_type!r} → {a.constraint_type!r}"
            )
            assert b.constraint_value == a.constraint_value, (
                f"{label} [{tc_iri}] <{pred}>: "
                f"constraint_value changed\n  before: {b.constraint_value!r}\n"
                f"  after:  {a.constraint_value!r}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Test classes
# ═══════════════════════════════════════════════════════════════════════════════

class TestShexRoundtrip:
    """ShEx → ShexJE → ShEx → ShexJE must produce equivalent normalised schemas.

    Covers 37 YAGO shapes and 53 WES (Wikidata Entity Shapes) schemas.
    The YAGO shapes use rdf:type as instance-of; the WES shapes use wdt:P31.
    After the roundtrip the serialiser always emits rdf:type, so the second
    conversion uses rdf:type — the normaliser handles both predicates uniformly.
    """

    @pytest.mark.parametrize("name,path", _ALL_SHEX_PARAMS)
    def test_shex_to_shexje_to_shex_roundtrip(self, name: str, path: str) -> None:
        before, after = _shex_roundtrip_norms(path)
        _assert_roundtrip_equivalent(before, after, f"ShEx roundtrip [{name}]")


class TestShaclRoundtrip:
    """SHACL → ShexJE → SHACL → ShexJE must produce equivalent normalised schemas.

    Covers three SHACL corpora with quite different characteristics:

    * shacl_yago     — clean YAGO shapes with sh:targetClass, simple constraints
    * shacl_dbpedia  — richer shapes: sh:or at shape level, sh:alternativePath,
                       combined sh:class + sh:nodeKind sh:IRI
    * shacl_shexer   — SHeXer-generated shapes: sh:in for rdf:type, compact
                       blank-node style, sh:targetClass at the end of the file
    """

    @pytest.mark.parametrize("name,path", _ALL_SHACL_PARAMS)
    def test_shacl_to_shexje_to_shacl_roundtrip(self, name: str, path: str) -> None:
        before, after = _shacl_roundtrip_norms(path)
        _assert_roundtrip_equivalent(before, after, f"SHACL roundtrip [{name}]")


class TestShexJERoundtrip:
    """ShexJE → serialize JSON → parse → ShexJE must recover the same schema.

    Covers six DeepSeek-generated DBpedia ShexJE files.  These use:

    * compact prefix notation for datatypes (e.g. ``"xsd:double"``)
    * lowercase nodeKind values (``"iri"`` instead of ``"IRI"``)
    * ``targetClass`` set directly on the Shape object

    The serialiser emits ``to_dict()`` verbatim, so compact IRIs survive the
    roundtrip unchanged; the normaliser compares them as plain strings.
    """

    @pytest.mark.parametrize("name,path", _SHEXJE_DEEPSEEK_PARAMS)
    def test_shexje_serialize_parse_roundtrip(self, name: str, path: str) -> None:
        before, after = _shexje_roundtrip_norms(path)
        _assert_roundtrip_equivalent(before, after, f"ShexJE roundtrip [{name}]")
