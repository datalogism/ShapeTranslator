# Architecture

## Pipeline

shaclex-py is organized as a three-stage pipeline — **parse → convert → serialize** — with two
language-neutral intermediate models at the center: the **Canonical JSON** model (simplified) and
the **ShexJE** model (full-featured, the new canonical format).

```
             SHACL (Turtle)                    ShEx (ShExC)
                  |                                 |
          shacl_parser.py                    shex_parser.py
                  |                                 |
                  v                                 v
          +--------------+                  +--------------+
          | SHACL Schema | <--- convert --> |  ShEx Schema |
          +--------------+                  +--------------+
                  |           \        /           |
        shacl_serializer.py    ↓      ↓    shex_serializer.py
                  |         +----------+          |
                  |         | Canonical|          |
                  |         |   JSON   |          |
                  |         +----------+          |
                  |              |                |
                  |      +--------------+         |
                  |      |   ShexJE     |         |
                  |      | (*.shexje)   |         |
                  |      +--------------+         |
                  |         |      |              |
                  v         v      v              v
             SHACL (Turtle)    (*.json / *.shexje)    ShEx (ShExC)
```

All four representations — SHACL, ShEx, Canonical JSON, and ShexJE — are fully interconvertible.

### Available conversion directions

| Direction flag     | Input             | Output            |
|--------------------|-------------------|-------------------|
| `shacl2shex`       | SHACL `.ttl`      | ShEx `.shex`      |
| `shex2shacl`       | ShEx `.shex`      | SHACL `.ttl`      |
| `shacl2json`       | SHACL `.ttl`      | Canonical JSON    |
| `shex2json`        | ShEx `.shex`      | Canonical JSON    |
| `json2shacl`       | Canonical JSON    | SHACL `.ttl`      |
| `json2shex`        | Canonical JSON    | ShEx `.shex`      |
| `shacl2shexje`     | SHACL `.ttl`      | ShexJE `.shexje`  |
| `shex2shexje`      | ShEx `.shex`      | ShexJE `.shexje`  |
| `shexje2shacl`     | ShexJE `.shexje`  | SHACL `.ttl`      |
| `shexje2shex`      | ShexJE `.shexje`  | ShEx `.shex`      |
| `json2shexje`      | Canonical JSON    | ShexJE `.shexje`  |

## Project Structure

```
├── src/shaclex_py/
│   ├── __init__.py              Public API + version
│   ├── __main__.py              python -m shaclex_py support
│   ├── cli.py                   CLI entry point (all 11 directions)
│   ├── schema/
│   │   ├── common.py            Shared types (Cardinality, IRI, NodeKind, Path, ...)
│   │   ├── shacl.py             SHACL dataclasses (SHACLSchema, NodeShape, PropertyShape)
│   │   ├── shex.py              ShEx dataclasses (ShExSchema, Shape, TripleConstraint)
│   │   ├── canonical.py         Canonical JSON model (CanonicalSchema, CanonicalShape)
│   │   └── shexje.py            ShexJE model (ShexJESchema, ShapeE, TripleConstraintE, ...)
│   ├── converter/
│   │   ├── shacl_to_shex.py       SHACL schema → ShEx schema (direct)
│   │   ├── shex_to_shacl.py       ShEx schema → SHACL schema (direct)
│   │   ├── shacl_to_canonical.py  SHACL schema → Canonical JSON
│   │   ├── shex_to_canonical.py   ShEx schema → Canonical JSON
│   │   ├── canonical_to_shacl.py  Canonical JSON → SHACL schema
│   │   ├── canonical_to_shex.py   Canonical JSON → ShEx schema
│   │   ├── canonical_to_shexje.py Canonical JSON → ShexJE    ← new
│   │   └── shexje_to_canonical.py ShexJE → Canonical JSON    ← new
│   ├── parser/
│   │   ├── shacl_parser.py      Turtle/SHACL → SHACL schema (uses rdflib)
│   │   ├── shex_parser.py       ShExC → ShEx schema (custom tokenizer)
│   │   ├── json_parser.py       JSON file/string → CanonicalSchema
│   │   └── shexje_parser.py     ShexJE JSON → ShexJESchema    ← new
│   ├── serializer/
│   │   ├── shacl_serializer.py  SHACL schema → Turtle string (uses rdflib)
│   │   ├── shex_serializer.py   ShEx schema → ShExC string
│   │   ├── json_serializer.py   Canonical schema → JSON string
│   │   └── shexje_serializer.py ShexJESchema → JSON string    ← new
│   └── utils/
│       └── wikidata.py          Wikidata SPARQL label resolver
├── tests/
│   ├── test_translation_cycles.py  8-chain cycle tests (Canonical JSON vs ShexJE)  ← new
│   └── ...                         96+ other tests across 10 test files
├── dataset/
│   ├── shacl_yago/              37 YAGO SHACL reference files (.ttl)
│   ├── shex_yago/               37 YAGO ShEx reference files (.shex)
│   ├── shex_wes/                53 Wikidata Entity Shapes (.shex)
│   └── shacl_dbpedia/           20 DBpedia SHACL shapes (.ttl)
├── docs/
│   ├── architecture.md          This file
│   ├── shexje-spec.md           ShexJE language specification  ← new
│   ├── evaluation.md            Cycle test results
│   ├── mapping-rules.md         SHACL ↔ ShEx mapping guide
│   ├── translation-coverage.md  Supported/approximated/unsupported constructs
│   └── ...
├── main.py                      Thin CLI wrapper (backward compat)
└── pyproject.toml
```

