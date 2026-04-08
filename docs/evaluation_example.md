# Evaluation Examples

One concrete worked example per chain, showing intermediate representations.  The
chains are defined in [Evaluation](evaluation.md); this document makes them tangible.

---

## Key

| Format | Role |
|--------|------|
| **SHACL (Turtle)** | Source or target for SHACL-starting chains |
| **ShexJE (JSON-LD)** | Canonical intermediate format (ShEx JSON-Extended) |
| **ShEx (ShExC)** | Source or target for ShEx-starting chains; intermediate for chains B/D |

---

## Chain A — SHACL → ShexJE → SHACL

Both chains start from the same SHACL file and produce the final SHACL after round-tripping through ShexJE.

### Example A — YAGO `Gender.ttl`

**Source SHACL** (`dataset/shacl_yago/Gender.ttl`)
```turtle
<http://shaclshapes.org/GenderShape> a sh:NodeShape ;
    sh:targetClass yago:Gender ;
    sh:property [ sh:path rdfs:label ;       sh:minCount 1 ; sh:datatype rdf:langString ] ;
    sh:property [ sh:path rdfs:comment ;                     sh:datatype rdf:langString ] ;
    sh:property [ sh:path schema:alternateName ;             sh:datatype rdf:langString ] ;
    sh:property [ sh:path schema:image ;     sh:maxCount 1 ; sh:datatype xsd:anyURI ] ;
    sh:property [ sh:path schema:mainEntityOfPage ; sh:minCount 1 ; sh:datatype xsd:anyURI ] ;
    sh:property [ sh:path schema:sameAs ;    sh:maxCount 1 ; sh:datatype xsd:anyURI ] ;
    sh:property [ sh:path owl:sameAs ;       sh:pattern "^http://www.wikidata.org/entity/" ] .
```

**Chain A intermediate — ShexJE**
```json
{
  "@context": "http://www.w3.org/ns/shexje.jsonld",
  "type": "Schema",
  "shapes": [{
    "type": "Shape",
    "id": "Gender",
    "targetClass": "http://yago-knowledge.org/resource/Gender",
    "expression": {
      "type": "EachOf",
      "expressions": [
        { "type": "TripleConstraint", "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
          "valueExpr": { "type": "NodeConstraint", "datatype": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString" }, "min": 1, "max": -1 },
        { "type": "TripleConstraint", "predicate": "http://www.w3.org/2000/01/rdf-schema#comment",
          "valueExpr": { "type": "NodeConstraint", "datatype": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString" } },
        { "type": "TripleConstraint", "predicate": "http://schema.org/alternateName",
          "valueExpr": { "type": "NodeConstraint", "datatype": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString" } },
        { "type": "TripleConstraint", "predicate": "http://schema.org/image",
          "valueExpr": { "type": "NodeConstraint", "datatype": "http://www.w3.org/2001/XMLSchema#anyURI" }, "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "http://schema.org/mainEntityOfPage",
          "valueExpr": { "type": "NodeConstraint", "datatype": "http://www.w3.org/2001/XMLSchema#anyURI" }, "min": 1, "max": -1 },
        { "type": "TripleConstraint", "predicate": "http://schema.org/sameAs",
          "valueExpr": { "type": "NodeConstraint", "datatype": "http://www.w3.org/2001/XMLSchema#anyURI" }, "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "http://www.w3.org/2002/07/owl#sameAs",
          "iriStem": "http://www.wikidata.org/entity" }
      ]
    }
  }]
}
```

**Chain A output — Regenerated SHACL**
```turtle
<http://shaclshapes.org/GenderShape> a sh:NodeShape ;
    sh:property [ sh:datatype rdf:langString ;      sh:path schema:alternateName ],
        [ sh:datatype xsd:anyURI ; sh:maxCount 1 ;  sh:path schema:image ],
        [ sh:datatype xsd:anyURI ; sh:minCount 1 ;  sh:path schema:mainEntityOfPage ],
        [ sh:datatype xsd:anyURI ; sh:maxCount 1 ;  sh:path schema:sameAs ],
        [ sh:datatype rdf:langString ; sh:minCount 1 ; sh:path rdfs:label ],
        [ sh:datatype rdf:langString ;              sh:path rdfs:comment ],
        [ sh:path owl:sameAs ; sh:pattern "^http://www.wikidata.org/entity/" ] ;
    sh:targetClass yago:Gender .
```

