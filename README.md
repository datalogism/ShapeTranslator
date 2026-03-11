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

Some DBpedia shapes use `sh:or` directly on the `sh:NodeShape` to declare that a conforming node must satisfy **one of several mutually exclusive property groups**. This typically models measurement paths that exist under two different predicates depending on the DBpedia version or language variant (e.g., `dbo:height` vs `dbo:Person/height`).

**SHACL source**
```turtle
<http://shaclshapes.org/ArtistShape> a sh:NodeShape ;
    sh:targetClass dbo:Artist ;

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
    ...
```

**What it means**: a valid `dbo:Artist` node must either have `dbo:height` with a centimetre value *or* `dbo:Person/height` with a centimetre value — not both, not neither.

#### How the translator handles it — union flattening

The translator collects all properties from all branches and adds them to the parent shape's property list as independent optional properties. The branches are not kept as a group.

**Canonical JSON output**
```json
[
  { "path": "http://dbpedia.org/ontology/height",
    "datatype": "http://dbpedia.org/datatype/centimetre",
    "cardinality": {"min": 0, "max": 1} },
  { "path": "http://dbpedia.org/ontology/Person/height",
    "datatype": "http://dbpedia.org/datatype/centimetre",
    "cardinality": {"min": 0, "max": 1} }
]
```

**ShEx output**
```shex
dbo:height        dbt:centimetre ? ;
dbo:Person/height dbt:centimetre ?
```

#### What is preserved vs what is lost

| Aspect | Preserved? |
|---|---|
| All property paths | Yes — every path from every branch appears in the output |
| All constraint values (datatype, cardinality, …) | Yes — verified 100% in cycle tests |
| Disjunction semantics ("exactly one branch") | **No** — relaxed to "any combination allowed" |
| Information that two paths were alternatives | **No** — the grouping is lost |

#### Why this is an intentional trade-off

SHACL's `sh:or` with `sh:property` groups is a *shape-level disjunction* — a concept that has no direct equivalent in either ShEx or the canonical JSON model. The possible approaches and their consequences are:

| Approach | Consequence |
|---|---|
| **Union flattening** *(current)* | All properties and their constraints are retained; validation becomes more permissive (false negatives are impossible, false positives may appear) |
| Drop all alternatives | Clean output, but all properties from `sh:or` branches are silently lost |
| Emit a `OneOf` expression in ShEx | Requires a new model concept; the canonical JSON has no `oneOf` field; roundtrip back to SHACL becomes ambiguous |

The union approach is chosen because **no constraint data is discarded**. A validator running against the translated output will accept any node that the original SHACL would accept, plus some nodes that have both alternatives at once. For the DBpedia shapes where this pattern occurs (measurement paths), the practical difference is negligible.

> **Cycle test result**: All 1 082 DBpedia properties — including those coming from `sh:or` alternative groups — are preserved with 100% fidelity through the SHACL→JSON→ShEx→JSON cycle. The loss is semantic (disjunction grouping), not structural (no data is dropped).

---

### Semantic Differences

Some constructs do not have exact equivalents:

- **Default cardinality**: ShEx defaults to `{1,1}`, SHACL defaults to `{0,*}`. The converter always emits explicit cardinality to avoid ambiguity.
- **`sh:pattern`**: Only patterns matching IRI prefixes (`^http://...`) are converted to ShEx IRI stems. Arbitrary regex patterns have no ShEx equivalent.
- **`rdf:type` handling**: SHACL uses `sh:targetClass` for class targeting, while ShEx uses `rdf:type [Class]` inside the shape body. During ShEx-to-SHACL conversion, the `rdf:type` constraint is promoted to `sh:targetClass`.
- **Auxiliary shapes**: When SHACL uses `sh:class` or `sh:or` with classes, the ShEx output generates auxiliary shapes (e.g., `<Place> EXTRA rdf:type { rdf:type [schema:Place] }`) to represent class constraints as shape references.
- **`sh:or` property alternatives**: The `sh:or ([ sh:property ... ] [ sh:property ... ])` pattern at NodeShape level is flattened into the parent shape's property list (union). All property paths and their constraints are retained, but the "exactly one branch" disjunction semantics are lost — see the *Property alternative groups* section above for a full analysis of the trade-off.
- **Named value shapes**: `sh:or ([sh:datatype D1] [sh:datatype D2] ...)` at NodeShape level is preserved faithfully in the canonical JSON (`datatypeOr`) and serialized as `<Name> D1 OR D2 OR ...` in ShEx.

