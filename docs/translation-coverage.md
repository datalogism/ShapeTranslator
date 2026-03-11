# Translation Coverage

This document catalogues which constructs from [Validating RDF Data, Ch. 13](https://book.validatingrdf.com/bookHtml013.html) are fully translated, which are approximated, and which are currently out of scope.

---

## Fully supported translations

The following patterns survive the SHACL→JSON→ShEx→JSON and ShEx→JSON→ShEx→JSON cycles with **zero data loss** (verified across 147 files, 4 309 properties — see [Evaluation](evaluation.md)).

| Construct | SHACL side | ShEx side | Book § |
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

---

## Approximated translations

Data is preserved; semantics are relaxed.

### `sh:or` with `sh:property` alternative groups at NodeShape level

The DBpedia pattern where `sh:or` appears on a `sh:NodeShape` with full `sh:property` blocks as alternatives (modelling two equivalent measurement paths) is **flattened into a union**. Every property path and its constraints are preserved, but the "exactly one branch must hold" exclusivity is not expressible in either ShEx or the canonical JSON model.

See [Mapping Rules — Property alternative groups](mapping-rules.md#property-alternative-groups--sh:or-with-sh:property-items-at-nodeshape-level) for a full analysis.

### `sh:pattern` — arbitrary regular expressions

`sh:pattern` values that match a URL prefix (`^http://...`) are converted to a ShEx `IriStem`. Arbitrary regex patterns have no ShEx equivalent and are carried through the canonical model as a `pattern` string; ShEx validators may or may not support them.

---

## Known gaps — constructs silently dropped today

When present in input these constructs are silently ignored and do not appear in the output, with no warning to the user.

### 1. SPARQL property paths (§7.9)

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
- Map `sh:alternativePath` → multiple independent properties (over-approximation).
- For `sh:zeroOrMorePath` and sequence paths, emit a warning comment; no loss-free translation exists per the book.

---

### 2. Recursion — ShEx→SHACL direction (§7.10)

**What ShEx allows:**
```shex
:UserShape IRI {
  schema:knows @:UserShape *
}
```

**SHACL:** The specification explicitly leaves recursive `sh:node` **undefined**. Most SHACL validators either loop or reject it.

**Current behaviour:** The translator emits recursive `sh:node` literally in the SHACL output. The result is formally undefined and may break validators.

**To fix:** Detect self-referencing `ShapeRef`s in the ShEx→SHACL converter and replace them with a documented approximation. The book suggests two workarounds: `sh:targetSubjectsOf` (loses type constraint) or `sh:zeroOrMorePath` (loses shape identity). No translation preserves full recursive semantics in SHACL.

---

### 3. Qualified value shapes (§7.12)

**What SHACL allows:**
```turtle
sh:property [
    sh:path schema:parent ;
    sh:qualifiedValueShape [ sh:property [ sh:path :isMale ; sh:hasValue true ] ] ;
    sh:qualifiedMinCount 1 ; sh:qualifiedMaxCount 1 ;
] ;
```

**ShEx equivalent:** Multiple triple constraints on the same predicate with different node constraints — natively supported.

**Current behaviour:** `sh:qualifiedValueShape`, `sh:qualifiedMinCount`, and `sh:qualifiedMaxCount` are not parsed. The constraints are silently dropped.

**To fix:** Add `qualified_constraints` to `PropertyShape` and `CanonicalProperty`. Parse the three SHACL fields. In the ShEx serializer, emit one `TripleConstraint` per qualified block. This is the correct translation direction per the book.

---

### 4. Logical operators: `sh:and`, `sh:not`, `sh:xone` (§7.13)

**What SHACL allows:**
```turtle
sh:and ( :ShapeA :ShapeB )      # conjunction — both must pass
sh:not :ShapeC                  # negation
sh:xone ( :ShapeA :ShapeB )     # exclusive OR — exactly one must pass
```

**ShEx equivalents:** `AND`, `NOT`, `|`. Note: `sh:xone` and ShEx `|` have **different semantics** — `sh:xone` requires other branches not even partially match; ShEx `|` requires at least one branch fully matches.

**Current behaviour:** All three are silently dropped when parsing SHACL.

**To fix:** Add `and_constraints`, `not_constraint`, `xone_constraints` to the schema model. Map `sh:and` → `AND`, `sh:not` → `NOT`, `sh:xone` → `|` with a semantic-difference comment.

---

### 5. Property pair constraints (§7.11)

**What SHACL allows:**
```turtle
sh:property [ sh:path schema:birthDate ; sh:lessThan :loginDate ] ;
sh:property [ sh:path foaf:firstName ;  sh:equals schema:givenName ] ;
sh:property [ sh:path schema:givenName ; sh:disjoint schema:lastName ] .
```

**ShEx equivalent:** None. The book states: "ShEx 2.0 does not have the concept of property pair constraints."

**Current behaviour:** `sh:lessThan`, `sh:equals`, and `sh:disjoint` are silently dropped.

**To fix:** Parse them and carry as opaque annotations in the canonical model. Preserve in SHACL roundtrips. Emit warning comments on ShEx output.

---

### 6. Numeric and string facets (§7.8)

SHACL: `sh:minInclusive`, `sh:maxInclusive`, `sh:minExclusive`, `sh:maxExclusive`, `sh:minLength`, `sh:maxLength`, `sh:languageIn`, `sh:uniqueLang`

ShEx: `MININCLUSIVE`, `MAXINCLUSIVE`, `MINEXCLUSIVE`, `MAXEXCLUSIVE`, `MINLENGTH`, `MAXLENGTH` on `NodeConstraint`

**Current behaviour:** None of these facets are parsed or emitted. They are silently dropped on both sides.

**To fix:** Add facet fields to `PropertyShape`, `NodeConstraint`, and `CanonicalProperty`. Wire through all parsers, converters, and serializers. The SHACL↔ShEx mapping is 1-to-1 for the six numeric/length facets. (`sh:languageIn` and `sh:uniqueLang` have no ShEx equivalent.)

---

### 7. Non-class target declarations (§7.4)

**What SHACL allows beyond `sh:targetClass`:**
```turtle
sh:targetNode ex:Alice              # targets a specific named node
sh:targetObjectsOf schema:knows     # targets all objects of this predicate
sh:targetSubjectsOf schema:knows    # targets all subjects of this predicate
```

**ShEx equivalent:** None inline — ShEx uses external shape maps for node–shape association.

**Current behaviour:** Only `sh:targetClass` is parsed. The other three target types are silently ignored.

**To fix:** Parse them and carry as annotations in the canonical model. Preserve in SHACL roundtrips. Emit `# NOTE: target scope cannot be expressed inline in ShEx` comments in ShEx output.

---

## Gap priority summary

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
