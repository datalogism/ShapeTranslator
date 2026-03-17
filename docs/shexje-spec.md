# ShexJE — ShEx JSON Extended Specification

**Version**: 1.0
**Status**: Draft
**Supersedes**: Canonical JSON (internal interchange format)

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
3. **Canonical-JSON compatibility** — the simplified shorthand fields used by
   the previous canonical JSON format (`classRef`, `iriStem`, `hasValue`, …)
   are retained as first-class fields so existing tooling migrates with
   zero friction.

ShexJE uses the same `"type"` discriminator pattern as ShexJ and produces
deterministic, human-readable JSON.

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

  "uniqueLang": false,

  "classRef":   "schema:Person",
  "classRefOr": ["schema:Person", "schema:Organization"],
  "iriStem":    "https://www.wikidata.org/wiki/",
  "hasValue":   "ex:specificValue",
  "in":         ["active", "inactive"]
}
```

#### ShexJE extensions

| Field                            | Type               | SHACL / canonical equivalent            |
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
| **`classRef`**                   | IRI string         | Canonical shorthand → `ShapeRef`        |
| **`classRefOr`**                 | IRI[]              | Canonical shorthand → OR of classes     |
| **`iriStem`**                    | IRI string         | Canonical shorthand → IriStem value-set |
| **`hasValue`**                   | IRI or literal     | Canonical shorthand → `sh:hasValue`     |
| **`in`**                         | value[]            | Canonical shorthand → `sh:in`           |

> **Shorthand precedence**: shorthand fields (`classRef`, `classRefOr`,
> `iriStem`, `hasValue`, `in`) take priority over `valueExpr` when both are
> present.  Prefer native `valueExpr` forms for new documents; shorthands are
> provided for migration from canonical JSON.

### 4.2 EachOf / OneOf

Unchanged from ShexJ (`"type": "EachOf"` / `"type": "OneOf"`).

```json
{ "type": "EachOf", "expressions": [ ... ], "min": 1, "max": 1 }
{ "type": "OneOf",  "expressions": [ ... ] }
```

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

## 8. Canonical JSON → ShexJE mapping

The previous internal canonical JSON format maps cleanly to ShexJE:

| Canonical JSON field          | ShexJE equivalent                                    |
|-------------------------------|------------------------------------------------------|
| `shapes[].name`               | `shapes[].id`                                        |
| `shapes[].targetClass`        | `shapes[].targetClass`                               |
| `shapes[].closed`             | `shapes[].closed`                                    |
| `shapes[].datatypeOr`         | `ShapeOrE` with `NodeConstraintE(datatype=…)` items  |
| `properties[].path`           | `TripleConstraintE.predicate`                        |
| `properties[].datatype`       | `valueExpr: {type:"NodeConstraint", datatype:…}`     |
| `properties[].classRef`       | `TripleConstraintE.classRef` shorthand               |
| `properties[].classRefOr`     | `TripleConstraintE.classRefOr` shorthand             |
| `properties[].nodeKind`       | `valueExpr: {type:"NodeConstraint", nodeKind:…}`     |
| `properties[].hasValue`       | `TripleConstraintE.hasValue` shorthand               |
| `properties[].inValues`       | `valueExpr: {type:"NodeConstraint", values:[…]}`     |
| `properties[].iriStem`        | `TripleConstraintE.iriStem` shorthand                |
| `properties[].nodeRef`        | `valueExpr: {type:"ShapeRef", reference:…}`          |
| `properties[].pattern`        | added to `NodeConstraintE.pattern`                   |
| `properties[].cardinality`    | `TripleConstraintE.min` / `TripleConstraintE.max`    |

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
| `sh:class C`                               | `classRef: C` shorthand                                 |
| `sh:or ([sh:class C1][sh:class C2])`       | `classRefOr: [C1, C2]` shorthand                        |
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
| `sh:node S`                                | `valueExpr: {type:"ShapeRef", reference:S}`             |
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
            "type":     "TripleConstraint",
            "predicate": "schema:name",
            "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:string" },
            "min": 1, "max": 1
          },
          {
            "type":     "TripleConstraint",
            "predicate": "schema:birthDate",
            "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:date" },
            "min": 0, "max": 1,
            "severity": "sh:Warning"
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:knows",
            "classRef":  "PersonShape",
            "min": 0, "max": -1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:alumniOf",
            "classRefOr": ["schema:CollegeOrUniversity", "schema:HighSchool"],
            "min": 0, "max": -1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:url",
            "iriStem":   "https://",
            "min": 0, "max": -1
          },
          {
            "type":      "TripleConstraint",
            "predicate": "schema:gender",
            "in":        ["Male", "Female", "NonBinary"],
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
      ↓    ↘          ↙    ↓               ↙       ↓
      ↓  convert_*_to_canonical()    convert_shexje_to_canonical()
      ↓              ↓                              ↓
      ↓         CanonicalSchema ←──────────────────→ CanonicalSchema
      ↓              ↓                convert_canonical_to_shexje()
      ↓    convert_canonical_to_shacl/shex()
      ↓              ↓
 serialize_shacl()  serialize_shex()       serialize_shexje()
      ↓                   ↓                      ↓
 SHACL (Turtle)       ShExC               ShexJE JSON
```

