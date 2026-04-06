# Mapping Rules

This document covers every pattern the converter handles. For each pattern the SHACL source and ShEx output are shown. ShexJE is the internal canonical format used during conversion.

Based on [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html).

---

## Shape container and target class

**SHACL**
```turtle
<http://shaclshapes.org/PersonShape> a sh:NodeShape ;
    sh:targetClass schema:Person .
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

**ShexJE**
```json
{
  "type": "TripleConstraint",
  "predicate": "http://schema.org/founder",
  "valueExpr": "Person",
  "min": 0, "max": -1
}
```

with companion value shape appended to the schema's `shapes` array:
```json
{
  "type": "Shape",
  "id": "Person",
  "extra": ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"],
  "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
  "values": ["http://schema.org/Person"]
}
```

**ShEx**
```shex
schema:founder @<Person> *

<Person> EXTRA rdf:type {
  rdf:type [ schema:Person ]
}
```

Multiple properties pointing to the same class share one companion value shape.

---

## OR class constraint — property level (`sh:or` with `sh:class`)

Two surface forms are parsed identically; both round-trip as the standard pySHACL-compatible form.

**SHACL (standard form)**
```turtle
sh:property [
    sh:path schema:founder ;
    sh:or ( [ sh:class schema:Organization ] [ sh:class schema:Person ] ) ;
] ;
```

**SHACL (legacy form — also accepted)**
```turtle
sh:property [
    sh:path schema:founder ;
    sh:class [ sh:or ( schema:Organization schema:Person ) ] ;
] ;
```

> **Note:** The legacy `sh:class [ sh:or (...) ]` form is not standard SHACL. Earlier versions of the YAGO dataset used this form; the current dataset uses only the standard form. The parser accepts both for backwards compatibility.

**ShexJE**
```json
{
  "type": "TripleConstraint",
  "predicate": "http://schema.org/founder",
  "valueExpr": "OrganizationOrPerson",
  "min": 0, "max": -1
}
```

with companion value shape:
```json
{
  "type": "Shape",
  "id": "OrganizationOrPerson",
  "extra": ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"],
  "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
  "values": [
    "http://schema.org/Organization",
    "http://schema.org/Person"
  ]
}
```

**ShEx**
```shex
schema:founder @<Founder> *

<Founder> EXTRA rdf:type {
  rdf:type [ schema:Organization schema:Person ]
}
```

The companion shape ID is derived from the local names of the class IRIs joined with `"Or"`.
Multiple properties pointing to the same combination share one companion shape.

---

## Node kind (`sh:nodeKind`)

**SHACL**
```turtle
sh:property [
    sh:path schema:url ;
    sh:nodeKind sh:IRI ;
] ;
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

**ShEx**
```shex
schema:sameAs [ <http://www.wikidata.org/entity>~ ] *
```

Arbitrary regex patterns that do not match a URL prefix are kept as a `pattern` field internally and serialised as a `.  /regex/` pattern facet in ShExC.

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

**ShEx**
```shex
dbo:wikiPageRedirects xsd:anyURI /^http:\/\/dbpedia.org\/resource\// *
```

The `/regex/` pattern facet in ShExC combines the datatype and the regex in a single constraint expression. Forward slashes inside the regex are escaped as `\/`. The parser and serializer both handle this encoding transparently.

---

## Non-standard `sh:dataType` (capital T) — shexer compatibility

Shexer-generated files use `sh:dataType` (capital T), which is not standard SHACL but occurs in real-world datasets.  The parser accepts both spellings and normalises them to the same canonical `datatype` field.

**SHACL (shexer form — accepted)**
```turtle
sh:property [
    sh:path dbo:populationTotal ;
    sh:dataType xsd:integer ;
] ;
```

---

## Reusable value shapes — node-level constraints

A `sh:NodeShape` may carry constraints **directly** (without `sh:property`) to act as a reusable value shape referenced elsewhere via `sh:node`.  Three patterns are supported:

### Node-level datatype + nodeKind (`LangStringShape` pattern)

**SHACL**
```turtle
shapes:LangStringShape a sh:NodeShape ;
    sh:nodeKind sh:Literal ;
    sh:datatype rdf:langString .

sh:property [ sh:path dbo:abstract ; sh:node shapes:LangStringShape ; sh:minCount 1 ] ;
```

**ShEx**
```shex
<LangString> rdf:langString
```

**ShexJE**
```json
{ "type": "NodeConstraint", "id": "LangString", "nodeKind": "Literal", "datatype": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString" }
```

The `nodeKind` is preserved in ShexJE. In ShExC only the datatype is serialized (the `Literal` nodeKind is implicit for any datatype constraint).

### Node-level value set (`TimeZoneShape` pattern)

