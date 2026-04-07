# ShexJE — ShEx JSON Extended Specification

**Version**: 2.0
**Status**: Draft
**Supersedes**: ShexJE 1.0 (prior internal format with JSON shorthand fields on TripleConstraint)

---

## 1. Overview

**ShexJE** (ShEx JSON Extended) is a JSON format that serves as the canonical
interchange language for this library.  It is designed around three goals:

1. **ShexJ backward-compatibility** — every valid
   [ShexJ](https://shex.io/shex-semantics/index.html#shexj) document is a
   valid ShexJE document.
2. **SHACL-completeness** — every SHACL construct (targets, severity,
   qualified value shapes, property paths, SPARQL constraints, …) can be
   expressed in ShexJE.
3. **ShexJ-first extension model** — ShexJE only adds SHACL-specific features
   on top of ShexJ.  All property constraints use the standard ShexJ
   ``valueExpr`` field; there are no non-ShexJ shorthands on
   ``TripleConstraint``.

ShexJE uses the same `"type"` discriminator pattern as ShexJ and produces
deterministic, human-readable JSON.

### 1.1 Changes from ShexJE 1.0

ShexJE 2.0 removes the following non-ShexJ shorthand fields that were
previously allowed on `TripleConstraint`:

| Removed field | Replacement |
|---|---|
| `classRef: "IRI"` | `valueExpr: "ShapeId"` (see §3.1.1) |
| `classRefOr: ["IRI", …]` | `valueExpr: "ShapeId"` with multiple `values` |
| `iriStem: "IRI"` | `valueExpr: {type:"NodeConstraint", values:[{type:"IriStem", stem:"IRI"}]}` |
| `hasValue: V` on TC | `valueExpr: {type:"NodeConstraint", values:[V]}` |
| `in: […]` on TC | `valueExpr: {type:"NodeConstraint", values:[…]}` |

The parser silently upgrades legacy documents that still carry these fields.
New documents **must** use the `valueExpr` forms.

A new **value-shape shorthand** was added to `Shape` (§3.1.1) for the common
pattern of constraining the type of a linked node.

---

## 2. Document structure

```json
{
  "@context": "http://www.w3.org/ns/shexje.jsonld",
  "type": "Schema",
  "prefixes": {
    "schema": "http://schema.org/",
    "xsd":    "http://www.w3.org/2001/XMLSchema#"
  },
  "base":      "http://example.org/",
  "start":     "PersonShape",
  "startActs": [],
  "imports":   [],
  "shapes":    [ ... ]
}
```

| Field       | Type              | ShexJ? | Description                                  |
|-------------|-------------------|--------|----------------------------------------------|
| `@context`  | string            | ✓      | ShexJE JSON-LD context IRI                   |
| `type`      | `"Schema"`        | ✓      | Fixed discriminator                          |
| `prefixes`  | object            | ✓      | Prefix → IRI namespace map                   |
| `base`      | IRI string        | ✓      | Base IRI for relative resolution             |
| `start`     | IRI string        | ✓      | IRI of start shape                           |
| `startActs` | SemAct[]          | ✓      | Semantic actions                             |
| `imports`   | IRI[]             | ✓      | Imported schema IRIs                         |
| `shapes`    | ShapeDecl[]       | ✓      | Shape declarations (see §3)                  |

---

## 3. Shape declarations

The `shapes` array holds **shape declarations**, each identified by an `"id"`
field.  IDs may be compact IRIs (`"ex:PersonShape"`) or full IRIs.

### 3.1 Shape (`type: "Shape"`)

Extends ShexJ `Shape`.  All ShexJ fields are preserved verbatim.

```json
{
  "type": "Shape",
  "id":   "PersonShape",

  "closed":    false,
  "extra":     ["rdf:type"],
  "extends":   ["BaseShape"],
  "restricts": [],
  "expression": { ... },
  "semActs":    [],
  "annotations": [],

  "targetClass":      "schema:Person",
  "targetNode":       ["ex:alice"],
  "targetSubjectsOf": ["schema:name"],
  "targetObjectsOf":  ["schema:knows"],

  "severity":    "sh:Violation",
  "message":     "Must be a valid person",
  "deactivated": false,

  "and":  [ ... ],
  "or":   [ ... ],
  "not":  { ... },
  "xone": [ ... ],

  "sparql": [ { "type": "SparqlConstraint", "select": "..." } ]
}
```

#### ShexJE extensions

| Field              | Type                  | SHACL equivalent           | Notes                              |
|--------------------|-----------------------|----------------------------|------------------------------------|
| `targetClass`      | IRI or IRI[]          | `sh:targetClass`           | Can be scalar or array             |
| `targetNode`       | IRI[]                 | `sh:targetNode`            |                                    |
| `targetSubjectsOf` | IRI[]                 | `sh:targetSubjectsOf`      |                                    |
| `targetObjectsOf`  | IRI[]                 | `sh:targetObjectsOf`       |                                    |
| `severity`         | IRI string            | `sh:severity`              | `sh:Violation`, `sh:Warning`, `sh:Info` |
| `message`          | string or string[]    | `sh:message`               | Plain string or lang-tagged list   |
| `deactivated`      | boolean               | `sh:deactivated`           |                                    |
| `and`              | ShapeExpression[]     | `sh:and`                   | All must match                     |
| `or`               | ShapeExpression[]     | `sh:or`                    | At least one must match            |
| `not`              | ShapeExpression       | `sh:not`                   | Must not match                     |
| `xone`             | ShapeExpression[]     | `sh:xone`                  | Exactly one must match             |
| `sparql`           | SparqlConstraint[]    | `sh:sparql`                | See §3.6                           |
| `predicate`        | IRI string            | (value-shape shorthand)    | See §3.1.1                         |
| `values`           | (IRI or literal)[]    | (value-shape shorthand)    | See §3.1.1                         |

#### 3.1.1 Value-shape shorthand

When a `Shape` is used exclusively to constrain the type of a linked node
(i.e. it encodes a `sh:class` constraint), the full `expression` form:

```json
{
  "type": "Shape",
  "id":   "Country",
  "extra": ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"],
  "expression": {
    "type": "TripleConstraint",
    "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
    "valueExpr": {
      "type": "NodeConstraint",
      "values": ["http://dbpedia.org/ontology/Country"]
    }
  }
}
```

can be written more compactly using the `predicate` + `values` shorthand:

```json
{
  "type":      "Shape",
  "id":        "Country",
  "extra":     ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"],
  "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
  "values":    ["http://dbpedia.org/ontology/Country"]
}
```

For OR-of-classes (formerly `classRefOr`), list all class IRIs in `values`:

```json
{
  "type":      "Shape",
  "id":        "AcademicSubjectOrMedicalSpecialty",
  "extra":     ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"],
  "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
  "values":    [
    "http://dbpedia.org/ontology/AcademicSubject",
    "http://dbpedia.org/ontology/MedicalSpecialty"
  ]
}
```

These value shapes are referenced from `TripleConstraint.valueExpr` using a
plain string (the shape `id`):

```json
{
  "type":      "TripleConstraint",
  "predicate": "http://dbpedia.org/ontology/academicDiscipline",
  "valueExpr": "AcademicSubjectOrMedicalSpecialty"
}
```

The `predicate` and `values` fields are mutually exclusive with `expression`.
The `extra` array should list the type predicate so the shape does not
*require* the triple (open-world assumption).

### 3.2 NodeConstraint (`type: "NodeConstraint"`)

Extends ShexJ `NodeConstraint`.

```json
{
  "type":          "NodeConstraint",
  "id":            "DateOrStringNC",

  "nodeKind":      "iri",
  "datatype":      "xsd:date",
  "values":        [ "ex:val1", {"type": "IriStem", "stem": "http://ex.org/"} ],
  "pattern":       "^[0-9]{4}",
  "flags":         "i",
  "minLength":     1,
  "maxLength":     100,
  "minInclusive":  0,
  "maxInclusive":  100,
  "minExclusive":  0,
  "maxExclusive":  100,
  "totalDigits":   10,
  "fractionDigits": 2,

  "hasValue":      "ex:specificValue",
  "in":            ["active", "inactive"],
  "languageIn":    ["en", "fr"],
  "uniqueLang":    false
}
```

#### ShexJE extensions

| Field        | Type                | SHACL equivalent  | Notes                                       |
|--------------|---------------------|-------------------|---------------------------------------------|
| `hasValue`   | IRI or literal dict | `sh:hasValue`     | Shorthand: value must equal this            |
| `in`         | (IRI or literal)[]  | `sh:in`           | Shorthand: value must be one of these       |
| `languageIn` | string[]            | `sh:languageIn`   | Language tags                               |
| `uniqueLang` | boolean             | `sh:uniqueLang`   | Each language tag at most once              |

### 3.3 ShapeOr / ShapeAnd / ShapeNot (`type: "ShapeOr"` / `"ShapeAnd"` / `"ShapeNot"`)

Mirrors ShexJ constructs; adds `severity`, `message`, `deactivated`.

```json
{ "type": "ShapeOr",  "id": "...", "shapeExprs": [ ... ], "severity": "sh:Warning" }
{ "type": "ShapeAnd", "id": "...", "shapeExprs": [ ... ] }
{ "type": "ShapeNot", "id": "...", "shapeExpr":  { ... } }
```

### 3.4 ShapeXone (`type: "ShapeXone"`) — *new in ShexJE*

Exclusive OR: exactly one of the listed shape expressions must match.
Maps to SHACL `sh:xone`.

```json
{
  "type": "ShapeXone",
  "id":   "ExclusiveTypeShape",
  "shapeExprs": [
    { "type": "NodeConstraint", "datatype": "xsd:date" },
    { "type": "NodeConstraint", "datatype": "xsd:dateTime" }
  ],
  "severity": "sh:Violation"
}
```

---

## 4. Triple expressions

### 4.1 TripleConstraint (`type: "TripleConstraint"`)

Extends ShexJ `TripleConstraint`.

```json
{
  "type":      "TripleConstraint",
  "predicate": "schema:birthDate",
  "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:date" },
  "inverse":   false,
  "min":       0,
  "max":       1,
  "semActs":   [],
  "annotations": [],

  "path": { "type": "InversePath", "expression": "schema:knows" },

  "severity":    "sh:Warning",
  "message":     "Expected a valid birth date",
  "deactivated": false,

  "equals":           "schema:sameAs",
  "disjoint":         "schema:alternateName",
  "lessThan":         "schema:endDate",
  "lessThanOrEquals": "schema:endDate",

  "qualifiedValueShape":          { "type": "ShapeRef", "reference": "PersonShape" },
  "qualifiedMinCount":            1,
  "qualifiedMaxCount":            3,
  "qualifiedValueShapesDisjoint": false,

  "uniqueLang": false
}
```

#### ShexJE extensions

| Field                            | Type               | SHACL equivalent                        |
|----------------------------------|--------------------|-----------------------------------------|
| `path`                           | PropertyPath       | sh:path (complex paths) — see §5        |
| `severity`                       | IRI string         | `sh:severity` (overrides shape-level)   |
| `message`                        | string or string[] | `sh:message`                            |
| `deactivated`                    | boolean            | `sh:deactivated`                        |
| `equals`                         | IRI string         | `sh:equals`                             |
| `disjoint`                       | IRI string         | `sh:disjoint`                           |
| `lessThan`                       | IRI string         | `sh:lessThan`                           |
| `lessThanOrEquals`               | IRI string         | `sh:lessThanOrEquals`                   |
| `qualifiedValueShape`            | ShapeExpression    | `sh:qualifiedValueShape`                |
| `qualifiedMinCount`              | integer            | `sh:qualifiedMinCount`                  |
| `qualifiedMaxCount`              | integer            | `sh:qualifiedMaxCount`                  |
| `qualifiedValueShapesDisjoint`   | boolean            | `sh:qualifiedValueShapesDisjoint`       |
| `uniqueLang`                     | boolean            | `sh:uniqueLang`                         |

#### Class / type constraints via valueExpr

All type/class constraints are expressed using the standard ShexJ `valueExpr`
field:

| Pattern                  | `valueExpr`                                                         |
|--------------------------|---------------------------------------------------------------------|
| Single class             | `"ShapeId"` (string — see §3.1.1)                                   |
| OR of classes            | `"ShapeId"` (string, shape has multiple `values`)                   |
| IRI stem                 | `{type:"NodeConstraint", values:[{type:"IriStem", stem:"…"}]}`      |
| hasValue (single)        | `{type:"NodeConstraint", values:["ex:value"]}`                      |
| Enumeration              | `{type:"NodeConstraint", values:["ex:v1","ex:v2"]}`                 |
| Named shape reference    | `"ShapeId"` or `{type:"ShapeRef", reference:"ShapeId"}`             |

> **Deprecated**: `classRef`, `classRefOr`, `iriStem`, `hasValue`, `in`
> directly on `TripleConstraint` were removed in ShexJE 2.0.  The parser
> still accepts them for backward compatibility and automatically converts
> them to `valueExpr` forms.

### 4.2 EachOf / OneOf

Mostly unchanged from ShexJ (`"type": "EachOf"` / `"type": "OneOf"`), with one ShexJE extension on `EachOf`:

```json
{ "type": "EachOf", "expressions": [ ... ], "min": 1, "max": 1 }
{ "type": "OneOf",  "expressions": [ ... ] }
```

#### 4.2.1 `alternativeGroups` (new in ShexJE 2.1)

`EachOf` may carry an optional `"alternativeGroups"` field — an array of arrays of predicate IRI strings.  Each inner array names a group of predicates that are **mutually exclusive alternatives** in the source schema (originating from a SHACL `sh:or` with `sh:property` blocks at `NodeShape` level).

The predicates named in `alternativeGroups` are still expressed as regular `TripleConstraint` entries inside `"expressions"` with their full constraints.  The `alternativeGroups` field is a **pure annotation** added for round-trip fidelity; it does not change the ShexJE validation semantics.

```json
{
  "type": "EachOf",
  "expressions": [
    {
      "type": "TripleConstraint",
      "predicate": "http://dbpedia.org/ontology/timeInSpace",
      "valueExpr": { "type": "NodeConstraint", "nodeKind": "Literal" },
      "min": 1, "max": -1
    },
    {
      "type": "TripleConstraint",
      "predicate": "http://dbpedia.org/ontology/Astronaut/timeInSpace",
      "valueExpr": { "type": "NodeConstraint", "nodeKind": "Literal" },
      "min": 1, "max": -1
    }
  ],
  "alternativeGroups": [
    [
      "http://dbpedia.org/ontology/timeInSpace",
      "http://dbpedia.org/ontology/Astronaut/timeInSpace"
    ]
  ]
}
```

When converting back to SHACL, each predicate in an `alternativeGroups` entry becomes its own `sh:or` branch:

```turtle
sh:or (
  [ sh:property [ sh:path dbo:timeInSpace ;        sh:nodeKind sh:Literal ; sh:minCount 1 ] ]
  [ sh:property [ sh:path dbo:Astronaut/timeInSpace ; sh:nodeKind sh:Literal ; sh:minCount 1 ] ]
) ;
```

This is distinct from `sh:alternativePath` (same constraint on multiple predicates), which is represented via `AlternativePath` on `TripleConstraint.path` — see §5.

### 4.3 Cardinality

Same as ShexJ: `"min"` and `"max"` integers on `TripleConstraint`, `EachOf`,
`OneOf`.  `"max": -1` denotes unbounded (`*`).  Absent `min` defaults to `1`
(ShexJ convention); absent `max` defaults to `1`.

---

## 5. Property paths (new in ShexJE)

When a `TripleConstraint` requires a non-simple property path (SHACL SPARQL
paths), the `"path"` field replaces `"predicate"`:

| Type               | SHACL                         | SPARQL    |
|--------------------|-------------------------------|-----------|
| `InversePath`      | `sh:inversePath`              | `^p`      |
| `SequencePath`     | (sequence)                    | `p1/p2`   |
| `AlternativePath`  | `sh:alternativePath`          | `p1\|p2`  |
| `ZeroOrMorePath`   | `sh:zeroOrMorePath`           | `p*`      |
| `OneOrMorePath`    | `sh:oneOrMorePath`            | `p+`      |
| `ZeroOrOnePath`    | `sh:zeroOrOnePath`            | `p?`      |

```json
{ "type": "InversePath",    "expression":  "schema:knows"               }
{ "type": "SequencePath",   "expressions": ["schema:a", "schema:b"]     }
{ "type": "AlternativePath","expressions": ["schema:name", "foaf:name"] }
{ "type": "ZeroOrMorePath", "expression":  "schema:knows"               }
{ "type": "OneOrMorePath",  "expression":  "schema:member"              }
{ "type": "ZeroOrOnePath",  "expression":  "schema:address"             }
```

Paths may be nested:

```json
{
  "type": "SequencePath",
  "expressions": [
    "schema:knows",
    { "type": "ZeroOrMorePath", "expression": "schema:follows" }
  ]
}
```

---

## 6. SPARQL constraints (new in ShexJE)

```json
{
  "type":     "SparqlConstraint",
  "prefixes": { "schema": "http://schema.org/" },
  "select":   "SELECT $this WHERE { $this schema:name ?n FILTER(!REGEX(?n,'^[A-Z]')) }",
  "message":  "Name must start with an uppercase letter",
  "severity": "sh:Violation"
}
```

`SparqlConstraint` objects appear in the `"sparql"` array on a `ShapeE`.

---

## 7. Value-set entries

Value sets (used in `NodeConstraintE.values` and `NodeConstraintE.in`) follow
ShexJ conventions, extended with SHACL language stems:

| Form                                               | Meaning                  |
|----------------------------------------------------|--------------------------|
| `"http://example.org/foo"` (plain string)          | IRI value                |
| `{"value": "hello", "type": "xsd:string"}`         | Typed literal            |
| `{"value": "bonjour", "language": "fr"}`           | Language-tagged literal  |
| `{"type": "IriStem", "stem": "http://ex.org/"}`    | IRI stem                 |
| `{"type": "IriStemRange", "stem": "…", …}`         | IRI stem range           |
| `{"type": "LiteralStem", "stem": "prefix"}`        | Literal stem             |
| `{"type": "Language", "languageTag": "en"}`        | Language tag             |
| `{"type": "LanguageStem", "stem": "en"}`           | Language stem            |

---

## 8. Internal canonical model → ShexJE mapping

The internal canonical representation used during conversion maps to ShexJE as follows:

| Internal canonical field      | ShexJE equivalent                                                     |
|-------------------------------|-----------------------------------------------------------------------|
| `shapes[].name`               | `shapes[].id`                                                         |
| `shapes[].targetClass`        | `shapes[].targetClass`                                                |
| `shapes[].closed`             | `shapes[].closed`                                                     |
| `shapes[].datatypeOr`         | `ShapeOrE` with `NodeConstraintE(datatype=…)` items                   |
| `properties[].path`           | `TripleConstraintE.predicate`                                         |
| `properties[].datatype`       | `valueExpr: {type:"NodeConstraint", datatype:…}`                      |
| `properties[].classRef`       | `valueExpr: "ShapeId"` + companion `ShapeE(predicate, values)`        |
| `properties[].classRefOr`     | `valueExpr: "ShapeId"` + companion `ShapeE(predicate, values:[…])`    |
| `properties[].nodeKind`       | `valueExpr: {type:"NodeConstraint", nodeKind:…}`                      |
| `properties[].hasValue`       | `valueExpr: {type:"NodeConstraint", values:[value]}`                  |
| `properties[].inValues`       | `valueExpr: {type:"NodeConstraint", values:[…]}`                      |
| `properties[].iriStem`        | `valueExpr: {type:"NodeConstraint", values:[{type:"IriStem",stem:…}]}`|
| `properties[].nodeRef`        | `valueExpr: "ShapeId"` (string reference)                             |
| `properties[].pattern`        | added to `NodeConstraintE.pattern`                                    |
| `properties[].cardinality`    | `TripleConstraintE.min` / `TripleConstraintE.max`                     |

---

## 9. ShexJ → ShexJE mapping

All ShexJ constructs are valid ShexJE as-is.  ShexJE adds optional fields that
are transparent to ShexJ-only consumers.  The following ShexJ types map
one-to-one:

| ShexJ type       | ShexJE type      | Changes                                     |
|------------------|------------------|---------------------------------------------|
| `Schema`         | `Schema`         | `prefixes` is now an object (was also object in ShexJ) |
| `Shape`          | `ShapeE`         | New optional SHACL fields                   |
| `NodeConstraint` | `NodeConstraintE`| New `hasValue`, `in`, `languageIn`, `uniqueLang` |
| `ShapeOr`        | `ShapeOrE`       | New `severity`, `message`, `deactivated`    |
| `ShapeAnd`       | `ShapeAndE`      | Same                                        |
| `ShapeNot`       | `ShapeNotE`      | Same                                        |
| `TripleConstraint` | `TripleConstraintE` | New SHACL fields + shorthands           |
| `EachOf`         | `EachOfE`        | Unchanged                                   |
| `OneOf`          | `OneOfE`         | Unchanged                                   |

New in ShexJE only: `ShapeXoneE`, `SparqlConstraintE`, `InversePath`,
`SequencePath`, `AlternativePath`, `ZeroOrMorePath`, `OneOrMorePath`,
`ZeroOrOnePath`.

---

## 10. SHACL → ShexJE mapping

| SHACL construct                            | ShexJE equivalent                                       |
|--------------------------------------------|---------------------------------------------------------|
| `sh:NodeShape`                             | `ShapeE`                                                |
| `sh:targetClass C`                         | `ShapeE.targetClass`                                    |
| `sh:targetNode n`                          | `ShapeE.targetNode`                                     |
| `sh:targetSubjectsOf p`                    | `ShapeE.targetSubjectsOf`                               |
| `sh:targetObjectsOf p`                     | `ShapeE.targetObjectsOf`                                |
| `sh:closed true`                           | `ShapeE.closed: true`                                   |
| `sh:property [ sh:path p … ]`              | `TripleConstraintE(predicate=p, …)`                     |
| `sh:datatype D`                            | `valueExpr: NodeConstraintE(datatype=D)`                |
| `sh:nodeKind sh:IRI`                       | `valueExpr: NodeConstraintE(nodeKind="iri")`            |
| `sh:class C`                               | `valueExpr: "ShapeId"` + `ShapeE(predicate, values:[C])` |
| `sh:or ([sh:class C1][sh:class C2])`       | `valueExpr: "ShapeId"` + `ShapeE(predicate, values:[C1,C2])` |
| `sh:pattern "regex"`                       | `valueExpr: NodeConstraintE(pattern="regex")`           |
| `sh:hasValue V`                            | `hasValue: V` shorthand                                 |
| `sh:in (v1 v2)`                            | `in: [v1, v2]` shorthand                                |
| `sh:minCount m; sh:maxCount n`             | `min: m, max: n`                                        |
| `sh:severity sh:Warning`                   | `severity: "sh:Warning"`                                |
| `sh:message "text"`                        | `message: "text"`                                       |
| `sh:deactivated true`                      | `deactivated: true`                                     |
| `sh:and ([S1][S2])`                        | `ShapeE.and: [S1, S2]` or `ShapeAndE`                   |
| `sh:or ([S1][S2])` (shapes)                | `ShapeE.or: [S1, S2]` or `ShapeOrE`                     |
| `sh:not S`                                 | `ShapeE.not: S` or `ShapeNotE`                          |
| `sh:xone ([S1][S2])`                       | `ShapeE.xone: [S1, S2]` or `ShapeXoneE`                 |
| `sh:qualifiedValueShape S; sh:qualifiedMinCount m` | `qualifiedValueShape + qualifiedMinCount`     |
| `sh:equals p`                              | `equals: p`                                             |
| `sh:disjoint p`                            | `disjoint: p`                                           |
| `sh:lessThan p`                            | `lessThan: p`                                           |
| `sh:inversePath p`                         | `path: {type:"InversePath", expression:p}`              |
| `sh:zeroOrMorePath p`                      | `path: {type:"ZeroOrMorePath", expression:p}`           |
| `sh:sparql [ sh:select "…" ]`              | `ShapeE.sparql: [{type:"SparqlConstraint", select:"…"}]`|
| `sh:languageIn ("en" "fr")`                | `NodeConstraintE.languageIn: ["en","fr"]`               |
| `sh:uniqueLang true`                       | `uniqueLang: true`                                      |
| `sh:node S`                                | `valueExpr: "S"` (string) or `{type:"ShapeRef", reference:S}` |
| Top-level `sh:or ([sh:datatype D1]…)`      | `ShapeOrE` with `NodeConstraintE(datatype=…)` items     |

---

## 11. Full example

```json
{
  "@context": "http://www.w3.org/ns/shexje.jsonld",
  "type": "Schema",
  "prefixes": {
    "schema": "http://schema.org/",
    "xsd":    "http://www.w3.org/2001/XMLSchema#",
    "rdf":    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "ex":     "http://example.org/"
  },
  "shapes": [
    {
      "type":        "Shape",
      "id":          "PersonShape",
      "targetClass": "schema:Person",
      "closed":      false,
      "expression": {
        "type": "EachOf",
        "expressions": [
          {
            "type":      "TripleConstraint",
            "predicate": "schema:name",
            "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:string" },
            "min": 1, "max": 1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:birthDate",
            "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:date" },
            "min": 0, "max": 1,
            "severity":  "sh:Warning"
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:knows",
            "valueExpr": "PersonShape",
            "min": 0, "max": -1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:alumniOf",
            "valueExpr": "CollegeOrUniversityOrHighSchool",
            "min": 0, "max": -1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:url",
            "valueExpr": {
              "type": "NodeConstraint",
              "values": [{ "type": "IriStem", "stem": "https://" }]
            },
            "min": 0, "max": -1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:gender",
            "valueExpr": {
              "type": "NodeConstraint",
              "values": ["ex:Male", "ex:Female", "ex:NonBinary"]
            },
            "min": 0, "max": 1
          }
        ]
      },
      "sparql": [
        {
          "type":     "SparqlConstraint",
          "prefixes": { "schema": "http://schema.org/" },
          "select":   "SELECT $this WHERE { $this schema:birthDate ?d FILTER(?d > '2100-01-01'^^xsd:date) }",
          "message":  "Birth date must not be in the future",
          "severity": "sh:Violation"
        }
      ]
    },
    {
      "type": "Shape",
      "id":   "CollegeOrUniversityOrHighSchool",
      "extra": ["rdf:type"],
      "predicate": "rdf:type",
      "values": [
        "http://schema.org/CollegeOrUniversity",
        "http://schema.org/HighSchool"
      ]
    },
    {
      "type": "ShapeOr",
      "id":   "DateOrDateTimeShape",
      "shapeExprs": [
        { "type": "NodeConstraint", "datatype": "xsd:date" },
        { "type": "NodeConstraint", "datatype": "xsd:dateTime" }
      ]
    }
  ]
}
```

---

## 12. Implementation notes

### Conversion pipeline

```
SHACL (Turtle)          ShExC               ShexJE JSON
      ↓                   ↓                      ↓
 parse_shacl()       parse_shex()          parse_shexje()
      ↓                   ↓                      ↓
  SHACLSchema         ShExSchema            ShexJESchema
      ↓                   ↓               ↙       ↓
 convert_shacl_to_shexje()  convert_shex_to_shexje()
              ↓                              ↓
         ShexJESchema ←───────────────── ShexJESchema
              ↓                    (canonical format)
 convert_shexje_to_shacl/shex()
      ↓              ↓
 serialize_shacl()  serialize_shex()       serialize_shexje()
      ↓                   ↓                      ↓
 SHACL (Turtle)       ShExC               ShexJE JSON
```

### Feature support matrix

| Feature                        | ShexJE | SHACL | ShExC |
|--------------------------------|:------:|:-----:|:-----:|
| Shape + properties             | ✓      | ✓     | ✓     |
| `targetClass`                  | ✓      | ✓     | ✓*    |
| Closed shapes                  | ✓      | ✓     | ✓     |
| Datatype constraint            | ✓      | ✓     | ✓     |
| Class reference (`sh:class`)   | ✓      | ✓     | ✓     |
| OR of classes                  | ✓      | ✓     | ✓     |
| NodeKind constraint            | ✓      | ✓     | ✓     |
| IRI stem                       | ✓      | ✓*    | ✓     |
| Cardinality                    | ✓      | ✓     | ✓     |
| hasValue / sh:in               | ✓      | ✓     | ✓     |
| Named shape reference          | ✓      | ✓     | ✓     |
| DatatypeOr (DBpedia)           | ✓      | ✓     | ✓     |
| Pattern / regex                | ✓      | ✓     | ✓     |
| Shape-level `sh:and/or/not`    | ✓      | ✓     | ✓     |
| `sh:xone`                      | ✓      | ✓     | —     |
| `sh:targetNode/SubjectsOf/…`   | ✓      | ✓     | —     |
| Severity / message             | ✓      | ✓     | —     |
| Deactivated                    | ✓      | ✓     | —     |
| Property-pair constraints      | ✓      | ✓     | —     |
| Qualified value shapes         | ✓      | ✓     | —     |
| SPARQL constraints             | ✓      | ✓     | —     |
| Property paths (inverse, …)    | ✓      | ✓     | ✓     |
| `sh:languageIn` / `uniqueLang` | ✓      | ✓     | —     |
| `sh:extends`                   | ✓      | —     | ✓     |
| Numeric facets                 | ✓      | ✓     | ✓     |
| Semantic actions               | ✓      | —     | ✓     |
| Annotations                    | ✓      | —     | ✓     |

(*) via approximation