> **What is preserved**: `targetClass`, all 7 property predicates, `datatype` on 6 of them,
> `iriStem` on the `owl:sameAs` property (serialised as `sh:pattern`), and all cardinalities.

---

### Example B — DBpedia `SportsTeam.ttl` (illustrates `sh:alternativePath`)

**Source SHACL** (excerpt — `dataset/shacl_dbpedia/SportsTeam.ttl`)
```turtle
sh:property [
    sh:path [ sh:alternativePath ( dbo:stadium dbo:homeStadium ) ] ;
    sh:class dbo:Stadium ;
    sh:minCount 1 ;
] ;
```

**ShexJE** (the relevant `TripleConstraint`)
```json
{
  "type": "TripleConstraint",
  "path": {
    "type": "AlternativePath",
    "expressions": [
      "http://dbpedia.org/ontology/stadium",
      "http://dbpedia.org/ontology/homeStadium"
    ]
  },
  "min": 1,
  "max": -1,
  "classRef": "http://dbpedia.org/ontology/Stadium"
}
```

**Regenerated SHACL** (round-trip output)
```turtle
sh:property [
    sh:class <http://dbpedia.org/ontology/Stadium> ;
    sh:minCount 1 ;
    sh:path [ sh:alternativePath ( <http://dbpedia.org/ontology/stadium>
                                   <http://dbpedia.org/ontology/homeStadium> ) ]
] ;
```

> **What is preserved**: both alternative paths, the `sh:class` constraint, and the `sh:minCount`.
> The `sh:alternativePath` BNode structure is fully round-tripped through ShexJE.

---

## Chain B — SHACL → ShexJE → ShEx → ShexJE → SHACL

Five-stage cycle going through ShEx as the middle format.  `pathAlternatives` are **flattened**
to two independent triple constraints in ShEx (ShEx has no `alternativePath` syntax), but all
other constraints are preserved.

### Example — YAGO `Gender.ttl` (continued)

**ShEx intermediate** (generated by chain B)
```shex
start = @<Gender>

<Gender> EXTRA rdf:type {
  rdf:type [ yago:Gender ] ;
  rdfs:label rdf:langString + ;
  rdfs:comment rdf:langString * ;
  schema:alternateName rdf:langString * ;
  schema:image xsd:anyURI ? ;
  schema:mainEntityOfPage xsd:anyURI + ;
  schema:sameAs xsd:anyURI ? ;
  owl:sameAs [ <http://www.wikidata.org/entity>~ ] *
}
```

**Chain B final output — Regenerated SHACL**

Same as the Chain A output above — all 7 properties are preserved identically.

> **Note on `rdf:type`**: In chain B the `targetClass` IRI passes through ShEx as an
> explicit `rdf:type [ yago:Gender ]` triple constraint.  The SHACL serialiser converts it
> back to `sh:targetClass`, so the final SHACL is structurally identical.

### Example — DBpedia `SportsTeam.ttl` (pathAlternatives flattening)

**ShEx intermediate** (the flattened stadium properties)
```shex
<SportsTeam> EXTRA rdf:type {
  ...
  <http://dbpedia.org/ontology/stadium>     @<Stadium> + ;
  <http://dbpedia.org/ontology/homeStadium> @<Stadium> + ;
  ...
}

<Stadium> EXTRA rdf:type {
  rdf:type [ <http://dbpedia.org/ontology/Stadium> ]
}
```

**Chain B final SHACL** (after ShEx round-trip)

```turtle
sh:property [ sh:class <http://dbpedia.org/ontology/Stadium> ; sh:minCount 1 ;
              sh:path <http://dbpedia.org/ontology/stadium> ] ;
sh:property [ sh:class <http://dbpedia.org/ontology/Stadium> ; sh:minCount 1 ;
              sh:path <http://dbpedia.org/ontology/homeStadium> ] ;
```

