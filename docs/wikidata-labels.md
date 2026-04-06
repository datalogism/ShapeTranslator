# Wikidata Label-Aware ShEx Generation

When generating ShEx for Wikidata-based schemas, shape references and comments use human-readable English labels instead of raw QIDs/PIDs. The feature is **disabled by default** (no network calls are made) and only applies to the `shacl2shex` direction.

## CLI

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

## Key behaviours

- `@<ShapeName>` uses the English label of the class, never raw QIDs like `@<Q5>`.
- Single-class auxiliaries use the **class** label (`@<Human>` for Q5).
- Multi-class OR auxiliaries use the **property** label.
- Multiple properties targeting the same class share one auxiliary shape.
- Section headers separate WikibaseItem properties from literal/IRI properties.
- Auxiliary shapes get `# qid_label, qid_label` comments.

## Python API

```python
from shaclex_py.utils.wikidata import collect_iris_from_shacl, fetch_labels
from shaclex_py import parse_shacl_file, convert_shacl_to_shex, serialize_shex

shacl     = parse_shacl_file("Q1172284.ttl")
label_map = fetch_labels(collect_iris_from_shacl(shacl))  # one SPARQL round-trip

shex   = convert_shacl_to_shex(shacl, label_map=label_map)
output = serialize_shex(shex,          label_map=label_map)
```

Pass `label_map=None` (default) for plain output without any network calls.
