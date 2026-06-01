# Architecture

## Pipeline

shaclex-py is organized as a three-stage pipeline — **parse → convert → serialize** — with
**ShexJE** as the single language-neutral canonical format at the center.

Every SHACL ↔ ShEx conversion routes through ShexJE as a mandatory intermediate.
No converter speaks directly from SHACL to ShEx or vice-versa; each step is
implemented once, tested independently, and composed.

```
        SHACL (Turtle)                        ShEx (ShExC)
               │                                    │
       shacl_parser.py                      shex_parser.py
               │                                    │
               ▼                                    ▼
        SHACL Schema                          ShEx Schema
               │                                    │
  shacl_to_shexje.py                    shex_to_shexje.py
               │                                    │
               └──────────────┬─────────────────────┘
                              ▼
                       ShexJE Schema
                     (canonical format)
                              │
               ┌──────────────┴─────────────────────┐
               │                                    │
  shexje_to_shacl.py                    shexje_to_shex.py
               │                                    │
               ▼                                    ▼
        SHACL Schema                          ShEx Schema
               │                                    │
  shacl_serializer.py                    shex_serializer.py
               │                                    │
               ▼                                    ▼
        SHACL (Turtle)                        ShEx (ShExC)
```

`shacl_to_shex.py` and `shex_to_shacl.py` are thin wrappers that compose the
two-step chain transparently, preserving the same public API:

```python
# shacl_to_shex.py
def convert_shacl_to_shex(shacl, label_map=None):
    shexje = convert_shacl_to_shexje(shacl)
    return convert_shexje_to_shex(shexje)

# shex_to_shacl.py
def convert_shex_to_shacl(shex):
    shexje = convert_shex_to_shexje(shex)
    return convert_shexje_to_shacl(shexje)
```

### Available conversion directions

| Direction flag     | Pipeline                           | Input             | Output            |
|--------------------|------------------------------------|-------------------|-------------------|
| `shacl2shex`       | SHACL → ShexJE → ShEx              | SHACL `.ttl`      | ShEx `.shex`      |
| `shex2shacl`       | ShEx → ShexJE → SHACL              | ShEx `.shex`      | SHACL `.ttl`      |
| `shacl2shexje`     | SHACL → ShexJE (direct)            | SHACL `.ttl`      | ShexJE `.shexje`  |
| `shex2shexje`      | ShEx → ShexJE (direct)             | ShEx `.shex`      | ShexJE `.shexje`  |
| `shexje2shacl`     | ShexJE → SHACL (direct)            | ShexJE `.shexje`  | SHACL `.ttl`      |
| `shexje2shex`      | ShexJE → ShEx (direct)             | ShexJE `.shexje`  | ShEx `.shex`      |

---

## Project structure

