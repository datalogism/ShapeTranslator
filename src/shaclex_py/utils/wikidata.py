"""Wikidata SPARQL label resolver for ShEx shape generation.

When generating ShEx for Wikidata-based schemas, shape references (@<>) and
inline comments should use human-readable English labels rather than raw QIDs
(e.g. ``@<Human>`` instead of ``@<Q5>``).  This module fetches those labels
in a single batch query via the public Wikidata SPARQL endpoint and is
**disabled by default** — pass ``label_map`` explicitly to opt-in.

Typical usage::

    from shaclex_py.utils.wikidata import collect_iris_from_shex, fetch_labels

    schema = parse_shacl_file("shapes.ttl")
    shex   = convert_shacl_to_shex(schema)

    iris      = collect_iris_from_shex(shex)
    label_map = fetch_labels(iris)          # one SPARQL round-trip

    print(serialize_shex(shex, label_map=label_map))
"""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ── IRI patterns ────────────────────────────────────────────────────────────

_QID_RE = re.compile(r"https?://www\.wikidata\.org/entity/(Q\d+)$")
_PID_RE = re.compile(r"https?://www\.wikidata\.org/prop/direct/(P\d+)$")

WD_BASE  = "http://www.wikidata.org/entity/"
WDT_BASE = "http://www.wikidata.org/prop/direct/"

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


# ── Public helpers ──────────────────────────────────────────────────────────

def is_wikidata_iri(iri: str) -> bool:
    """Return True if *iri* is a Wikidata entity (``wd:``) or direct property (``wdt:``)."""
    return bool(_QID_RE.match(iri) or _PID_RE.match(iri))


def is_wikidata_schema(prefixes) -> bool:
    """Return True if the prefix list contains the Wikidata ``wdt:`` namespace."""
    for pfx in prefixes:
        if pfx.name == "wdt" and "wikidata.org" in pfx.iri:
            return True
    return False


def fetch_labels(iris: list[str], lang: str = "en") -> dict[str, str]:
    """Batch-fetch English labels for a list of Wikidata IRIs via SPARQL.

    Args:
        iris:  Full IRI strings — may include both ``wd:`` entities and
               ``wdt:`` direct-property IRIs.
        lang:  BCP-47 language code (default: ``"en"``).

    Returns:
        Mapping of IRI → label string for every IRI that has a label.
        IRIs not found in Wikidata or on network failure are silently omitted.

    This function makes **at most two** SPARQL requests (one for Q-items,
    one for P-properties) and caches nothing — call it once and reuse the
    returned dict.
    """
    qids = [_QID_RE.match(iri).group(1) for iri in iris if _QID_RE.match(iri)]
    pids = [_PID_RE.match(iri).group(1) for iri in iris if _PID_RE.match(iri)]

    result: dict[str, str] = {}
    if qids:
        result.update(_fetch_entity_labels(qids, lang))
    if pids:
        result.update(_fetch_property_labels(pids, lang))
    return result


def to_shape_name(label: str) -> str:
    """Convert a Wikidata English label to a CamelCase ShEx shape name.

    Examples::

        to_shape_name("author")                  # → "Author"
        to_shape_name("maintained by")            # → "MaintainedBy"
        to_shape_name("copyright license")        # → "CopyrightLicense"
        to_shape_name("political party")          # → "PoliticalParty"
        to_shape_name("WikiProject")              # → "WikiProject"
    """
    words = re.split(r"[\s\-_/\\()\[\]]+", label)
    return "".join(w[0].upper() + w[1:] if w else "" for w in words if w)


def collect_iris_from_shex(schema) -> list[str]:
    """Collect all Wikidata IRIs (QIDs and PIDs) from a :class:`ShExSchema`.

    Returns only IRIs that match ``is_wikidata_iri``.
    """
    from shaclex_py.schema.shex import (
        ShExSchema, EachOf, OneOf, TripleConstraint, NodeConstraint,
    )
    from shaclex_py.schema.common import IRI

    iris: set[str] = set()
    if not isinstance(schema, ShExSchema):
        return []

    for shape in schema.shapes:
        _collect_from_expr(shape.expression, iris)
        for e in shape.extra:
            iris.add(e.value)

    return [iri for iri in iris if is_wikidata_iri(iri)]


