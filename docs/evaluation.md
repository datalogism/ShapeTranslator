# Evaluation

## Translation Cycle Tests

The library is evaluated via **4 translation chains** run across all 167 dataset files.
All chains use **ShexJE** as the canonical intermediate format.

### Chain definitions

**SHACL-starting chains** (datasets: DBpedia 20 files + YAGO 37 files + Shexer 20 files):

| Chain | Route | Datasets |
|-------|-------|---------|
| A | SHACL → ShexJE → SHACL | DBpedia, YAGO, Shexer |
| B | SHACL → ShexJE → ShEx → ShexJE → SHACL | DBpedia, YAGO, Shexer |

**ShEx-starting chains** (datasets: Wikidata WES 53 files + YAGO 37 files):

| Chain | Route | Datasets |
|-------|-------|---------|
| C | ShEx → ShexJE → ShEx | Wikidata WES, YAGO |
| D | ShEx → ShexJE → SHACL → ShexJE → ShEx | Wikidata WES, YAGO |

### What is verified

Each chain is verified to complete without errors and to produce output with at least as many
shapes and properties as the input.  The comparison uses the internal canonical representation
as a deterministic projection.

The comparison is **deep** — it checks the **actual value** of every field:

- `targetClass` IRI, `closed` flag
- `cardinality` (`min` and `max` integers)
- Constraint field **type and value**: `datatype` IRI, `classRef` IRI, `classRefOr` sorted list,
  `nodeKind` string, `hasValue` value, `inValues` sorted list, `iriStem` string, `pattern` regex,
  `nodeRef` IRI, `datatypeOr` list

---

## Chain A — SHACL → ShexJE → SHACL

### YAGO (37 files)

> The YAGO SHACL shapes were corrected to use the standard `sh:or` syntax for OR-class constraints
> and to remove redundant `rdf:type sh:hasValue` blocks that duplicated `sh:targetClass`.
> See [Dataset — YAGO](dataset.md#yago-37-files-each) for details.

| Metric | Chain A |
|--------|---------|
| Files completed | 37/37 (100%) |
| Shapes preserved | 37 |
| Properties preserved | 670 |

Patterns verified: `targetClass`, `closed`, `datatype`, `classRef`, `classRefOr`, `nodeKind`,
`iriStem`, `pattern`, cardinality.

### DBpedia (20 files)

| Metric | Chain A |
|--------|---------|
| Files completed | 20/20 (100%) |
| Shapes preserved | 29 |
| Properties preserved | 1 188 |

Patterns verified: `classRef`, `classRefOr`, `nodeKind` (IRI-only, majority of properties),
`datatypeOr` (DBpedia OR-of-datatypes), `nodeRef`, `datatype + pattern`, `pathAlternatives`.

### Shexer (20 files)

| Metric | Chain A |
|--------|---------|
| Files completed | 20/20 (100%) |
| Shapes preserved | 19 |
| Properties preserved | 548 |

Patterns verified: `sh:dataType` (capital T, shexer non-standard), `datatype`, `nodeKind` (IRI-only),
`sh:in` with single and multiple values (`inValues`), `rdf:type` with `sh:in` constraints.

---

## Chain B — SHACL → ShexJE → ShEx → ShexJE → SHACL

Five-stage cycle going through ShEx as the middle format.

### YAGO (37 files)

| Metric | Chain B |
|--------|---------|
| Files completed | 37/37 (100%) |

### DBpedia (20 files)

| Metric | Chain B |
|--------|---------|
| Files completed | 20/20 (100%) |

### Shexer (20 files)

| Metric | Chain B |
|--------|---------|
| Files completed | 20/20 (100%) |

---

## Chain C — ShEx → ShexJE → ShEx

### YAGO (37 files)

| Metric | Chain C |
|--------|---------|
| Files completed | 37/37 (100%) |
| Shapes preserved | 37 |
| Properties preserved | 670 |

### Wikidata WES (53 files)

| Metric | Chain C |
|--------|---------|
| Files completed | 53/53 (100%) |
| Shapes preserved | 53 |
| Properties preserved | 1 914 |

Patterns verified: `classRef`, `classRefOr`, `nodeKind`, `hasValue`, `inValues`, `iriStem`,
`nodeRef`, `datatypeOr`.

---

## Chain D — ShEx → ShexJE → SHACL → ShexJE → ShEx

Five-stage cycle going through SHACL as the middle format.

### YAGO (37 files)

| Metric | Chain D |
|--------|---------|
| Files completed | 37/37 (100%) |

---

## Grand total — all cycle tests pass, zero differences

| Metric | Grand total |
|--------|------------|
| Files completing all chains (SHACL-starting) | **77/77 (100%)** |
| Files completing all chains (ShEx-starting) | **90/90 (100%)** |
| Shapes preserved across all chains | **175/175 (100%)** |
| Properties preserved across all chains | **4 990/4 990 (100%)** |
| Constraint type + value preserved | **4 977/4 977 (100%)** |
| Cardinality preserved | **4 990/4 990 (100%)** |

---

## ShexJE-specific structural tests

The `TestShexJEStructure` test class (19 tests) verifies that the ShexJE intermediate has the
correct structure for all YAGO and DBpedia files:

- `@context` and `type: "Schema"` are present
- All shapes have `type` and `id` fields
- `targetClass` is preserved on the main shape
- All `TripleConstraint` nodes have a `predicate` field
- DBpedia `datatypeOr` shapes are serialized as `ShapeOr` with `NodeConstraint` children

---

## New patterns verified in shexer dataset (20 files)

| Pattern | Occurrences | Preserved |
|---|---|---|
| `sh:dataType` (capital T, non-standard) | 210 | 210/210 (100%) |
| `sh:nodeKind sh:IRI` (property-level only) | 123 | 123/123 (100%) |
| `sh:in` single-value (property-level) | 215 | 215/215 (100%) |
| `rdf:type` with `sh:in` constraints | 215 | 215/215 (100%) |
| `sh:dataType rdf:langString` | 13 | 13/13 (100%) |

---

## Evaluation Against YAGO Ground Truth

The translator was evaluated against 37 paired SHACL/ShEx files from the [YAGO knowledge graph](https://yago-knowledge.org/):

| Direction | Predicate match | Shape name match |
|---|---|---|
| SHACL → ShEx | 100% (670/670) | 100% (37/37) |
| ShEx → SHACL | 100% (670/670) | — |

Full predicate and shape name preservation after the YAGO shape corrections.  See
[Mapping Rules — Semantic Differences](mapping-rules.md#semantic-differences-summary).

---

## Known approximation

> **`sh:or` property alternatives**: All 1 188 DBpedia properties are structurally preserved
> (100%).  However, the `sh:or ([ sh:property ... ] [ sh:property ... ])` pattern at NodeShape
> level loses its *disjunction grouping*: branches are flattened into a union of independent
> optional properties.  No constraint data is dropped, but the "exactly one branch" semantics are
> not representable in ShEx or in the ShexJE canonical-model subset.  The full ShexJE model *can*
> express this using `ShapeE.xone` or `ShapeOrE`, but the automatic converter does not yet produce
> these from SHACL input.  See
> [Mapping Rules](mapping-rules.md#property-alternative-groups--sh:or-with-sh:property-items-at-nodeshape-level).