## Translation Coverage and Known Limitations

This section documents which constructs from [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html) are fully translated, which are approximated, and which are currently out of scope. For each gap the development effort required to close it is described.

### Fully supported translations

The following patterns survive the SHACL→JSON→ShEx→JSON and ShEx→JSON→ShEx→JSON cycles with **zero data loss** (verified across 147 files, 4 309 properties — see Roundtrip Cycle Evaluation).

| Construct | SHACL side | ShEx side | Book §|
|---|---|---|---|
| Shape container | `sh:NodeShape` | `<Name> { ... }` | 7.1 |
| Target class | `sh:targetClass C` | `rdf:type [C]` | 7.1 |
| Direct property path | `sh:property [ sh:path P ]` | `P ...` | 7.1 |
| Datatype | `sh:datatype D` | `D` (NodeConstraint) | 7.1 |
| Single class reference | `sh:class C` | `@<Aux>` + auxiliary shape | 7.1 |
| OR of classes (property level) | `sh:or ([sh:class C1] [sh:class C2])` | `@<Aux>` + OR value set | 7.1 |
| Node kind | `sh:nodeKind sh:IRI / sh:Literal / …` | `IRI / LITERAL / BNODE / NONLITERAL` | 7.1 |
| Cardinality | `sh:minCount m ; sh:maxCount n` | `{m,n}`, `?`, `*`, `+` | 7.8 |
| Single value | `sh:hasValue V` | `[V]` | 7.1 |
| Enumeration | `sh:in (v1 v2)` | `[v1 v2]` | 7.1 |
| IRI stem (URL prefix pattern) | `sh:pattern "^http://..."` | `[<http://...>~]` | 7.15 |
| Named shape reference | `sh:node S` | `@<S>` | 7.1 |
| Named value shapes (OR of datatypes) | `sh:NodeShape` with `sh:or ([sh:datatype D1]...)` | `<Name> D1 OR D2 OR ...` | 7.15 |
| Closed shapes | `sh:closed true` | `CLOSED` | 7.14 |
| Default cardinality mismatch | explicit `{0,*}` vs `{1,1}` | always emitted explicitly | 7.8 |

### Approximated translations (data preserved, semantics relaxed)

#### `sh:or` with `sh:property` alternative groups at NodeShape level

The DBpedia pattern where `sh:or` appears on a `sh:NodeShape` with full `sh:property` blocks as alternatives (modelling two equivalent measurement paths) is **flattened into a union**. Every property path and its constraints are preserved, but the "exactly one branch must hold" exclusivity is not expressible in either ShEx or the canonical JSON model. See the *Property alternative groups* section in Mapping Rules for a full analysis.

#### `sh:pattern` — arbitrary regular expressions

`sh:pattern` values that match a URL prefix (`^http://...`) are converted to a ShEx `IriStem`. Arbitrary regex patterns (e.g., `"^[A-Z]{2}[0-9]{6}$"`) have no ShEx equivalent and are carried through the canonical model as a `pattern` string. On conversion to ShEx they are emitted as `NodeConstraint(pattern=...)` which ShEx validators may or may not support.

---

### Known gaps — constructs silently dropped today

The following constructs are **not yet parsed or emitted** by the translator. When present in input they are silently ignored and do not appear in the output, with no warning to the user. Each entry describes the book's treatment, the reason for the gap, and what would be required to close it.

---

#### 1. SPARQL property paths (§7.9)

**What SHACL allows:**
```turtle
sh:property [ sh:path [ sh:zeroOrMorePath schema:knows ] ]
sh:property [ sh:path ( schema:child schema:child ) ]       # sequence path
sh:property [ sh:path [ sh:alternativePath ( schema:name foaf:name ) ] ]
sh:property [ sh:path [ sh:inversePath schema:parent ] ]
```

**ShEx equivalent:** None for the path algebra. ShEx supports only direct predicates and inverse predicates (`^pred`).

