# Evaluation

## Roundtrip Cycle Tests

Every dataset was put through a full information-preserving cycle:

- **SHACL → JSON → ShEx → JSON** (DBpedia, YAGO SHACL source)
- **ShEx → JSON → ShEx → JSON** (YAGO ShEx source, WES Wikidata Entity Shapes)

The cycle verifies that no information is silently dropped: the canonical JSON produced at the start must exactly match the canonical JSON produced at the end.

### What is verified

The comparison is **deep** — it checks the **actual value** of every field, not just field types:

- `targetClass` IRI
- `closed` flag
- `cardinality` (`min` and `max` integers)
- Constraint field **type and value**: `datatype` IRI, `classRef` IRI, `classRefOr` sorted list, `nodeKind` string, `hasValue` value, `inValues` sorted list, `iriStem` string, `pattern` regex string, `nodeRef` IRI, `datatypeOr` sorted list

---

### YAGO SHACL → JSON → ShEx → JSON (37 files)

| Pattern | Occurrences | Preserved |
|---|---|---|
| `targetClass` | 37 | 37/37 (100%) |
| `closed` flag | 37 | 37/37 (100%) |
| `cardinality` | 670 | 670/670 (100%) |
| `sh:datatype` | 375 | 375/375 (100%) |
| `sh:class` (single) | 217 | 217/217 (100%) |
| `sh:or` classes (`classRefOr`) | 28 | 28/28 (100%) |
| `sh:nodeKind` | 11 | 11/11 (100%) |
| `sh:pattern` → `iriStem` | 37 | 37/37 (100%) |

---

### DBpedia SHACL → JSON → ShEx → JSON (20 files)

| Pattern | Occurrences | Preserved |
|---|---|---|
| `targetClass` | 32 | 32/32 (100%) |
| `closed` flag | 32 | 32/32 (100%) |
| `cardinality` | 1 082 | 1 082/1 082 (100%) |
| `sh:datatype` | 612 | 612/612 (100%) |
| `sh:class` (single) | 420 | 420/420 (100%) |
| `sh:node` ref (`nodeRef`) | 12 | 12/12 (100%) |
| `sh:or` datatypes at NodeShape (`datatypeOr`) | 12 | 12/12 (100%) |

---

### YAGO ShEx → JSON → ShEx → JSON (37 files)

| Pattern | Occurrences | Preserved |
|---|---|---|
| `targetClass` | 37 | 37/37 (100%) |
| `closed` flag | 37 | 37/37 (100%) |
| `cardinality` | 643 | 643/643 (100%) |
| `sh:datatype` | 366 | 366/366 (100%) |
| `sh:class` (single) | 192 | 192/192 (100%) |
| `sh:or` classes (`classRefOr`) | 29 | 29/29 (100%) |
| `sh:nodeKind` | 12 | 12/12 (100%) |
| `sh:pattern` → `iriStem` | 36 | 36/36 (100%) |
| `sh:node` ref (`nodeRef`) | 8 | 8/8 (100%) |

---

### WES Wikidata ShEx → JSON → ShEx → JSON (53 files)

| Pattern | Occurrences | Preserved |
|---|---|---|
| `targetClass` | 53 | 53/53 (100%) |
| `closed` flag | 53 | 53/53 (100%) |
| `cardinality` | 1 914 | 1 914/1 914 (100%) |
| `sh:datatype` | 496 | 496/496 (100%) |
| `sh:class` (single) | 640 | 640/640 (100%) |
| `sh:or` classes (`classRefOr`) | 280 | 280/280 (100%) |
| `sh:nodeKind` | 382 | 382/382 (100%) |
| `sh:hasValue` | 13 | 13/13 (100%) |
| `sh:in` (`inValues`) | 6 | 6/6 (100%) |
| `sh:pattern` → `iriStem` | 2 | 2/2 (100%) |
| `sh:node` ref (`nodeRef`) | 95 | 95/95 (100%) |

---

### Grand total — 147 files, zero differences

| Metric | Grand total |
|---|---|
| Files completing cycle | **147/147 (100%)** |
| Shapes preserved | **159/159 (100%)** |
| Properties preserved | **4 309/4 309 (100%)** |
| Constraint type + value preserved | **4 269/4 269 (100%)** |
| Cardinality preserved | **4 309/4 309 (100%)** |
| `datatypeOr` shape lists preserved | **12/12 (100%)** |

> **Known approximation — `sh:or` property alternatives**: All 1 082 DBpedia properties are structurally preserved (100%). However, the `sh:or ([ sh:property ... ] [ sh:property ... ])` pattern at NodeShape level loses its *disjunction grouping*: branches are flattened into a union of independent optional properties. No constraint data is dropped, but the "exactly one branch" semantics are not representable in the canonical model or ShEx. See [Mapping Rules](mapping-rules.md#property-alternative-groups--sh:or-with-sh:property-items-at-nodeshape-level) for details.

---

## Evaluation Against YAGO Ground Truth

The translator was evaluated against 37 paired SHACL/ShEx files from the [YAGO knowledge graph](https://yago-knowledge.org/):

| Direction | Predicate match | Shape name match |
|---|---|---|
| SHACL → ShEx | 99.9% (706/707) | 94.7% (195/206) |
| ShEx → SHACL | 99.3% (669/674) | — |

The small gaps are due to semantic differences: primarily `rdf:type` / `sh:targetClass` handling and auxiliary shape naming conventions. See [Mapping Rules — Semantic Differences](mapping-rules.md#semantic-differences-summary) for a full explanation.