```
├── src/shaclex_py/
│   ├── __init__.py              Public API + version
│   ├── __main__.py              python -m shaclex_py support
│   ├── cli.py                   CLI entry point (6 directions)
│   ├── schema/
│   │   ├── common.py            Shared types (Cardinality, IRI, NodeKind, Path, …)
│   │   ├── shacl.py             SHACL dataclasses (SHACLSchema, NodeShape, PropertyShape)
│   │   ├── shex.py              ShEx dataclasses (ShExSchema, Shape, TripleConstraint, …)
│   │   ├── shexje.py            ShexJE model (ShexJESchema, ShapeE, TripleConstraintE, …)
│   │   └── canonical.py         CanonicalSchema — language-neutral form for metrics/evaluation
│   ├── converter/
│   │   ├── shacl_to_shex.py       SHACL → ShEx  (wrapper: chains shacl_to_shexje + shexje_to_shex)
│   │   ├── shex_to_shacl.py       ShEx → SHACL  (wrapper: chains shex_to_shexje + shexje_to_shacl)
│   │   ├── shacl_to_shexje.py     SHACL → ShexJE  ← primary canonical converter
│   │   ├── shex_to_shexje.py      ShEx  → ShexJE  ← primary canonical converter
│   │   ├── shexje_to_shacl.py     ShexJE → SHACL  ← primary canonical converter
│   │   ├── shexje_to_shex.py      ShexJE → ShEx   ← primary canonical converter
│   │   ├── shacl_to_canonical.py  SHACL → CanonicalSchema  (metrics/evaluation layer only)
│   │   └── shexje_to_canonical.py ShexJE → CanonicalSchema (metrics/evaluation layer only)
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
├── tests/                       10 test files, ~940 tests
│   ├── test_mapping_rules.py        75 tests — one per documented mapping rule (§1–17)
│   ├── test_translation_cycles.py   4-chain ShexJE cycle tests (A, B, C, D)
│   ├── test_intershexje_roundtrip.py  ShEx ↔ ShexJE roundtrip across all YAGO shapes
│   ├── test_yago_fidelity.py        SHACL → ShEx fidelity vs. reference YAGO files
│   ├── test_yago_shexje_equivalence.py  Spotchecks on YAGO ShexJE canonical output
│   ├── test_shacl_parser.py         SHACL parser unit tests
│   ├── test_shex_parser.py          ShEx parser unit tests
│   ├── test_shacl_to_shex.py        SHACL → ShEx converter tests (YAGO dataset)
│   ├── test_shex_to_shacl.py        ShEx → SHACL converter tests
│   ├── test_pyshacl_compat.py       pySHACL validator compatibility
│   └── test_pyshex_compat.py        PyShEx validator compatibility
├── dataset/
│   ├── shacl_yago/              37 YAGO SHACL reference files (.ttl)
│   ├── shex_yago/               37 YAGO ShEx reference files (.shex)
│   ├── shex_wes/                53 Wikidata Entity Shapes (.shex)
│   ├── shacl_dbpedia/           20 DBpedia SHACL shapes (.ttl)
│   ├── shacl_shexer/            20 shexer-generated SHACL shapes (.ttl)
│   └── deepseek_dbpedia_shexje/ 20 DeepSeek-generated ShexJE files (.shexje)
├── docs/
│   ├── architecture.md          This file
│   ├── mapping-rules.md         SHACL ↔ ShEx mapping rules (17 patterns)
│   ├── shexje-spec.md           ShexJE language specification
│   ├── translation-coverage.md  Supported / approximated / unsupported constructs
│   ├── dataset.md               Dataset provenance and statistics
│   ├── evaluation.md            Cycle test results
│   ├── validator-compatibility.md  pySHACL / PyShEx compatibility notes
│   └── wikidata-labels.md       Wikidata label-enriched output guide
├── main.py                      Thin CLI wrapper (backward compat)
└── pyproject.toml
```

---

## Relationship to weso/shaclex

This project is a Python companion to [weso/shaclex](https://github.com/weso/shaclex), the Scala reference implementation for SHACL/ShEx interoperability. The module layout (`schema`, `converter`, `parser`, `serializer`) mirrors the architecture of shaclex to make the two projects easy to navigate side by side.

---

## ShexJE — the canonical format

**ShexJE** (ShEx JSON Extended) is the canonical interchange format of shaclex-py. It is a proper
superset of the W3C ShexJ format extended for full SHACL compatibility. See
[ShexJE Specification](shexje-spec.md) for the complete language reference.

### Key design properties

- **Deterministic** — shapes and properties are sorted alphabetically so that equivalent schemas always produce identical JSON
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

---

## CanonicalSchema — metrics and evaluation layer

`CanonicalSchema` (in `schema/canonical.py`) is a lightweight, language-neutral dataclass used **only** by the shapespresso evaluation and metrics layer — it is not part of the conversion pipeline. `shacl_to_canonical.py` and `shexje_to_canonical.py` convert to it purely for property-level classification and similarity scoring. It is never exposed in the public API or CLI.

The user-visible canonical format is **ShexJE** exclusively.

---

## Design decisions

### Why route SHACL ↔ ShEx through ShexJE?

The alternative — dedicated direct converters — was the original design. It was abandoned because:

1. **Duplicated rule logic.** Every mapping rule (cardinality, `sh:datatype`, `sh:class`, alternative paths, node-level value shapes, etc.) had to be implemented and maintained in two separate files. Any fix needed to be applied twice.
2. **Divergence.** The two converters drifted: `shacl_to_shexje.py` handled combined `sh:datatype + sh:pattern`, `sh:alternativePath` expansion, and node-level `NodeConstraintShape` emission correctly; the old `shacl_to_shex.py` did not.
3. **Single source of truth.** With the ShexJE pivot, each rule is implemented once and exercised by the full test suite of 75 mapping-rule tests.

### Companion value shapes

When a SHACL property uses `sh:class C` or `sh:or ([sh:class C1] [sh:class C2])`, the
converter emits a **companion value shape** in ShexJE — a `ShapeE` with `predicate = rdf:type`
and `values = [C, …]`. The companion shape ID is derived deterministically:

- Single class `C` → local name of `C` (e.g. `schema:Person` → `"Person"`)
- OR of classes → local names joined with `"Or"`, sorted (e.g. `schema:Organization` + `schema:Person` → `"OrganizationOrPerson"`)

Multiple properties pointing to the same class combination share **one** companion shape. The `shexje_to_shex.py` converter reuses an existing companion (by ID) rather than creating a duplicate.