## Relationship to weso/shaclex

This project is a Python companion to [weso/shaclex](https://github.com/weso/shaclex), the Scala reference implementation for SHACL/ShEx interoperability. The module layout (`schema`, `converter`, `parser`, `serializer`) mirrors the architecture of shaclex to make the two projects easy to navigate side by side.

## Canonical JSON format (simplified)

The **Canonical JSON** model is the simplified lingua franca of the pipeline used for deterministic
comparison and for converting between SHACL and ShEx. It is designed to be:

- **Deterministic** — shapes and properties are sorted alphabetically (with full-content
  secondary key for duplicate paths) so that equivalent schemas always produce identical JSON
- **Language-neutral** — does not embed SHACL or ShEx syntax; all IRIs are stored as full strings
- **Portable** — can be saved to disk and later converted to either SHACL or ShEx

### Shape structure

```json
{
  "shapes": [
    {
      "name": "Person",
      "targetClass": "http://schema.org/Person",
      "closed": false,
      "properties": [
        {
          "path": "http://schema.org/birthDate",
          "datatype": "http://www.w3.org/2001/XMLSchema#date",
          "cardinality": { "min": 0, "max": 1 }
        }
      ]
    }
  ]
}
```

### Constraint fields

The primary constraint fields are mutually exclusive — at most one is set per property. `pattern` is the exception: it is **additive** and may accompany any primary constraint (most commonly `datatype`).

| Field | Mutually exclusive? | Meaning |
|---|---|---|
| `datatype` | yes | `sh:datatype` / ShEx datatype NodeConstraint |
| `classRef` | yes | `sh:class` (single) / ShEx `@<Aux>` shape reference |
| `classRefOr` | yes | `sh:or` with classes / ShEx OR auxiliary shape |
| `nodeKind` | yes | `sh:nodeKind` / ShEx `IRI`, `LITERAL`, etc. |
| `hasValue` | yes | `sh:hasValue` / ShEx `[V]` |
| `inValues` | yes | `sh:in` / ShEx `[v1 v2]` |
| `iriStem` | yes | standalone `sh:pattern "^http://..."` / ShEx `[<stem>~]` |
| `pattern` | **no** | `sh:pattern` regex — may accompany `datatype` or stand alone |
| `nodeRef` | yes | `sh:node` / ShEx `@<ShapeRef>` |

### Shape-level fields

| Field | Meaning |
|---|---|
| `targetClass` | `sh:targetClass` / ShEx `rdf:type [C]` absorbed |
| `closed` | `sh:closed` / ShEx `CLOSED` |
| `datatypeOr` | `sh:or ([sh:datatype D1]...)` at NodeShape level (DBpedia pattern) — order preserved |

## ShexJE format (full-featured)

**ShexJE** (ShEx JSON Extended) is the new, full-featured canonical format. It is a proper superset
of the W3C ShexJ format extended for full SHACL compatibility.  See [ShexJE Specification](shexje-spec.md) for the complete language reference.

Key additions over Canonical JSON:

| Feature | ShexJE field |
|---------|-------------|
| All ShexJ constructs | Preserved verbatim |
| SHACL target declarations | `targetClass`, `targetNode`, `targetSubjectsOf`, `targetObjectsOf` |
| Validation metadata | `severity`, `message`, `deactivated` |
| Logical operators | `and`, `or`, `not`, `xone` (shape-level); `ShapeXoneE` type |
| Property paths | `InversePath`, `SequencePath`, `AlternativePath`, `ZeroOrMorePath`, … |
| Property-pair constraints | `equals`, `disjoint`, `lessThan`, `lessThanOrEquals` |
| Qualified value shapes | `qualifiedValueShape`, `qualifiedMinCount`, `qualifiedMaxCount` |
| SPARQL constraints | `SparqlConstraintE` in `sparql` array on shapes |
| Language facets | `languageIn`, `uniqueLang` on NodeConstraint |
| Numeric/string facets | Full ShexJ facets: `minLength`, `maxLength`, `minInclusive`, … |
| Shape extensions | `extends`, `restricts`, `semActs`, `annotations` |
| Canonical JSON shorthands | `classRef`, `classRefOr`, `iriStem`, `hasValue`, `in` on TripleConstraintE |
