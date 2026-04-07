# Architecture

## Pipeline

shaclex-py is organized as a three-stage pipeline — **parse → convert → serialize** — with
**ShexJE** as the single language-neutral canonical format at the center.

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
                  |         |  ShexJE  |          |
                  |         | canonical|          |
                  |         +----------+          |
                  |              |                |
                  v              v                v
             SHACL (Turtle)   (*.shexje)    ShEx (ShExC)
```

All three representations — SHACL, ShEx, and ShexJE — are fully interconvertible.
Every SHACL ↔ ShEx conversion passes through ShexJE internally.

### Available conversion directions

| Direction flag     | Input             | Output            |
|--------------------|-------------------|-------------------|
| `shacl2shex`       | SHACL `.ttl`      | ShEx `.shex`      |
| `shex2shacl`       | ShEx `.shex`      | SHACL `.ttl`      |
| `shacl2shexje`     | SHACL `.ttl`      | ShexJE `.shexje`  |
| `shex2shexje`      | ShEx `.shex`      | ShexJE `.shexje`  |
| `shexje2shacl`     | ShexJE `.shexje`  | SHACL `.ttl`      |
| `shexje2shex`      | ShexJE `.shexje`  | ShEx `.shex`      |

## Project Structure

```
├── src/shaclex_py/
│   ├── __init__.py              Public API + version
│   ├── __main__.py              python -m shaclex_py support
│   ├── cli.py                   CLI entry point (6 directions)
│   ├── schema/
│   │   ├── common.py            Shared types (Cardinality, IRI, NodeKind, Path, ...)
│   │   ├── shacl.py             SHACL dataclasses (SHACLSchema, NodeShape, PropertyShape)
│   │   ├── shex.py              ShEx dataclasses (ShExSchema, Shape, TripleConstraint)
│   │   └── shexje.py            ShexJE model (ShexJESchema, ShapeE, TripleConstraintE, ...)
│   ├── converter/
│   │   ├── shacl_to_shex.py       SHACL schema → ShEx schema (direct)
│   │   ├── shex_to_shacl.py       ShEx schema → SHACL schema (direct)
│   │   ├── shacl_to_shexje.py     SHACL schema → ShexJE  ← canonical pipeline
│   │   ├── shex_to_shexje.py      ShEx schema  → ShexJE  ← canonical pipeline
│   │   ├── shexje_to_shacl.py     ShexJE → SHACL schema  ← canonical pipeline
│   │   └── shexje_to_shex.py      ShexJE → ShEx schema   ← canonical pipeline
│   ├── parser/
│   │   ├── shacl_parser.py      Turtle/SHACL → SHACL schema (uses rdflib)
│   │   ├── shex_parser.py       ShExC → ShEx schema (custom tokenizer)
│   │   └── shexje_parser.py     ShexJE JSON → ShexJESchema
│   ├── serializer/
│   │   ├── shacl_serializer.py  SHACL schema → Turtle string (uses rdflib)
│   │   ├── shex_serializer.py   ShEx schema → ShExC string
│   │   └── shexje_serializer.py ShexJESchema → JSON string
│   └── utils/
│       └── wikidata.py          Wikidata SPARQL label resolver
├── tests/
│   ├── test_translation_cycles.py  4-chain ShexJE cycle tests (A, B, C, D)
│   └── ...                         90+ other tests across 9 test files
├── dataset/
│   ├── shacl_yago/              37 YAGO SHACL reference files (.ttl)
│   ├── shex_yago/               37 YAGO ShEx reference files (.shex)
│   ├── shex_wes/                53 Wikidata Entity Shapes (.shex)
│   └── shacl_dbpedia/           20 DBpedia SHACL shapes (.ttl)
├── docs/
│   ├── architecture.md          This file
│   ├── shexje-spec.md           ShexJE language specification
│   ├── evaluation.md            Cycle test results
│   ├── mapping-rules.md         SHACL ↔ ShEx mapping guide
│   ├── translation-coverage.md  Supported/approximated/unsupported constructs
│   └── ...
├── main.py                      Thin CLI wrapper (backward compat)
└── pyproject.toml
```

## Relationship to weso/shaclex

This project is a Python companion to [weso/shaclex](https://github.com/weso/shaclex), the Scala reference implementation for SHACL/ShEx interoperability. The module layout (`schema`, `converter`, `parser`, `serializer`) mirrors the architecture of shaclex to make the two projects easy to navigate side by side.

## ShexJE format — the canonical format

**ShexJE** (ShEx JSON Extended) is the canonical interchange format of shaclex-py. It is a proper
superset of the W3C ShexJ format extended for full SHACL compatibility. See
[ShexJE Specification](shexje-spec.md) for the complete language reference.

### Key design properties

- **Deterministic** — shapes and properties are sorted alphabetically so that equivalent schemas
  always produce identical JSON
- **Language-neutral** — does not embed SHACL or ShEx syntax; all IRIs are stored as full strings
- **Portable** — can be saved to `.shexje` files and later converted to either SHACL or ShEx
- **Full-featured** — preserves all ShexJ constructs plus SHACL extensions

### ShexJE additions over plain ShexJ

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
| Canonical shorthands | `classRef`, `classRefOr`, `iriStem`, `hasValue`, `in` on TripleConstraintE |

### Internal implementation note

Internally, the converters use a normalized `CanonicalSchema` dataclass as a lightweight
intermediate step within the SHACL → ShexJE and ShexJE → SHACL pipelines. This is an
implementation detail — it is not exposed in the public API or CLI. The user-visible canonical
format is ShexJE exclusively.
