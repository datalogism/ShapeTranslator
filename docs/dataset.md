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

## Wikidata Entity Shapes — WES (53 files)

ShEx files using Wikidata Q-codes as filenames. These test the [Wikidata label-aware ShEx generation](wikidata-labels.md) feature — shape references and comments use human-readable English labels resolved via SPARQL.

## DBpedia (20 files)

SHACL shapes from the DBpedia ontology. Introduced two new patterns now fully supported by the translator:

- **Named value shapes** — `sh:NodeShape` with `sh:or ([sh:datatype D1] [sh:datatype D2] ...)` at the shape level (e.g. `costValueShape` accepting multiple currency datatypes).
- **Property alternative groups** — `sh:or` on a `sh:NodeShape` with `sh:property` blocks as alternatives (e.g. `dbo:height` vs `dbo:Person/height`). These are flattened into a union — see [Mapping Rules](mapping-rules.md#property-alternative-groups--sh:or-with-sh:property-items-at-nodeshape-level) for the trade-off analysis.