> **Approximation**: `pathAlternatives` cannot be expressed in ShEx, so the two paths become
> separate independent properties.  Both predicates, the class constraint, and cardinality are
> preserved — only the "either one path or the other" grouping is lost.

---

## Chain C — ShEx → ShexJE → ShEx

### Example A — YAGO `Gender.shex`

**Source ShEx** (`dataset/shex_yago/Gender.shex`)
```shex
start = @<Gender>

<Gender> EXTRA rdf:type {
  rdf:type [ yago:Gender ] ;
  rdfs:label rdf:langString + ;
  rdfs:comment rdf:langString * ;
  schema:alternateName rdf:langString * ;
  schema:image xsd:anyURI ? ;
  schema:mainEntityOfPage xsd:anyURI + ;
  schema:sameAs xsd:anyURI ? ;
  owl:sameAs [ <http://www.wikidata.org/entity>~ ] *
}
```

**Chain C intermediate — ShexJE** _(same as the SHACL-source ShexJE above)_

**Chain C output — Regenerated ShEx**
```shex
start = @<Gender>

<Gender> EXTRA rdf:type {
  rdf:type [ yago:Gender ] ;
  rdfs:label rdf:langString + ;
  rdfs:comment rdf:langString * ;
  schema:alternateName rdf:langString * ;
  schema:image xsd:anyURI ? ;
  schema:mainEntityOfPage xsd:anyURI + ;
  schema:sameAs xsd:anyURI ? ;
  owl:sameAs [ <http://www.wikidata.org/entity>~ ] *
}
```

> **Result**: bit-for-bit identical to the source ShEx.

---

### Example B — WES `Q37748.shex` (Chromosome)

This WES file shows `classRef`, `nodeRef` (self-reference), and `nodeKind`.

**Source ShEx** (`dataset/shex_wes/Q37748.shex`)
```shex
start = @<Chromosome>

<Chromosome> EXTRA wdt:P31 {
  wdt:P31  [ wd:Q37748 ] ;       # instance of
  wdt:P703 @<Taxon> ;            # found in taxon
  wdt:P156 @<Chromosome> ? ;     # followed by (self-ref)
  wdt:P155 @<Chromosome> ? ;     # follows (self-ref)
  wdt:P361 IRI * ;               # part of
  wdt:P910 @<WikimediaCategory> ? ;
  wdt:P2043 xsd:decimal ? ;
  wdt:P1813 rdf:langString ? ;
  wdt:P373  xsd:string ?
}

<Taxon>             { wdt:P31 [ wd:Q16521   ] }
<WikimediaCategory> { wdt:P31 [ wd:Q4167836 ] }
```

**Chain C intermediate — ShexJE**
```json
{
  "type": "Schema",
  "shapes": [{
    "type": "Shape",
    "id": "Chromosome",
    "targetClass": "http://www.wikidata.org/entity/Q37748",
    "expression": {
      "type": "EachOf",
      "expressions": [
        { "type": "TripleConstraint", "predicate": "wdt:P703",  "classRef": "wd:Q16521",   "min": 1, "max": 1 },
        { "type": "TripleConstraint", "predicate": "wdt:P156",  "valueExpr": { "type": "ShapeRef", "reference": "Chromosome" }, "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "wdt:P155",  "valueExpr": { "type": "ShapeRef", "reference": "Chromosome" }, "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "wdt:P361",  "valueExpr": { "type": "NodeConstraint", "nodeKind": "IRI" } },
        { "type": "TripleConstraint", "predicate": "wdt:P910",  "classRef": "wd:Q4167836", "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "wdt:P2043", "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:decimal" },     "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "wdt:P1813", "valueExpr": { "type": "NodeConstraint", "datatype": "rdf:langString" },   "min": 0, "max": 1 },
        { "type": "TripleConstraint", "predicate": "wdt:P373",  "valueExpr": { "type": "NodeConstraint", "datatype": "xsd:string" },       "min": 0, "max": 1 }
      ]
    }
  }]
}
```

