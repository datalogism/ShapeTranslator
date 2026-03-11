# Architecture

## Pipeline

shaclex-py is organized as a three-stage pipeline — **parse → convert → serialize** — with a language-neutral canonical JSON model at the center.

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
        shacl_serializer.py    Canonical    shex_serializer.py
                  |           /   JSON  \          |
                  v          v          v          v
             SHACL (Turtle)    (*.json)       ShEx (ShExC)
                               |
                          json_parser.py
                               |
                               v
                       +--------------+
                       |  Canonical   |--- canonical_to_shacl ---> SHACL
                       |   Schema     |--- canonical_to_shex  ---> ShEx
                       +--------------+
```

All three representations — SHACL, ShEx, and canonical JSON — are fully interconvertible. The canonical JSON format serves both as a deterministic comparison tool and as a portable interchange format.

## Project Structure

```
├── src/shaclex_py/
│   ├── __init__.py              Public API + version
│   ├── __main__.py              python -m shaclex_py support
│   ├── cli.py                   CLI entry point
│   ├── schema/
│   │   ├── common.py            Shared types (Cardinality, IRI, NodeKind, Path, ...)
│   │   ├── shacl.py             SHACL dataclasses (SHACLSchema, NodeShape, PropertyShape)
│   │   ├── shex.py              ShEx dataclasses (ShExSchema, Shape, TripleConstraint)
│   │   └── canonical.py         Canonical JSON model (CanonicalSchema, CanonicalShape)
│   ├── converter/
│   │   ├── shacl_to_shex.py       SHACL schema -> ShEx schema
│   │   ├── shex_to_shacl.py       ShEx schema -> SHACL schema
│   │   ├── shacl_to_canonical.py  SHACL schema -> canonical JSON
│   │   ├── shex_to_canonical.py   ShEx schema -> canonical JSON
│   │   ├── canonical_to_shacl.py  Canonical JSON -> SHACL schema
│   │   └── canonical_to_shex.py   Canonical JSON -> ShEx schema
│   ├── parser/
│   │   ├── shacl_parser.py      Turtle/SHACL -> SHACL schema (uses rdflib)
│   │   ├── shex_parser.py       ShExC -> ShEx schema (custom tokenizer)
│   │   └── json_parser.py       JSON file/string -> CanonicalSchema
│   ├── serializer/
│   │   ├── shacl_serializer.py  SHACL schema -> Turtle string (uses rdflib)
│   │   ├── shex_serializer.py   ShEx schema -> ShExC string
│   │   └── json_serializer.py   Canonical schema -> JSON string
│   └── utils/
│       └── wikidata.py          Wikidata SPARQL label resolver
├── tests/                       96+ tests across 7 test files
├── dataset/
│   ├── shacl_yago/              37 YAGO SHACL reference files (.ttl)
│   ├── shex_yago/               37 YAGO ShEx reference files (.shex)
│   ├── shex_wes/                53 Wikidata Entity Shapes (.shex)
│   └── shacl_dbpedia/           20 DBpedia SHACL shapes (.ttl)
├── docs/                        This documentation
├── main.py                      Thin CLI wrapper (backward compat)
└── pyproject.toml
```

## Relationship to weso/shaclex

This project is a Python companion to [weso/shaclex](https://github.com/weso/shaclex), the Scala reference implementation for SHACL/ShEx interoperability. The module layout (`schema`, `converter`, `parser`, `serializer`) mirrors the architecture of shaclex to make the two projects easy to navigate side by side.

## Canonical JSON format

The canonical JSON model is the lingua franca of the pipeline. It is designed to be:

- **Deterministic** — shapes and properties are sorted alphabetically so that equivalent schemas always produce identical JSON
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

### Constraint fields (mutually exclusive per property)

| Field | Meaning |
|---|---|
| `datatype` | `sh:datatype` / ShEx datatype NodeConstraint |
| `classRef` | `sh:class` (single) / ShEx `@<Aux>` shape reference |
| `classRefOr` | `sh:or` with classes / ShEx OR auxiliary shape |
| `nodeKind` | `sh:nodeKind` / ShEx `IRI`, `LITERAL`, etc. |
| `hasValue` | `sh:hasValue` / ShEx `[V]` |
| `inValues` | `sh:in` / ShEx `[v1 v2]` |
| `iriStem` | `sh:pattern "^http://..."` / ShEx `[<stem>~]` |
| `pattern` | `sh:pattern` (arbitrary regex) |
| `nodeRef` | `sh:node` / ShEx `@<ShapeRef>` |

### Shape-level fields

| Field | Meaning |
|---|---|
| `targetClass` | `sh:targetClass` / ShEx `rdf:type [C]` absorbed |
| `closed` | `sh:closed` / ShEx `CLOSED` |
| `datatypeOr` | `sh:or ([sh:datatype D1]...)` at NodeShape level (DBpedia pattern) |