### Feature support matrix

| Feature                        | Canonical JSON | ShexJE | SHACL | ShExC |
|--------------------------------|:--------------:|:------:|:-----:|:-----:|
| Shape + properties             | ✓              | ✓      | ✓     | ✓     |
| `targetClass`                  | ✓              | ✓      | ✓     | ✓*    |
| Closed shapes                  | ✓              | ✓      | ✓     | ✓     |
| Datatype constraint            | ✓              | ✓      | ✓     | ✓     |
| Class reference (`sh:class`)   | ✓              | ✓      | ✓     | ✓     |
| OR of classes                  | ✓              | ✓      | ✓     | ✓     |
| NodeKind constraint            | ✓              | ✓      | ✓     | ✓     |
| IRI stem                       | ✓              | ✓      | ✓*    | ✓     |
| Cardinality                    | ✓              | ✓      | ✓     | ✓     |
| hasValue / sh:in               | ✓              | ✓      | ✓     | ✓     |
| Named shape reference          | ✓              | ✓      | ✓     | ✓     |
| DatatypeOr (DBpedia)           | ✓              | ✓      | ✓     | ✓     |
| Pattern / regex                | ✓              | ✓      | ✓     | ✓     |
| Shape-level `sh:and/or/not`    | —              | ✓      | ✓     | ✓     |
| `sh:xone`                      | —              | ✓      | ✓     | —     |
| `sh:targetNode/SubjectsOf/…`   | —              | ✓      | ✓     | —     |
| Severity / message             | —              | ✓      | ✓     | —     |
| Deactivated                    | —              | ✓      | ✓     | —     |
| Property-pair constraints      | —              | ✓      | ✓     | —     |
| Qualified value shapes         | —              | ✓      | ✓     | —     |
| SPARQL constraints             | —              | ✓      | ✓     | —     |
| Property paths (inverse, …)    | —              | ✓      | ✓     | ✓     |
| `sh:languageIn` / `uniqueLang` | —              | ✓      | ✓     | —     |
| `sh:extends`                   | —              | ✓      | —     | ✓     |
| Numeric facets                 | —              | ✓      | ✓     | ✓     |
| Semantic actions               | —              | ✓      | —     | ✓     |
| Annotations                    | —              | ✓      | —     | ✓     |

(*) via approximation

### Canonical JSON migration

Existing canonical JSON files continue to work unchanged via `parse_canonical()`.
To migrate to ShexJE:

```python
from shaclex_py import (
    parse_canonical, convert_canonical_to_shexje, serialize_shexje
)

canonical = parse_canonical("my_schema.json")
shexje    = convert_canonical_to_shexje(canonical)
print(serialize_shexje(shexje))
```