**Chain C output — Regenerated ShEx**
```shex
start = @<Chromosome>

<Chromosome> EXTRA rdf:type {
  rdf:type [ wd:Q37748 ] ;
  wdt:P703 @<Q16521> ;
  wdt:P156 @<Chromosome> ? ;
  wdt:P155 @<Chromosome> ? ;
  wdt:P361 IRI * ;
  wdt:P910 @<Q4167836> ? ;
  wdt:P2043 xsd:decimal ? ;
  wdt:P1813 rdf:langString ? ;
  wdt:P373  xsd:string ?
}

<Q16521>   EXTRA rdf:type { rdf:type [ wd:Q16521   ] }
<Q4167836> EXTRA rdf:type { rdf:type [ wd:Q4167836 ] }
```

> **Notes**:
> - Auxiliary shapes are named by the class IRI local name (`Q16521`, `Q4167836`) instead of `Taxon`
>   / `WikimediaCategory` because the Wikidata label resolver is not active for this chain.
>   In Wikidata label mode the names would be human-readable (e.g. `@<Taxon>`).
> - The self-referencing `@<Chromosome>` is preserved through the chain.

---

## Chain D — ShEx → ShexJE → SHACL → ShexJE → ShEx

Five-stage chains going through SHACL as the middle format.

### Example A — YAGO `Gender.shex`

**SHACL intermediate** (generated by chain D)
```turtle
<http://shaclshapes.org/GenderShape> a sh:NodeShape ;
    sh:property [ sh:path owl:sameAs ; sh:pattern "^http://www.wikidata.org/entity/" ],
        [ sh:datatype xsd:anyURI ; sh:maxCount 1 ;  sh:path schema:image ],
        [ sh:datatype xsd:anyURI ; sh:minCount 1 ;  sh:path schema:mainEntityOfPage ],
        [ sh:datatype rdf:langString ;              sh:path schema:alternateName ],
        [ sh:datatype rdf:langString ; sh:minCount 1 ; sh:path rdfs:label ],
        [ sh:datatype xsd:anyURI ; sh:maxCount 1 ;  sh:path schema:sameAs ],
        [ sh:datatype rdf:langString ;              sh:path rdfs:comment ] ;
    sh:targetClass yago:Gender .
```

**Chain D final output — Regenerated ShEx** _(same as Chain C)_

```shex
start = @<Gender>

<Gender> EXTRA rdf:type {
  rdf:type [ yago:Gender ] ;
  rdfs:label rdf:langString + ;
  rdfs:comment rdf:langString * ;
  schema:alternateName rdf:langString * ;
  schema:image xsd:anyURI ? ;
  schema:mainEntityOfPage xsd:anyURI + ;
  schema:sameAs xsd:anyURI ? ;
  owl:sameAs [ <http://www.wikidata.org/entity>~ ] *
}
```

---

### Example B — WES `Q37748.shex` (Chromosome)

**SHACL intermediate** (generated by chain D)
```turtle
<http://shaclshapes.org/ChromosomeShape> a sh:NodeShape ;
    sh:property [ sh:class <wd:Q16521> ;  sh:minCount 1 ; sh:maxCount 1 ; sh:path wdt:P703 ],
        [ sh:nodeKind sh:IRI ;            sh:path wdt:P361 ],
        [ sh:datatype xsd:decimal ;       sh:maxCount 1 ;  sh:path wdt:P2043 ],
        [ sh:maxCount 1 ; sh:node <Chromosome> ; sh:path wdt:P156 ],
        [ sh:maxCount 1 ; sh:node <Chromosome> ; sh:path wdt:P155 ],
        [ sh:class <wd:Q4167836> ;        sh:maxCount 1 ;  sh:path wdt:P910 ],
        [ sh:datatype rdf:langString ;    sh:maxCount 1 ;  sh:path wdt:P1813 ],
        [ sh:datatype xsd:string ;        sh:maxCount 1 ;  sh:path wdt:P373 ] ;
    sh:targetClass wd:Q37748 .
```

**Chain D final output — Regenerated ShEx** _(same as Chain C output)_