**Current behaviour:** The entire `sh:property` block is silently dropped if the path is not a plain IRI.

**To fix:**
- Detect complex paths in the SHACL parser and carry them as an opaque `pathExpr` field.
- Map `sh:inversePath` → ShEx inverse constraint (`^pred`).
- Map `sh:alternativePath` → multiple independent properties (over-approximation, same strategy as property-group flattening).
- For `sh:zeroOrMorePath` and sequence paths, emit a warning comment in ShEx; no loss-free translation exists per the book.

---

#### 2. Recursion — ShEx→SHACL direction (§7.10)

**What ShEx allows:**
```shex
:UserShape IRI {
  schema:knows @:UserShape *
}
```

**SHACL:** The specification explicitly leaves recursive `sh:node` **undefined**. Most SHACL validators either loop or reject it.

**Current behaviour:** The translator emits recursive `sh:node` literally in the SHACL output. The result is formally undefined and may break validators. The reverse direction (SHACL→ShEx) works correctly because ShEx was designed with recursion.

**To fix:** In the ShEx→SHACL converter, detect self-referencing `ShapeRef`s and replace them with an approximation. The book suggests two workarounds: `sh:targetSubjectsOf` (loses type constraint) or `sh:zeroOrMorePath` (loses shape identity). No translation preserves full recursive semantics in SHACL.

---

#### 3. Qualified value shapes (§7.12)

**What SHACL allows** (the correct way to put two constraints on the same predicate):
```turtle
sh:property [
    sh:path schema:parent ;
    sh:qualifiedValueShape [ sh:property [ sh:path :isMale ; sh:hasValue true ] ] ;
    sh:qualifiedMinCount 1 ; sh:qualifiedMaxCount 1 ;
] ;
sh:property [
    sh:path schema:parent ;
    sh:qualifiedValueShape [ sh:property [ sh:path :isFemale ; sh:hasValue true ] ] ;
    sh:qualifiedMinCount 1 ; sh:qualifiedMaxCount 1 ;
] .
```

**ShEx equivalent:** Multiple triple constraints on the same predicate with different node constraints — natively supported.

**Current behaviour:** `sh:qualifiedValueShape`, `sh:qualifiedMinCount`, and `sh:qualifiedMaxCount` are not parsed. The constraints are silently dropped.

**To fix:** Add `qualified_constraints` to `PropertyShape` and `CanonicalProperty`. Parse the three SHACL fields. In the ShEx serializer, emit one `TripleConstraint` per qualified block on the same predicate. In the SHACL serializer, emit `sh:qualifiedValueShape` blocks. This is the correct translation direction per the book.

---

#### 4. Logical operators: `sh:and`, `sh:not`, `sh:xone` (§7.13)

**What SHACL allows:**
```turtle
sh:and ( :ShapeA :ShapeB )      # conjunction — both must pass
sh:not :ShapeC                  # negation
sh:xone ( :ShapeA :ShapeB )     # exclusive OR — exactly one must pass
```

**ShEx equivalents:** `AND`, `NOT`, `|`. However, `sh:xone` and ShEx `|` have **different semantics**: `sh:xone` requires that the other branches do not even partially match; ShEx `|` requires only that at least one branch fully matches. The book calls this out explicitly.

**Current behaviour:** All three are silently dropped when parsing SHACL. Not emitted when converting from ShEx.

**To fix:**
- Add `and_constraints`, `not_constraint`, `xone_constraints` to `PropertyShape` and `NodeShape`.
- In the SHACL parser, read `sh:and`, `sh:not`, `sh:xone`.
- In the canonical model, add `andOf`, `notOf`, `xoneOf` fields to `CanonicalShape`/`CanonicalProperty`.
- In ShEx output: map `sh:and` → `ShapeAnd` / `AND`, `sh:not` → `ShapeNot` / `NOT`, `sh:xone` → `|` with an inline comment flagging the semantic difference.
- In the ShEx parser, read `AND`, `NOT`, `|` (already partially supported via `OneOf`).

---

#### 5. Property pair constraints (§7.11)

