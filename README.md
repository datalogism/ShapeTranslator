# shaclex-py

A bidirectional translator between **SHACL** (Shapes Constraint Language, Turtle format) and **ShEx** (Shape Expressions, ShExC compact syntax), built from scratch in Python.

Uses a language-neutral canonical JSON model as an intermediate representation, handling the semantic differences documented in [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html).

A Python companion to [weso/shaclex](https://github.com/weso/shaclex) — the module layout mirrors the Scala reference implementation.

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Pipeline diagram, project structure, canonical JSON format |
| [Mapping Rules](docs/mapping-rules.md) | Every supported pattern with SHACL / JSON / ShEx examples |
| [Translation Coverage](docs/translation-coverage.md) | Fully supported, approximated, and known gaps with fix guidance |
| [Evaluation](docs/evaluation.md) | Roundtrip cycle results (147 files, 4 309 properties, 0 differences) |
| [Wikidata Labels](docs/wikidata-labels.md) | Label-aware ShEx generation for Wikidata schemas |
| [Validator Compatibility](docs/validator-compatibility.md) | pySHACL and PyShEx integration examples |
| [Dataset](docs/dataset.md) | Reference dataset descriptions (YAGO, WES, DBpedia) |

## Installation

Requires Python 3.10+.

```bash
pip install -e .                    # core (rdflib only)
pip install -e ".[dev]"             # + development tools and validators
pip install -e ".[pyshacl]"         # + pySHACL validator
pip install -e ".[pyshex]"          # + PyShEx validator
pip install -e ".[validation]"      # + both validators
```

## Quick Start

### CLI

```bash
# SHACL → ShEx
shaclex-py --input shapes.ttl --direction shacl2shex

# ShEx → SHACL (output to file)
shaclex-py --input shapes.shex --direction shex2shacl --output shapes.ttl

# Convert a whole directory
shaclex-py --input-dir my_shacl/ --output-dir my_shex/ --direction shacl2shex

# Wikidata label-aware output
shaclex-py --input Q1172284.ttl --direction shacl2shex --wikidata-labels
```

Also available via `python -m shaclex_py` or the legacy `python main.py`.

### Python API

```python
from shaclex_py import parse_shacl_file, convert_shacl_to_shex, serialize_shex

shacl = parse_shacl_file("shapes.ttl")
shex  = convert_shacl_to_shex(shacl)
print(serialize_shex(shex))
```

```python
from shaclex_py import parse_shex_file, convert_shex_to_shacl, serialize_shacl

shex  = parse_shex_file("shapes.shex")
shacl = convert_shex_to_shacl(shex)
print(serialize_shacl(shacl))
```

## Testing

```bash
pytest tests/ -v
```

The suite covers: parser round-trips, converter structural comparisons, SHACL↔ShEx roundtrips for all 37 YAGO files, and exact-match canonical JSON comparisons.

## Roundtrip Evaluation (summary)

Tested across 147 files (YAGO, DBpedia, Wikidata WES) using deep value-comparison cycles:

| Metric | Result |
|---|---|
| Files completing cycle | **147/147 (100%)** |
| Properties preserved | **4 309/4 309 (100%)** |
| Constraint type + value preserved | **4 269/4 269 (100%)** |

> The only known approximation is `sh:or` property-alternative groups at NodeShape level (DBpedia pattern), which are flattened to a union — all property data is kept but disjunction grouping is lost. See [Translation Coverage](docs/translation-coverage.md#approximated-translations).
