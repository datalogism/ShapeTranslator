# Mapping Rules

This document covers every pattern the converter handles. For each pattern the SHACL source, canonical JSON representation, and ShEx output are shown.

Based on [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html).

---

## Shape container and target class

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

The shape IRI suffix `Shape` is stripped to produce the short name (`PersonShape` → `Person`). `sh:targetClass` becomes an `rdf:type [C]` triple constraint inside the ShEx body. In the reverse direction (ShEx→SHACL), the `rdf:type [C]` constraint is promoted back to `sh:targetClass`.

---

## Datatype constraint (`sh:datatype`)

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

## Class reference (`sh:class`)

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

Multiple properties pointing to the same class share one auxiliary shape (e.g., `@<Human>` for all properties whose range is `wd:Q5`).

---

## OR class constraint — property level (`sh:or` with `sh:class`)

Two surface forms are parsed identically; both round-trip as the standard pySHACL-compatible form.

**SHACL (standard — recommended)**
```turtle
sh:property [
    sh:path schema:founder ;
    sh:or ( [ sh:class schema:Organization ] [ sh:class schema:Person ] ) ;
] ;
```

**SHACL (custom YAGO form — also accepted)**
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

## Node kind (`sh:nodeKind`)

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

## Cardinality (`sh:minCount` / `sh:maxCount`)

| SHACL | ShEx shorthand | Notes |
|---|---|---|
| _(none)_ | `*` | SHACL default `{0,*}` |
| `sh:minCount 0 ; sh:maxCount 1` | `?` | Optional single |
| `sh:minCount 1` | `+` | At least one |
| `sh:minCount 1 ; sh:maxCount 1` | _(no suffix)_ | Exactly one (ShEx default) |
| `sh:minCount 2 ; sh:maxCount 5` | `{2,5}` | Explicit range |

The converter always emits explicit cardinality to avoid ambiguity between the different language defaults (SHACL `{0,*}` vs ShEx `{1,1}`).

---

## Single-value constraint (`sh:hasValue`)

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

## Enumerated values (`sh:in`)

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

## IRI stem pattern (`sh:pattern` as the sole constraint, matching a URL prefix)

When `sh:pattern` is the only constraint on a property and its value matches `^http://...`, it is converted to a ShEx IRI stem.

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

Arbitrary regex patterns that do not match a URL prefix are kept as `pattern` in the canonical JSON and serialised as a `.  /regex/` pattern facet in ShExC.

---

## Combined datatype + pattern constraint (`sh:datatype` + `sh:pattern`)

When both `sh:datatype` and `sh:pattern` appear on the same property shape, both constraints are preserved throughout the full pipeline. The `pattern` field is **additive** — it accompanies the primary `datatype` constraint rather than replacing it.

**SHACL**
```turtle
sh:property [
    sh:path dbo:wikiPageRedirects ;
    sh:datatype xsd:anyURI ;
    sh:pattern "^http://dbpedia.org/resource/" ;
] ;
```

**Canonical JSON**
```json
{
  "path": "http://dbpedia.org/ontology/wikiPageRedirects",
  "datatype": "http://www.w3.org/2001/XMLSchema#anyURI",
  "pattern": "^http://dbpedia.org/resource/",
  "cardinality": {"min": 0, "max": -1}
}
```

**ShEx**
```shex
dbo:wikiPageRedirects xsd:anyURI /^http:\/\/dbpedia.org\/resource\// *
```

The `/regex/` pattern facet in ShExC combines the datatype and the regex in a single constraint expression. Forward slashes inside the regex are escaped as `\/`. The parser and serializer both handle this encoding transparently.

---

## Named shape reference (`sh:node`)

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

---

## Named value shapes — `sh:or` with datatype alternatives at NodeShape level

DBpedia uses reusable "value type" shapes that declare which datatypes a literal value may have via `sh:or` directly on a `sh:NodeShape`.

**SHACL**
```turtle
shapes:costValueShape a sh:NodeShape ;
    sh:or (
        [ sh:datatype dbt:usDollar ]
        [ sh:datatype dbt:euro ]
        [ sh:datatype dbt:poundSterling ]
    ) .

sh:property [
    sh:path dbo:cost ;
    sh:node shapes:costValueShape ;
] ;
```

**Canonical JSON**
```json
{
  "name": "costValue",
  "datatypeOr": ["http://dbpedia.org/datatype/euro", "http://dbpedia.org/datatype/poundSterling", "http://dbpedia.org/datatype/usDollar"],
  "closed": false,
  "properties": []
}
```

**ShEx**
```shex
<costValue> dbt:usDollar OR dbt:euro OR dbt:poundSterling
```

The **declaration order** of the datatype list is preserved in the canonical JSON (not sorted). The ShEx uses valid `NodeConstraint OR NodeConstraint` syntax (ShEx 2.0 `ShapeOr`).

---

## Property alternative groups — `sh:or` with `sh:property` items at NodeShape level

Some DBpedia shapes use `sh:or` on a `sh:NodeShape` to declare mutually exclusive property groups (e.g., two alternative measurement paths).

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

The translator flattens all alternatives into the parent shape's property list (union / over-approximation). All property paths and constraint values are preserved; the strict "exactly one branch" disjunction semantics are relaxed to "any combination allowed". See [Translation Coverage — approximated translations](translation-coverage.md#approximated-translations) for the full analysis.

---

## Closed shapes

**SHACL**
```turtle
:UserShape a sh:NodeShape ;
    sh:closed true ;
    sh:property [ sh:path schema:name ; sh:datatype xsd:string ] .
```

**ShEx**
```shex
<User> EXTRA rdf:type CLOSED {
  schema:name xsd:string
}
```

> **Note**: `sh:closed` in SHACL only considers top-level `sh:property` entries — properties declared inside nested `sh:and` or `sh:or` blocks are invisible to the closed check. ShEx's `CLOSED` applies uniformly. This difference is documented in [Validating RDF Data §7.14](https://book.validatingrdf.com/bookHtml013.html).

---

## Semantic differences summary

| Difference | Details |
|---|---|
| Default cardinality | ShEx defaults to `{1,1}`; SHACL defaults to `{0,*}`. Always emitted explicitly to avoid ambiguity. |
| `rdf:type` vs `sh:targetClass` | SHACL uses `sh:targetClass`; ShEx uses `rdf:type [C]` inside the shape body. Promoted/demoted on conversion. |
| Auxiliary shapes | `sh:class` and `sh:or` with classes produce auto-generated auxiliary shapes in ShEx. |
| `sh:pattern` (standalone arbitrary regex) | Preserved as `pattern` in canonical JSON; emitted as `. /regex/` pattern facet in ShExC. |
| `sh:datatype` + `sh:pattern` combined | Both fields carried through canonical JSON; emitted as `dtype /regex/` pattern facet in ShExC. |
| `sh:or` property alternatives | Flattened to union; disjunction grouping is lost. |