**What SHACL allows:**
```turtle
sh:property [
    sh:path schema:birthDate ;
    sh:lessThan :loginDate ;       # birthDate < loginDate
] ;
sh:property [
    sh:path foaf:firstName ;
    sh:equals schema:givenName ;   # firstName = givenName
] ;
sh:property [
    sh:path schema:givenName ;
    sh:disjoint schema:lastName ;  # no value shared between the two
] .
```

**ShEx equivalent:** None. The book states explicitly: "ShEx 2.0 does not have the concept of property pair constraints." These are SHACL-only.

**Current behaviour:** `sh:lessThan`, `sh:equals`, and `sh:disjoint` are silently dropped.

**To fix:** Parse them in the SHACL parser and carry as opaque annotations in the canonical model. In SHACL→SHACL roundtrips they should be preserved. In SHACL→ShEx, emit a `# WARNING: sh:lessThan/equals/disjoint cannot be expressed in ShEx` comment on the relevant triple constraint. No loss-free ShEx translation exists.

---

#### 6. Numeric and string facets (§7.8)

**What both languages support:**

SHACL: `sh:minInclusive`, `sh:maxInclusive`, `sh:minExclusive`, `sh:maxExclusive`, `sh:minLength`, `sh:maxLength`, `sh:languageIn`, `sh:uniqueLang`

ShEx: `MININCLUSIVE`, `MAXINCLUSIVE`, `MINEXCLUSIVE`, `MAXEXCLUSIVE`, `MINLENGTH`, `MAXLENGTH` on `NodeConstraint`

**Current behaviour:** None of these facets are parsed or emitted. They are silently dropped on both sides even though ShEx and SHACL map to each other directly for the numeric and length facets. (`sh:languageIn` and `sh:uniqueLang` have no ShEx equivalent and would need warning comments.)

**To fix:** This is the most mechanical of all gaps. Add facet fields to `PropertyShape`, `NodeConstraint`, and `CanonicalProperty`. Wire through all parsers, converters, and serializers. The SHACL↔ShEx mapping is 1-to-1 for the six numeric/length facets.

---

#### 7. Non-class target declarations (§7.4)

**What SHACL allows beyond `sh:targetClass`:**
```turtle
sh:targetNode ex:Alice              # targets a specific named node
sh:targetObjectsOf schema:knows     # targets all objects of this predicate
sh:targetSubjectsOf schema:knows    # targets all subjects of this predicate
```

**ShEx equivalent:** None inline — ShEx uses external shape maps for node–shape association.

**Current behaviour:** Only `sh:targetClass` is parsed. The other three target types are silently ignored.

**To fix:** Parse them and carry as annotations in the canonical model. In SHACL roundtrips preserve them. In ShEx output, emit a `# NOTE: target scope cannot be expressed inline in ShEx` comment.

---

### Gap priority summary

| Gap | Impact | Effort | Loss-free translation possible? |
|---|---|---|---|
| Numeric/string facets | High — dropped in many real schemas | Low — mechanical field additions | Yes (6 of 8 facets) |
| `sh:and` / `sh:not` | Medium | Medium — new model fields + serializers | Yes (`AND`/`NOT`) |
| `sh:xone` | Medium | Medium | No — semantic mismatch with ShEx `\|` |
| Qualified value shapes | Medium — DBpedia, enterprise shapes | Medium | Yes |
| Property pair constraints | Low in KG schemas, high in enterprise | Low — opaque carry-through | No (ShEx has no equivalent) |
| Complex property paths | High in DBpedia/enterprise | High — path algebra in both models | Partial (`sh:inversePath` only) |
| Recursion (ShEx→SHACL) | Low — rare in practice | Medium | No — SHACL recursion is undefined |
| Non-class target types | Low — rare in dataset schemas | Low — opaque carry-through | Partial |

## Testing

```bash
pytest tests/ -v
```

The test suite includes:
- **Parser tests**: Verify all 37 YAGO files parse correctly in both formats
- **Converter tests**: Structural comparison against reference files
- **Roundtrip tests**: SHACL -> ShEx -> SHACL and ShEx -> SHACL -> ShEx for all 37 files
- **Canonical JSON tests**: Exact-match comparison ensuring SHACL and ShEx produce identical canonical output

## Roundtrip Cycle Evaluation

Every dataset was put through a full information-preserving cycle and measured for fidelity:

