# Validator Compatibility

## pySHACL

SHACL output produced by shaclex-py is compatible with [pySHACL](https://github.com/RDFLib/pySHACL).

```python
import pyshacl
from shaclex_py import parse_shacl_file, serialize_shacl

schema = parse_shacl_file("shapes.ttl")
shapes_turtle = serialize_shacl(schema)

conforms, report_graph, report_text = pyshacl.validate(
    data_graph="data.ttl",
    data_graph_format="turtle",
    shacl_graph=shapes_turtle,
    shacl_graph_format="turtle",
)
print(report_text)
```

### OR-class constraint encoding

The SHACL specification requires `sh:or` at the property shape level for disjunctive class constraints. shaclex-py serializes these as:

```turtle
sh:property [
    sh:path schema:founder ;
    sh:or ([ sh:class schema:Organization ] [ sh:class schema:Person ]) ;
] ;
```

The parser also accepts the custom YAGO form (`sh:class [ sh:or (...) ]`) for backward compatibility with the `dataset/shacl_yago/` reference files.

---

## PyShEx

ShExC output produced by shaclex-py is compatible with [PyShEx](https://github.com/hsolbrig/PyShEx).

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
    start="http://example.org/MyShape",
)
for r in results:
    print(r.focus, "conforms:", r.result)
```

### Shape name IRIs

shaclex-py serializes shape names as relative IRIs (e.g. `<Person>`). When using PyShEx, resolve these against your chosen base URI or provide fully-qualified IRIs in the `start` parameter.
