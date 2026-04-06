# Dataset

The `dataset/` directory contains reference files used for testing and evaluation.

| Directory | Format | Files | Source |
|---|---|---|---|
| `dataset/shacl_yago/` | SHACL (Turtle) | 37 | YAGO knowledge graph |
| `dataset/shex_yago/` | ShEx (ShExC) | 37 | YAGO knowledge graph |
| `dataset/shex_wes/` | ShEx (ShExC) | 53 | Wikidata Entity Shapes (WES) |
| `dataset/shacl_dbpedia/` | SHACL (Turtle) | 20 | DBpedia ontology shapes |

## YAGO (37 files each)

Paired SHACL and ShEx files covering a range of complexity from simple shapes (Gender, Language) to complex ones with class references, OR constraints, and IRI stems (Person, Politician, Event). Used for ground-truth evaluation — see [Evaluation](evaluation.md#evaluation-against-yago-ground-truth).

**Shape corrections (2025):** The SHACL files were updated to fix two issues present in the original export:

- **`sh:or` syntax standardised** — Properties using the non-standard `sh:class [ sh:or ( C1 C2 ) ]` form (where `sh:or` appeared as the value of `sh:class`) were rewritten to the correct SHACL form: `sh:or ( [ sh:class C1 ] [ sh:class C2 ] )`. Both forms are still accepted by the parser, but the dataset now uses only the standard form.
- **Redundant `rdf:type sh:hasValue` removed** — Four shapes (Country, Election, Event, Product) previously had a `sh:property [ sh:path rdf:type ; sh:hasValue <Class> ]` block that duplicated the `sh:targetClass` declaration. These redundant entries were removed.

One non-standard term appears in `Book.ttl`: `sh:classKind sh:IRI` (not in the SHACL spec). The parser silently ignores unknown predicates, so this property is treated as unconstrained.

## Wikidata Entity Shapes — WES (53 files)

ShEx files using Wikidata Q-codes as filenames. These test the [Wikidata label-aware ShEx generation](wikidata-labels.md) feature — shape references and comments use human-readable English labels resolved via SPARQL.

## DBpedia (20 files)

SHACL shapes from the DBpedia ontology. Introduced two new patterns now fully supported by the translator:

- **Named value shapes** — `sh:NodeShape` with `sh:or ([sh:datatype D1] [sh:datatype D2] ...)` at the shape level (e.g. `costValueShape` accepting multiple currency datatypes).
- **Property alternative groups** — `sh:or` on a `sh:NodeShape` with `sh:property` blocks as alternatives (e.g. `dbo:height` vs `dbo:Person/height`). These are flattened into a union — see [Mapping Rules](mapping-rules.md#property-alternative-groups--sh:or-with-sh:property-items-at-nodeshape-level) for the trade-off analysis.
