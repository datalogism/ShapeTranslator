"""Serialize SHACL model to Turtle string using rdflib."""
from __future__ import annotations

import rdflib
from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.collection import Collection

from shaclex_py.schema.common import IRI, Literal, NodeKind
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema

SH = Namespace("http://www.w3.org/ns/shacl#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
SCHEMA = Namespace("http://schema.org/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

NODE_KIND_MAP = {
    NodeKind.IRI: SH.IRI,
    NodeKind.BLANK_NODE: SH.BlankNode,
    NodeKind.LITERAL: SH.Literal,
    NodeKind.BLANK_NODE_OR_IRI: SH.BlankNodeOrIRI,
    NodeKind.BLANK_NODE_OR_LITERAL: SH.BlankNodeOrLiteral,
    NodeKind.IRI_OR_LITERAL: SH.IRIOrLiteral,
}


def _iri_to_uri(iri: IRI) -> URIRef:
    return URIRef(iri.value)


def _value_to_rdf(val) -> rdflib.term.Node:
    if isinstance(val, IRI):
        return URIRef(val.value)
    if isinstance(val, Literal):
        dt = URIRef(val.datatype.value) if val.datatype else None
        lang = val.language
        return rdflib.Literal(val.value, datatype=dt, lang=lang)
    return rdflib.Literal(str(val))


def _add_property_shape(g: Graph, shape_node: URIRef, ps: PropertyShape):
    """Add a property shape as a blank node to the graph."""
    prop = BNode()
    g.add((shape_node, SH.property, prop))

    if ps.alternative_paths:
        # sh:path [ sh:alternativePath ( path1 path2 ... ) ]
        alt_items = [_iri_to_uri(p) for p in ps.alternative_paths]
        alt_list = BNode()
        Collection(g, alt_list, alt_items)
        path_bn = BNode()
        g.add((path_bn, SH.alternativePath, alt_list))
        g.add((prop, SH.path, path_bn))
    else:
        g.add((prop, SH.path, _iri_to_uri(ps.path.iri)))

    if ps.datatype:
        g.add((prop, SH.datatype, _iri_to_uri(ps.datatype)))

    if ps.class_:
        g.add((prop, SH["class"], _iri_to_uri(ps.class_)))

    if ps.node_kind:
        g.add((prop, SH.nodeKind, NODE_KIND_MAP[ps.node_kind]))

    if ps.min_count is not None:
        g.add((prop, SH.minCount, rdflib.Literal(ps.min_count)))

    if ps.max_count is not None:
        g.add((prop, SH.maxCount, rdflib.Literal(ps.max_count)))

    if ps.pattern:
        g.add((prop, SH.pattern, rdflib.Literal(ps.pattern)))

    if ps.has_value is not None:
        g.add((prop, SH.hasValue, _value_to_rdf(ps.has_value)))

    if ps.in_values is not None:
        items = [_value_to_rdf(v) for v in ps.in_values]
        collection = BNode()
        Collection(g, collection, items)
        g.add((prop, SH["in"], collection))

    if ps.node:
        g.add((prop, SH.node, _iri_to_uri(ps.node)))

    if ps.or_constraints:
        # Standard SHACL sh:or at property shape level:
        #   sh:or ([sh:class class1] [sh:class class2])
        # pySHACL requires this form; the custom sh:class [sh:or (...)] is
        # not standard SHACL.
        or_items = []
        for c in ps.or_constraints:
            item_node = BNode()
            g.add((item_node, SH["class"], _iri_to_uri(c)))
            or_items.append(item_node)
        or_list = BNode()
        Collection(g, or_list, or_items)
        g.add((prop, SH["or"], or_list))


def serialize_shacl(schema: SHACLSchema) -> str:
    """Serialize a SHACLSchema to Turtle string.

    Args:
        schema: The SHACL schema to serialize.

    Returns:
        Turtle format string.
    """
    g = Graph()

    # Bind standard prefixes (replace=True to override rdflib's builtins)
    g.bind("sh", SH, override=True, replace=True)
    g.bind("rdf", RDF, override=True, replace=True)
    g.bind("rdfs", RDFS, override=True, replace=True)
    g.bind("xsd", XSD, override=True, replace=True)
    g.bind("schema", SCHEMA, override=True, replace=True)
    g.bind("owl", OWL, override=True, replace=True)

    # Bind custom prefixes from schema
    for pfx in schema.prefixes:
        if pfx.name:
            g.bind(pfx.name, Namespace(pfx.iri), override=True, replace=True)

    for shape in schema.shapes:
        shape_uri = _iri_to_uri(shape.iri)
        g.add((shape_uri, rdflib.RDF.type, SH.NodeShape))

        if shape.target_class:
            g.add((shape_uri, SH.targetClass, _iri_to_uri(shape.target_class)))

        if shape.closed:
            g.add((shape_uri, SH.closed, rdflib.Literal(True)))

        if shape.ignored_properties:
            items = [_iri_to_uri(ip) for ip in shape.ignored_properties]
            collection = BNode()
            Collection(g, collection, items)
            g.add((shape_uri, SH.ignoredProperties, collection))

        # sh:or at NodeShape level (named value shapes with datatype alternatives)
        if shape.or_datatypes:
            or_items = []
            for dt in shape.or_datatypes:
                item_node = BNode()
                g.add((item_node, SH.datatype, _iri_to_uri(dt)))
                or_items.append(item_node)
            or_list = BNode()
            Collection(g, or_list, or_items)
            g.add((shape_uri, SH["or"], or_list))

        # Node-level constraints (reusable value shapes)
        if shape.node_kind is not None:
            g.add((shape_uri, SH.nodeKind, NODE_KIND_MAP[shape.node_kind]))

        if shape.node_datatype is not None:
            g.add((shape_uri, SH.datatype, _iri_to_uri(shape.node_datatype)))

        if shape.node_in_values is not None:
            items = [_value_to_rdf(v) for v in shape.node_in_values]
            collection = BNode()
            Collection(g, collection, items)
            g.add((shape_uri, SH["in"], collection))

        for ps in shape.properties:
            _add_property_shape(g, shape_uri, ps)

    result = g.serialize(format="turtle")
    # Fix rdflib's schema prefix issue (it uses schema1 for http://schema.org/
    # because it reserves 'schema' for https://schema.org/)
    result = result.replace("@prefix schema1: <http://schema.org/> .",
                            "@prefix schema: <http://schema.org/> .")
    result = result.replace("schema1:", "schema:")
    return result


def serialize_shacl_to_file(schema: SHACLSchema, filepath: str):
    """Serialize a SHACLSchema to a Turtle file."""
    turtle = serialize_shacl(schema)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(turtle)