**SHACL**
```turtle
shapes:TimeZoneShape a sh:NodeShape ;
    sh:in ( dbr:Eastern_Time_Zone dbr:Indian_Standard_Time dbr:Central_Time_Zone ) .

sh:property [ sh:path dbo:timeZone ; sh:node shapes:TimeZoneShape ] ;
```

**ShEx**
```shex
<TimeZone> [ dbr:Eastern_Time_Zone dbr:Indian_Standard_Time dbr:Central_Time_Zone ]
```

**ShExJE**
```json
{ "type": "NodeConstraint", "id": "TimeZone", "values": ["http://dbpedia.org/resource/Eastern_Time_Zone", ...] }
```

### Node-level nodeKind only

**SHACL**
```turtle
shapes:IRIShape a sh:NodeShape ;
    sh:nodeKind sh:IRI .
```

**ShEx**
```shex
<IRIShape> IRI
```

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

**ShEx**
```shex
<costValue> dbt:usDollar OR dbt:euro OR dbt:poundSterling
```

The **declaration order** of the datatype list is preserved (not sorted). The ShEx uses valid `NodeConstraint OR NodeConstraint` syntax (ShEx 2.0 `ShapeOr`).

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

**ShexJE**
```json
{
  "type": "EachOf",
  "expressions": [
    { "type": "TripleConstraint", "predicate": "http://dbpedia.org/ontology/height",
      "valueExpr": { "type": "NodeConstraint", "datatype": "dbt:centimetre" }, "max": 1 },
    { "type": "TripleConstraint", "predicate": "http://dbpedia.org/ontology/Person/height",
      "valueExpr": { "type": "NodeConstraint", "datatype": "dbt:centimetre" }, "max": 1 }
  ],
  "alternativeGroups": [
    [
      "http://dbpedia.org/ontology/height",
      "http://dbpedia.org/ontology/Person/height"
    ]
  ]
}
```

The `alternativeGroups` annotation records which predicates are mutually exclusive. All property paths and constraint values are fully preserved. Round-tripping through SHACL reconstructs the original `sh:or` blocks. See the ShexJE spec §4.2.1 for the full definition.

**ShEx** (when the chain includes a ShEx step — `alternativeGroups` is not expressible in ShExC)
```shex
dbo:height        dbt:centimetre ? ;
dbo:Person/height dbt:centimetre ?
```

When the ShEx step is included, the grouping annotation is preserved in the ShexJE intermediates but lost in the ShExC text. The strict "exactly one branch" disjunction semantics cannot be expressed in ShEx. See [Translation Coverage — approximated translations](translation-coverage.md#approximated-translations) for the full analysis.

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

## Alternative path (`sh:alternativePath`)

`sh:alternativePath` expresses that any one of multiple predicates may satisfy the property constraint.

**SHACL**
```turtle
sh:property [
    sh:path [ sh:alternativePath ( dbo:foundingDate dbo:formationDate dbo:openingDate ) ] ;
    sh:datatype xsd:date ;
    sh:minCount 1 ;
] ;
```

**ShEx**
```shex
(
  dbo:foundingDate xsd:date {1,} |
  dbo:formationDate xsd:date {1,} |
  dbo:openingDate xsd:date {1,}
)
```

ShexJE stores the primary path (first alternative) in `predicate` and the full ordered list in `pathAlternatives`. In ShEx the constraint becomes a `OneOf` expression (using `|`) with one `TripleConstraint` per alternative path, wrapped in parentheses when embedded inside a larger `EachOf`. This is a slight over-approximation: ShEx `|` requires at least one branch to match, while SHACL `sh:alternativePath` means the constraint applies to whichever path(s) have triples. See [Translation Coverage — approximated translations](translation-coverage.md#approximated-translations) for the full analysis.

---

## Semantic differences summary

| Difference | Details |
|---|---|
| Default cardinality | ShEx defaults to `{1,1}`; SHACL defaults to `{0,*}`. Always emitted explicitly to avoid ambiguity. |
| `rdf:type` vs `sh:targetClass` | SHACL uses `sh:targetClass`; ShEx uses `rdf:type [C]` inside the shape body. Promoted/demoted on conversion. |
| Auxiliary shapes | `sh:class` and `sh:or` with classes produce auto-generated auxiliary shapes in ShEx. |
| `sh:pattern` (standalone arbitrary regex) | Preserved as `pattern` in ShexJE; emitted as `. /regex/` pattern facet in ShExC. |
| `sh:datatype` + `sh:pattern` combined | Both fields carried through ShexJE; emitted as `dtype /regex/` pattern facet in ShExC. |
| `sh:or` property alternatives | Preserved via `alternativeGroups` on `EachOf` in ShexJE. Grouping is lost only when the chain passes through ShExC (no ShEx equivalent). |
| `sh:alternativePath` | Translated to ShEx `OneOf` (`\|`); semantics slightly differ (ShEx requires at least one branch to match; SHACL applies constraint to any present path). |
