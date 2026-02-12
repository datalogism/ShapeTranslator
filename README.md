# SHACL <-> ShEx Translator

A bidirectional translator between **SHACL** (Shapes Constraint Language, Turtle format) and **ShEx** (Shape Expressions, ShExC compact syntax), built from scratch in Python.

The translator converts between these two RDF validation languages using an intermediate model representation, handling the semantic differences documented in [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html) and informed by the [weso/shaclex](https://github.com/weso/shaclex) Scala reference implementation.

## Architecture

```
             SHACL (Turtle)                    ShEx (ShExC)
                  |                                 |
          shacl_parser.py                    shex_parser.py
                  |                                 |
                  v                                 v
          +--------------+                  +--------------+
          | SHACL Model  | <--- convert --> |  ShEx Model  |
          +--------------+                  +--------------+
                  |                                 |
        shacl_serializer.py                shex_serializer.py
                  |                                 |
                  v                                 v
             SHACL (Turtle)                    ShEx (ShExC)
```

The pipeline is: **parse** input into an internal model, **convert** between models, then **serialize** to the target format. This design keeps each concern isolated and allows roundtrip testing.

## Project Structure

```
├── models/
│   ├── common.py             Shared types (Cardinality, IRI, NodeKind, Path, etc.)
│   ├── shacl_model.py        SHACL dataclasses (SHACLSchema, NodeShape, PropertyShape)
│   └── shex_model.py         ShEx dataclasses (ShExSchema, Shape, TripleConstraint)
├── parsers/
│   ├── shacl_parser.py       Turtle/SHACL -> SHACL model (uses rdflib)
│   └── shex_parser.py        ShExC -> ShEx model (custom tokenizer)
├── converters/
│   ├── shacl_to_shex.py      SHACL model -> ShEx model
│   └── shex_to_shacl.py      ShEx model -> SHACL model
├── serializers/
│   ├── shacl_serializer.py   SHACL model -> Turtle string (uses rdflib)
│   └── shex_serializer.py    ShEx model -> ShExC string
├── tests/                    37 tests across 5 test files
├── dataset/
│   ├── shacl_yago/           37 YAGO SHACL reference files (.ttl)
│   └── shex_yago/            37 YAGO ShEx reference files (.shex)
├── shacl_to_shex/            Output: SHACL -> ShEx conversion results
├── shex_to_shacl/            Output: ShEx -> SHACL conversion results
├── main.py                   CLI entry point
└── requirements.txt
```

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

Dependencies:
- **rdflib** (>=7.0) -- SHACL/Turtle parsing and serialization
- **pytest** -- test runner

> Note: `pyshexc` and `ShExJSG` are listed in requirements.txt for reference but are not used at runtime. The ShEx parser is a custom implementation to avoid compatibility issues with Python 3.12+.

## Usage

### Single file conversion

```bash
# SHACL -> ShEx (output to stdout)
python main.py --input shapes.ttl --direction shacl2shex

# ShEx -> SHACL (output to file)
python main.py --input shapes.shex --direction shex2shacl --output shapes.ttl
```

### Batch conversion

```bash
# Convert a directory of files
python main.py --input-dir my_shacl/ --output-dir my_shex/ --direction shacl2shex

# Run the full YAGO dataset in both directions
python main.py --batch
```

### Python API

```python
from parsers.shacl_parser import parse_shacl_file
from converters.shacl_to_shex import convert_shacl_to_shex
from serializers.shex_serializer import serialize_shex

shacl = parse_shacl_file("shapes.ttl")
shex = convert_shacl_to_shex(shacl)
print(serialize_shex(shex))
```

```python
from parsers.shex_parser import parse_shex_file
from converters.shex_to_shacl import convert_shex_to_shacl
from serializers.shacl_serializer import serialize_shacl

shex = parse_shex_file("shapes.shex")
shacl = convert_shex_to_shacl(shex)
print(serialize_shacl(shacl))
```

## Mapping Rules

The converter handles the following SHACL/ShEx correspondences:

| SHACL | ShEx | Notes |
|---|---|---|
| `sh:NodeShape` | `<ShapeName> { ... }` | Shape container |
| `sh:targetClass C` | `rdf:type [C]` | Target class becomes a value set constraint |
| `sh:property [ sh:path P ]` | `P ...` | Property path becomes a predicate |
| `sh:datatype D` | `D` | Direct datatype mapping |
| `sh:class C` | `@<CShape>` | Class reference becomes a shape reference |
| `sh:class [ sh:or (A B) ]` | `@<AuxShape>` with `rdf:type [A B]` | OR classes become an auxiliary shape |
| `sh:nodeKind sh:IRI` | `IRI` | Node kind mapping |
| `sh:minCount m` / `sh:maxCount n` | `{m,n}`, `?`, `*`, `+` | Cardinality (defaults differ: SHACL {0,\*} vs ShEx {1,1}) |
| `sh:hasValue V` | `[V]` | Single-value set |
| `sh:in (v1 v2)` | `[v1 v2]` | Value set |
| `sh:pattern "^http://..."` | `[<http://...>~]` | Regex pattern to IRI stem |
| `EXTRA rdf:type` | _(always emitted)_ | Extra predicates for open typing |

### Semantic Differences

Some constructs do not have exact equivalents:

- **Default cardinality**: ShEx defaults to `{1,1}`, SHACL defaults to `{0,*}`. The converter always emits explicit cardinality to avoid ambiguity.
- **`sh:pattern`**: Only patterns matching IRI prefixes (`^http://...`) are converted to ShEx IRI stems. Arbitrary regex patterns have no ShEx equivalent.
- **`rdf:type` handling**: SHACL uses `sh:targetClass` for class targeting, while ShEx uses `rdf:type [Class]` inside the shape body. During ShEx-to-SHACL conversion, the `rdf:type` constraint is promoted to `sh:targetClass`.
- **Auxiliary shapes**: When SHACL uses `sh:class` or `sh:or`, the ShEx output generates auxiliary shapes (e.g., `<Place> EXTRA rdf:type { rdf:type [schema:Place] }`) to represent class constraints as shape references.

## Testing

```bash
pytest tests/ -v
```

The test suite includes:
- **Parser tests**: Verify all 37 YAGO files parse correctly in both formats
- **Converter tests**: Structural comparison against reference files
- **Roundtrip tests**: SHACL -> ShEx -> SHACL and ShEx -> SHACL -> ShEx for all 37 files

## Evaluation Against YAGO Ground Truth

The translator was evaluated against 37 paired SHACL/ShEx files from the [YAGO knowledge graph](https://yago-knowledge.org/):

| Direction | Predicate Match | Shape Name Match |
|---|---|---|
| SHACL -> ShEx | 99.9% (706/707) | 94.7% (195/206) |
| ShEx -> SHACL | 99.3% (669/674) | -- |

The small gaps are due to the semantic differences described above (primarily `rdf:type` / `sh:targetClass` handling and auxiliary shape naming).

## Dataset

The `dataset/` directory contains 37 paired files from the YAGO knowledge graph, originally sourced from [DoubleShapespresso](https://github.com/). Each pair consists of:
- `dataset/shacl_yago/<Name>.ttl` -- SHACL shape in Turtle format
- `dataset/shex_yago/<Name>.shex` -- Equivalent ShEx shape in ShExC format

These cover a range of complexity from simple shapes (Gender, Language) to complex ones with class references, OR constraints, and IRI stems (Person, Politician, Event).