def collect_iris_from_shacl(schema) -> list[str]:
    """Collect all Wikidata IRIs from a :class:`SHACLSchema`."""
    from shaclex_py.schema.shacl import SHACLSchema

    iris: set[str] = set()
    if not isinstance(schema, SHACLSchema):
        return []

    for shape in schema.shapes:
        if shape.target_class:
            iris.add(shape.target_class.value)
        for ps in shape.properties:
            iris.add(ps.path.iri.value)
            if ps.datatype:
                iris.add(ps.datatype.value)
            if ps.class_:
                iris.add(ps.class_.value)
            if ps.or_constraints:
                for c in ps.or_constraints:
                    iris.add(c.value)

    return [iri for iri in iris if is_wikidata_iri(iri)]


def collect_iris_from_canonical(schema) -> list[str]:
    """Collect all Wikidata IRIs from a :class:`CanonicalSchema`."""
    from shaclex_py.schema.canonical import CanonicalSchema

    iris: set[str] = set()
    if not isinstance(schema, CanonicalSchema):
        return []

    for shape in schema.shapes:
        if shape.targetClass:
            iris.add(shape.targetClass)
        for prop in shape.properties:
            iris.add(prop.path)
            if prop.datatype:
                iris.add(prop.datatype)
            if prop.classRef:
                iris.add(prop.classRef)
            if prop.classRefOr:
                for c in prop.classRefOr:
                    iris.add(c)

    return [iri for iri in iris if is_wikidata_iri(iri)]


# ── Internal helpers ─────────────────────────────────────────────────────────

def _collect_from_expr(expr, iris: set[str]) -> None:
    """Recursively collect IRIs from a ShEx triple expression."""
    from shaclex_py.schema.shex import EachOf, OneOf, TripleConstraint, NodeConstraint
    from shaclex_py.schema.common import IRI

    if expr is None:
        return
    if isinstance(expr, TripleConstraint):
        iris.add(expr.predicate.value)
        if isinstance(expr.constraint, NodeConstraint):
            if expr.constraint.datatype:
                iris.add(expr.constraint.datatype.value)
            if expr.constraint.values:
                for v in expr.constraint.values:
                    if isinstance(v.value, IRI):
                        iris.add(v.value.value)
    elif isinstance(expr, (EachOf, OneOf)):
        for sub in expr.expressions:
            _collect_from_expr(sub, iris)


def _fetch_entity_labels(qids: list[str], lang: str) -> dict[str, str]:
    """SPARQL fetch for Q-items."""
    values = " ".join(f"wd:{q}" for q in qids)
    query = f"""SELECT ?item ?label WHERE {{
  VALUES ?item {{ {values} }}
  ?item rdfs:label ?label .
  FILTER(LANG(?label) = "{lang}")
}}"""
    result: dict[str, str] = {}
    for row in _run_sparql(query):
        iri = row["item"]["value"]
        result[iri] = row["label"]["value"]
    return result


def _fetch_property_labels(pids: list[str], lang: str) -> dict[str, str]:
    """SPARQL fetch for P-properties (using wd: entity IRI, mapped back to wdt:)."""
    values = " ".join(f"wd:{p}" for p in pids)
    query = f"""SELECT ?prop ?label WHERE {{
  VALUES ?prop {{ {values} }}
  ?prop rdfs:label ?label .
  FILTER(LANG(?label) = "{lang}")
}}"""
    result: dict[str, str] = {}
    for row in _run_sparql(query):
        entity_iri = row["prop"]["value"]   # http://www.wikidata.org/entity/P50
        pid = entity_iri.rsplit("/", 1)[-1]  # P50
        wdt_iri = f"{WDT_BASE}{pid}"
        result[wdt_iri] = row["label"]["value"]
    return result


def _run_sparql(query: str) -> list[dict]:
    """Execute one SPARQL query against the Wikidata endpoint."""
    params = urlencode({"query": query, "format": "json"})
    req = Request(
        f"{WIKIDATA_SPARQL}?{params}",
        headers={
            "User-Agent": "shaclex-py/0.1 (https://github.com/cringwald/shaclex-py)",
            "Accept": "application/sparql-results+json",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("results", {}).get("bindings", [])
    except (URLError, OSError, json.JSONDecodeError):
        return []