- **SHACL → JSON → ShEx → JSON** (DBpedia, YAGO SHACL source)
- **ShEx → JSON → ShEx → JSON** (YAGO ShEx source, WES Wikidata Entity Shapes)

The cycle verifies that no information is silently dropped: the canonical JSON produced at the start of the cycle must exactly match the canonical JSON produced at the end.

### What is verified

The comparison is **deep**: it checks the **actual value** of every field, not just whether the field type is present. For every shape and every property the following are compared exactly:

- `targetClass` IRI
- `closed` flag
- `cardinality` (`min` and `max` integers)
- Constraint field **type** and **value** (`datatype` IRI, `classRef` IRI, `classRefOr` sorted list, `nodeKind` string, `hasValue` value, `inValues` sorted list, `iriStem` string, `pattern` regex string, `nodeRef` IRI, `datatypeOr` sorted list)

### Results — per pattern, per dataset

#### YAGO SHACL → JSON → ShEx → JSON (37 files)

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

#### DBpedia SHACL → JSON → ShEx → JSON (20 files)

| Pattern | Occurrences | Preserved |
|---|---|---|
| `targetClass` | 32 | 32/32 (100%) |
| `closed` flag | 32 | 32/32 (100%) |
| `cardinality` | 1 082 | 1 082/1 082 (100%) |
| `sh:datatype` | 612 | 612/612 (100%) |
| `sh:class` (single) | 420 | 420/420 (100%) |
| `sh:node` ref (`nodeRef`) | 12 | 12/12 (100%) |
| `sh:or` datatypes at NodeShape (`datatypeOr`) | 12 | 12/12 (100%) |

#### YAGO ShEx → JSON → ShEx → JSON (37 files)

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

#### WES Wikidata ShEx → JSON → ShEx → JSON (53 files)

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

### Grand total — 147 files, zero differences

| Metric | Grand total |
|---|---|
| Files completing cycle | **147/147 (100%)** |
| Shapes preserved | **159/159 (100%)** |
| Properties preserved | **4 309/4 309 (100%)** |
| Constraint type + value preserved | **4 269/4 269 (100%)** |
| Cardinality preserved | **4 309/4 309 (100%)** |
| `datatypeOr` shape lists preserved | **12/12 (100%)** |

> **Known approximation — `sh:or` property alternatives**: All 1 082 DBpedia properties are structurally preserved (100% in the cycle test). However, the `sh:or ([ sh:property ... ] [ sh:property ... ])` pattern at NodeShape level loses its *disjunction grouping*: the branches are flattened into a union of independent optional properties. No constraint data is dropped, but the "exactly one branch must hold" semantics cannot be expressed in the canonical model or ShEx. See the *Property alternative groups* section in Mapping Rules for a full explanation and comparison of alternatives.

## Evaluation Against YAGO Ground Truth

The translator was evaluated against 37 paired SHACL/ShEx files from the [YAGO knowledge graph](https://yago-knowledge.org/):

| Direction | Predicate Match | Shape Name Match |
|---|---|---|
| SHACL -> ShEx | 99.9% (706/707) | 94.7% (195/206) |
| ShEx -> SHACL | 99.3% (669/674) | -- |

The small gaps are due to the semantic differences described above (primarily `rdf:type` / `sh:targetClass` handling and auxiliary shape naming).

## Dataset

The `dataset/` directory contains:

| Directory | Format | Files | Source |
|---|---|---|---|
| `dataset/shacl_yago/` | SHACL (Turtle) | 37 | YAGO knowledge graph |
| `dataset/shex_yago/` | ShEx (ShExC) | 37 | YAGO knowledge graph |
| `dataset/shex_wes/` | ShEx (ShExC) | 53 | Wikidata Entity Shapes (WES) |
| `dataset/shacl_dbpedia/` | SHACL (Turtle) | 20 | DBpedia ontology shapes |

The YAGO files cover a range of complexity from simple shapes (Gender, Language) to complex ones with class references, OR constraints, and IRI stems (Person, Politician, Event). The WES files use Wikidata Q-codes as filenames and test the Wikidata label-aware ShEx generation feature. The DBpedia files introduced new patterns (named value shapes with datatype alternatives, property alternative groups) that are now fully supported.
