# shaclex-py

A bidirectional translator between **SHACL** (Shapes Constraint Language, Turtle format) and **ShEx** (Shape Expressions, ShExC compact syntax), built from scratch in Python.

The translator converts between these two RDF validation languages using an intermediate model representation, handling the semantic differences documented in [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html).

## Relationship to weso/shaclex

This project is a Python companion to [weso/shaclex](https://github.com/weso/shaclex), the Scala reference implementation for SHACL/ShEx interoperability. The module layout (`schema`, `converter`, `parser`, `serializer`) mirrors the architecture of shaclex to make the two projects easy to navigate side by side. Where shaclex provides the authoritative Scala-based toolkit, **shaclex-py** offers a lightweight pure-Python alternative suitable for scripting, prototyping, and integration into Python-based RDF workflows.

## Architecture

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

The pipeline is: **parse** input into an internal schema model, **convert** between models, then **serialize** to the target format. All three representations (SHACL, ShEx, canonical JSON) are fully interconvertible -- the canonical JSON format serves both as a deterministic comparison tool and as a portable interchange format that can be converted back to SHACL or ShEx.

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
│   │   ├── shacl_to_shex.py      SHACL schema -> ShEx schema
│   │   ├── shex_to_shacl.py      ShEx schema -> SHACL schema
│   │   ├── shacl_to_canonical.py  SHACL schema -> canonical JSON
│   │   ├── shex_to_canonical.py   ShEx schema -> canonical JSON
│   │   ├── canonical_to_shacl.py  Canonical JSON -> SHACL schema
│   │   └── canonical_to_shex.py   Canonical JSON -> ShEx schema
│   ├── parser/
│   │   ├── shacl_parser.py      Turtle/SHACL -> SHACL schema (uses rdflib)
│   │   ├── shex_parser.py       ShExC -> ShEx schema (custom tokenizer)
│   │   └── json_parser.py       JSON file/string -> CanonicalSchema
│   └── serializer/
│       ├── shacl_serializer.py  SHACL schema -> Turtle string (uses rdflib)
│       ├── shex_serializer.py   ShEx schema -> ShExC string
│       └── json_serializer.py   Canonical schema -> JSON string
├── tests/                       91 tests across 7 test files
├── dataset/
│   ├── shacl_yago/              37 YAGO SHACL reference files (.ttl)
│   └── shex_yago/               37 YAGO ShEx reference files (.shex)
├── main.py                      Thin CLI wrapper (backward compat)
└── pyproject.toml
```

## Installation

Requires Python 3.10+.

```bash
# Core (rdflib only)
pip install -e .

# With development tools + validators
pip install -e ".[dev]"

# With pySHACL validator only
pip install -e ".[pyshacl]"

# With PyShEx validator only
pip install -e ".[pyshex]"

# With both validators
pip install -e ".[validation]"
```

Dependencies:
- **rdflib** (>=7.0) -- SHACL/Turtle parsing and serialization (required)
- **pyshacl** (>=0.20) -- SHACL validation against generated shapes (optional)
- **PyShEx** (>=0.8) -- ShEx validation against generated schemas (optional)
- **pytest** (dev) -- test runner

## Wikidata Label-Aware ShEx Generation

When generating ShEx for Wikidata-based schemas, shape references and comments
use human-readable English labels instead of raw QIDs/PIDs.  The feature is
**disabled by default** (no network calls are made) and only applies to ShEx
output directions (`shacl2shex`, `json2shex`).

### CLI

```bash
shaclex-py --input Q1172284.ttl --direction shacl2shex --wikidata-labels
```

With `--wikidata-labels` the output matches the WES ShEx format:

```shex
<DataSet> EXTRA wdt:P31 {
  # WikibaseItem property
  wdt:P31   [ wd:Q1172284 ] ;            # instance of
  wdt:P50   @<Author> * ;                # author
  wdt:P126  @<MaintainedBy> ? ;          # maintained by
  wdt:P407  @<LanguageOfWorkOrName> * ;  # language of work or name

  # URL, String, Quantity, Time property
  wdt:P577  xsd:dateTime ? ;             # publication date
}

<Author> EXTRA wdt:P31 {
  wdt:P31 [ wd:Q482980 ]  # author
}
```

Key behaviours:
- `@<ShapeName>` uses the English label of the class, never `@<Q5>`.
- Single-class auxiliaries use the **class** label (`@<Human>` for Q5).
- Multi-class OR auxiliaries use the **property** label.
- Multiple properties targeting the same class share one auxiliary shape.
- Section headers separate WikibaseItem from literal/IRI properties.
- Auxiliary shapes get `# qid_label, qid_label` comments.

### Python API

```python
from shaclex_py.utils.wikidata import collect_iris_from_shacl, fetch_labels
from shaclex_py import parse_shacl_file, convert_shacl_to_shex, serialize_shex

shacl     = parse_shacl_file("Q1172284.ttl")
label_map = fetch_labels(collect_iris_from_shacl(shacl))  # one SPARQL round-trip

shex   = convert_shacl_to_shex(shacl, label_map=label_map)
output = serialize_shex(shex,          label_map=label_map)
```

Pass `label_map=None` (default) for plain output without any network calls.

## pySHACL Compatibility

SHACL output produced by shaclex-py is compatible with
[pySHACL](https://github.com/RDFLib/pySHACL).

```python
import pyshacl
from shaclex_py import parse_shacl_file, serialize_shacl

# Load and re-serialize any SHACL shape
schema = parse_shacl_file("shapes.ttl")
shapes_turtle = serialize_shacl(schema)

# Use directly as the shapes graph in pyshacl
conforms, report_graph, report_text = pyshacl.validate(
    data_graph="data.ttl",
    data_graph_format="turtle",
    shacl_graph=shapes_turtle,
    shacl_graph_format="turtle",
)
print(report_text)
```

**OR-class constraint encoding**: The SHACL specification requires
`sh:or` at the property shape level for disjunctive class constraints.
shaclex-py serializes these as:

```turtle
sh:property [
    sh:path schema:founder ;
    sh:or ([ sh:class schema:Organization ] [ sh:class schema:Person ]) ;
] ;
```

The parser accepts both this standard form and the custom YAGO form
(`sh:class [ sh:or (...) ]`) for backward compatibility with the
`dataset/shacl_yago/` reference files.

## PyShEx Compatibility

ShExC output produced by shaclex-py is compatible with
[PyShEx](https://github.com/hsolbrig/PyShEx).

```python
from pyshex.shex_evaluator import ShExEvaluator
from shaclex_py import parse_shacl_file, convert_shacl_to_shex, serialize_shex

schema = parse_shacl_file("shapes.ttl")
shex = convert_shacl_to_shex(schema)
shexc = serialize_shex(shex)

evaluator = ShExEvaluator(
    rdf="data.ttl",
    schema=shexc,
    rdf_format="turtle",
)
results = evaluator.evaluate(
    focus="http://example.org/myNode",
    start="http://example.org/MyShape",  # or use the shape IRI
)
for r in results:
    print(r.focus, "conforms:", r.result)
```

**Shape name IRIs**: shaclex-py serializes shape names as relative IRIs
(e.g. `<Person>`). When using PyShEx, resolve these against your chosen
base URI or provide fully-qualified IRIs in the `start` parameter.

## Usage

### CLI

```bash
# SHACL -> ShEx (output to stdout)
shaclex-py --input shapes.ttl --direction shacl2shex

# ShEx -> SHACL (output to file)
shaclex-py --input shapes.shex --direction shex2shacl --output shapes.ttl

# Convert a directory of files
shaclex-py --input-dir my_shacl/ --output-dir my_shex/ --direction shacl2shex

# Run the full YAGO dataset in both directions
shaclex-py --batch
```

Also available via `python -m shaclex_py` or the legacy `python main.py`.

### Python API

```python
from shaclex_py import (
    parse_shacl_file, convert_shacl_to_shex, serialize_shex,
)

shacl = parse_shacl_file("shapes.ttl")
shex = convert_shacl_to_shex(shacl)
print(serialize_shex(shex))
```

```python
from shaclex_py import (
    parse_shex_file, convert_shex_to_shacl, serialize_shacl,
)

shex = parse_shex_file("shapes.shex")
shacl = convert_shex_to_shacl(shex)
print(serialize_shacl(shacl))
```

## Mapping Rules

The sections below cover every pattern the converter handles, grouped by topic. For each pattern, the SHACL source, the canonical JSON representation, and the ShEx output are shown.

### Shape container and target class

**SHACL**
```turtle
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:targetClass schema:Person .
```

**Canonical JSON**
```json
{ "name": "Person", "targetClass": "http://schema.org/Person", "closed": false, "properties": [] }
```

**ShEx**
```shex
<Person> EXTRA rdf:type {
  rdf:type [ schema:Person ]
}
```

The shape IRI suffix `Shape` is stripped to produce the short name (`PersonShape` → `Person`).  `sh:targetClass` becomes an `rdf:type [C]` triple constraint inside the ShEx body.

---

### Datatype constraint (`sh:datatype`)

**SHACL**
```turtle
sh:property [
    sh:path schema:birthDate ;
    sh:datatype xsd:date ;
    sh:maxCount 1 ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://schema.org/birthDate", "datatype": "http://www.w3.org/2001/XMLSchema#date", "cardinality": {"min": 0, "max": 1} }
```

**ShEx**
```shex
schema:birthDate xsd:date ?
```

---

### Class reference (`sh:class`)

A single class reference becomes an auxiliary shape and a `@<ShapeName>` reference.

**SHACL**
```turtle
sh:property [
    sh:path schema:founder ;
    sh:class schema:Person ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://schema.org/founder", "classRef": "http://schema.org/Person", "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
schema:founder @<Person> *

<Person> EXTRA rdf:type {
  rdf:type [ schema:Person ]
}
```

---

### OR class constraint — property level (`sh:or` with `sh:class`)

Two supported surface forms are parsed identically; both round-trip as the standard pySHACL form.

**SHACL (standard form — pySHACL compatible)**
```turtle
sh:property [
    sh:path schema:founder ;
    sh:or ( [ sh:class schema:Organization ] [ sh:class schema:Person ] ) ;
] ;
```

**SHACL (custom YAGO form — also accepted by the parser)**
```turtle
sh:property [
    sh:path schema:founder ;
    sh:class [ sh:or ( schema:Organization schema:Person ) ] ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://schema.org/founder", "classRefOr": ["http://schema.org/Organization","http://schema.org/Person"], "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
schema:founder @<Founder> *

<Founder> EXTRA rdf:type {
  rdf:type [ schema:Organization schema:Person ]
}
```

The auxiliary shape name is derived from the property label (Wikidata mode) or the property IRI local name.

---

### Node kind (`sh:nodeKind`)

**SHACL**
```turtle
sh:property [
    sh:path schema:url ;
    sh:nodeKind sh:IRI ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://schema.org/url", "nodeKind": "IRI", "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
schema:url IRI *
```

Supported node kinds: `sh:IRI`, `sh:BlankNode`, `sh:Literal`, `sh:BlankNodeOrIRI`, `sh:BlankNodeOrLiteral`, `sh:IRIOrLiteral`.

---

### Cardinality (`sh:minCount` / `sh:maxCount`)

| SHACL | ShEx shorthand | Notes |
|---|---|---|
| _(none)_ | `*` | SHACL default `{0,*}` |
| `sh:minCount 0 ; sh:maxCount 1` | `?` | Optional single |
| `sh:minCount 1` | `+` | At least one |
| `sh:minCount 1 ; sh:maxCount 1` | _(no suffix)_ | Exactly one (ShEx default) |
| `sh:minCount 2 ; sh:maxCount 5` | `{2,5}` | Explicit range |

The converter always emits explicit cardinality to avoid ambiguity between the different language defaults (SHACL `{0,*}` vs ShEx `{1,1}`).

---

### Single-value constraint (`sh:hasValue`)

**SHACL**
```turtle
sh:property [
    sh:path rdf:type ;
    sh:hasValue schema:Person ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "hasValue": "http://schema.org/Person", "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
rdf:type [ schema:Person ] *
```

---

### Enumerated values (`sh:in`)

**SHACL**
```turtle
sh:property [
    sh:path schema:gender ;
    sh:in ( schema:Male schema:Female ) ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://schema.org/gender", "inValues": ["http://schema.org/Female","http://schema.org/Male"], "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
schema:gender [ schema:Male schema:Female ] *
```

---

### IRI stem pattern (`sh:pattern` matching a URL prefix)

Patterns of the form `^http://...` are converted to a ShEx IRI stem.

**SHACL**
```turtle
sh:property [
    sh:path schema:sameAs ;
    sh:pattern "^http://www.wikidata.org/entity/" ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://schema.org/sameAs", "iriStem": "http://www.wikidata.org/entity", "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
schema:sameAs [ <http://www.wikidata.org/entity>~ ] *
```

Arbitrary regex patterns that do not match a URL prefix are kept as `pattern` in the canonical JSON and have no ShEx equivalent.

---

### Shape reference (`sh:node`)

`sh:node` links a property to a separately declared NodeShape.

**SHACL**
```turtle
sh:property [
    sh:path dbo:cost ;
    sh:node shapes:costValueShape ;
] ;
```

**Canonical JSON**
```json
{ "path": "http://dbpedia.org/ontology/cost", "nodeRef": "http://shaclshapes.org/costValueShape", "cardinality": {"min": 0, "max": -1} }
```

**ShEx**
```shex
dbo:cost @<costValue> *
```

The referenced shape is emitted separately (see *Named value shapes* below for the case where the target is a datatype-OR shape).

---

### Named value shapes — `sh:or` with datatype alternatives at NodeShape level

DBpedia uses reusable "value type" shapes that declare which datatypes a literal value may have. The `sh:or` sits directly on the `sh:NodeShape`, not on a property.

**SHACL**
```turtle
shapes:costValueShape a sh:NodeShape ;
    sh:or (
        [ sh:datatype dbt:usDollar ]
        [ sh:datatype dbt:euro ]
        [ sh:datatype dbt:poundSterling ]
    ) .

# Used by the main shape via sh:node:
sh:property [
    sh:path dbo:cost ;
    sh:node shapes:costValueShape ;
] ;
```

**Canonical JSON**
```json
{
  "name": "costValue",
  "datatypeOr": [
    "http://dbpedia.org/datatype/euro",
    "http://dbpedia.org/datatype/poundSterling",
    "http://dbpedia.org/datatype/usDollar"
  ],
  "closed": false,
  "properties": []
}
```

**ShEx**
```shex
<costValue> dbt:usDollar OR dbt:euro OR dbt:poundSterling
```

The datatype list is sorted alphabetically in the canonical JSON. The ShEx uses the valid `NodeConstraint OR NodeConstraint` syntax (ShEx 2.0 `ShapeOr`).

---

### Property alternative groups — `sh:or` with `sh:property` items at NodeShape level

Some DBpedia shapes use `sh:or` to declare that a node must satisfy one of several property groups (e.g., two alternative paths for the same measurement). Each alternative is a blank node containing `sh:property` blocks.

**SHACL**
```turtle
sh:or (
    [
        sh:property [
            sh:path dbo:height ;
            sh:datatype dbt:centimetre ;
            sh:maxCount 1 ;
        ]
    ]
    [
        sh:property [
            sh:path <http://dbpedia.org/ontology/Person/height> ;
            sh:datatype dbt:centimetre ;
            sh:maxCount 1 ;
        ]
    ]
) ;
```

**Canonical JSON** (union of all branches)
```json
[
  { "path": "http://dbpedia.org/ontology/height",        "datatype": "http://dbpedia.org/datatype/centimetre", "cardinality": {"min": 0, "max": 1} },
  { "path": "http://dbpedia.org/ontology/Person/height", "datatype": "http://dbpedia.org/datatype/centimetre", "cardinality": {"min": 0, "max": 1} }
]
```

**ShEx**
```shex
dbo:height        dbt:centimetre ? ;
dbo:Person/height dbt:centimetre ?
```

The translator flattens all alternatives into the parent shape's property list (union / over-approximation). All constraint information is preserved; the strict "exactly one branch" disjunction is relaxed to "any combination allowed".

---

### Semantic Differences

Some constructs do not have exact equivalents:

- **Default cardinality**: ShEx defaults to `{1,1}`, SHACL defaults to `{0,*}`. The converter always emits explicit cardinality to avoid ambiguity.
- **`sh:pattern`**: Only patterns matching IRI prefixes (`^http://...`) are converted to ShEx IRI stems. Arbitrary regex patterns have no ShEx equivalent.
- **`rdf:type` handling**: SHACL uses `sh:targetClass` for class targeting, while ShEx uses `rdf:type [Class]` inside the shape body. During ShEx-to-SHACL conversion, the `rdf:type` constraint is promoted to `sh:targetClass`.
- **Auxiliary shapes**: When SHACL uses `sh:class` or `sh:or` with classes, the ShEx output generates auxiliary shapes (e.g., `<Place> EXTRA rdf:type { rdf:type [schema:Place] }`) to represent class constraints as shape references.
- **`sh:or` property alternatives**: The `sh:or ([ sh:property ... ] [ sh:property ... ])` pattern at NodeShape level is flattened into the property list. The strict disjunction semantics are approximated by a union of all branches.
- **Named value shapes**: `sh:or ([sh:datatype D1] [sh:datatype D2] ...)` at NodeShape level is preserved faithfully in the canonical JSON (`datatypeOr`) and serialized as `<Name> D1 OR D2 OR ...` in ShEx.

## Testing

```bash
pytest tests/ -v
```

The test suite includes:
- **Parser tests**: Verify all 37 YAGO files parse correctly in both formats
- **Converter tests**: Structural comparison against reference files
- **Roundtrip tests**: SHACL -> ShEx -> SHACL and ShEx -> SHACL -> ShEx for all 37 files
- **Canonical JSON tests**: Exact-match comparison ensuring SHACL and ShEx produce identical canonical output

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
