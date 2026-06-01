# Wikidata Label-Aware Output

When generating output for Wikidata-based schemas, human-readable English labels
are used instead of raw QIDs/PIDs. The feature is **disabled by default** (no
network calls are made) and is activated with `--wikidata-labels`.

Supported directions and how labels are injected:

| Direction | Effect |
|-----------|--------|
| `shacl2shex` | `@<ShapeName>` uses the class label; inline `# property label` comments |
| `shex2shacl` | `sh:name "label"@en` on property shapes; `rdfs:label "label"@en` on node shapes |
| `shexje2shacl` | same as `shex2shacl` |

## CLI

**ShEx → SHACL with labels:**
```bash
shaclex-py --input dataset/shex_wes/Q1172284.shex --direction shex2shacl --wikidata-labels
```

The output will include `sh:name` on each property shape and `rdfs:label` on the
node shape:

```turtle
<http://shaclshapes.org/DataSetShape> a sh:NodeShape ;
    rdfs:label "dataset"@en ;
    sh:property [ sh:datatype xsd:dateTime ;
            sh:maxCount 1 ;
            sh:name "publication date"@en ;
            sh:path wdt:P577 ],
        [ sh:nodeKind sh:IRI ;
            sh:name "author"@en ;
            sh:path wdt:P50 ] ;
    sh:targetClass wd:Q1172284 .
```

**SHACL → ShEx with labels:**
```bash
shaclex-py --input Q1172284.ttl --direction shacl2shex --wikidata-labels
```

```shex
<DataSet> EXTRA wdt:P31 {
  # WikibaseItem property
  wdt:P31   [ wd:Q1172284 ] ;            # instance of
  wdt:P50   @<Author> * ;                # author
  wdt:P126  @<MaintainedBy> ? ;          # maintained by

  # URL, String, Quantity, Time property
  wdt:P577  xsd:dateTime ? ;             # publication date
}
```

**Batch conversion with labels:**
```bash
shaclex-py --input-dir dataset/shex_wes/ --output-dir output/wes_shacl_labeled/ \
           --direction shex2shacl --wikidata-labels
```

## Key behaviours

**shacl2shex:**
- `@<ShapeName>` uses the English label of the class, never raw QIDs like `@<Q5>`.
- Single-class auxiliaries use the **class** label (`@<Human>` for Q5).
- Multi-class OR auxiliaries use the **property** label.
- Section headers separate WikibaseItem properties from literal/IRI properties.

**shex2shacl / shexje2shacl:**
- `sh:name "label"@en` added to every property shape whose `sh:path` is a `wdt:P...` IRI with a known label.
- `rdfs:label "label"@en` added to every node shape whose `sh:targetClass` is a `wd:Q...` IRI with a known label.
- At most **two SPARQL requests** per file (one for Q-items, one for P-properties).
- IRIs with no label in Wikidata are silently skipped (no stub triples).

## Python API

**ShEx → SHACL:**
```python
from shaclex_py.utils.wikidata import collect_iris_from_shacl, fetch_labels
from shaclex_py import parse_shex_file, convert_shex_to_shacl, serialize_shacl

shex      = parse_shex_file("Q1172284.shex")
shacl     = convert_shex_to_shacl(shex)
label_map = fetch_labels(collect_iris_from_shacl(shacl))  # one SPARQL round-trip
output    = serialize_shacl(shacl, label_map=label_map)
```

**SHACL → ShEx:**
```python
from shaclex_py.utils.wikidata import collect_iris_from_shacl, fetch_labels
from shaclex_py import parse_shacl_file, convert_shacl_to_shex, serialize_shex

shacl     = parse_shacl_file("Q1172284.ttl")
label_map = fetch_labels(collect_iris_from_shacl(shacl))  # one SPARQL round-trip
shex      = convert_shacl_to_shex(shacl, label_map=label_map)
output    = serialize_shex(shex, label_map=label_map)
```

Pass `label_map=None` (default) for plain output without any network calls.
