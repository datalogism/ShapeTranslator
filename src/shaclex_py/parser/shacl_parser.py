"""Parse SHACL Turtle files into SHACL model using rdflib."""
from __future__ import annotations

from typing import Optional, Union

import rdflib
from rdflib import RDF, BNode, Graph, Namespace, URIRef
from rdflib.collection import Collection

from shaclex_py.schema.common import IRI, Literal, NodeKind, Path, Prefix
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema

SH = Namespace("http://www.w3.org/ns/shacl#")

NODE_KIND_MAP = {
    SH.IRI: NodeKind.IRI,
    SH.BlankNode: NodeKind.BLANK_NODE,
    SH.Literal: NodeKind.LITERAL,
    SH.BlankNodeOrIRI: NodeKind.BLANK_NODE_OR_IRI,
    SH.BlankNodeOrLiteral: NodeKind.BLANK_NODE_OR_LITERAL,
    SH.IRIOrLiteral: NodeKind.IRI_OR_LITERAL,
}


def _uri_to_iri(uri: URIRef) -> IRI:
    return IRI(str(uri))


def _rdf_to_value(g: Graph, node) -> Union[IRI, Literal]:
    if isinstance(node, URIRef):
        return _uri_to_iri(node)
    if isinstance(node, rdflib.Literal):
        dt = IRI(str(node.datatype)) if node.datatype else None
        lang = str(node.language) if node.language else None
        return Literal(value=str(node), datatype=dt, language=lang)
    return IRI(str(node))


def _parse_rdf_list(g: Graph, head) -> list:
    """Parse an RDF collection (list) starting at head."""
    if head is None or head == RDF.nil:
        return []
    return list(Collection(g, head))


def _parse_or_classes(g: Graph, prop_node: BNode) -> Optional[list[IRI]]:
    """Parse sh:class with sh:or pattern.

    Handles patterns like:
        sh:class [ sh:or ( schema:Org schema:Person ) ]
    """
    class_node = g.value(prop_node, SH["class"])
    if class_node is None:
        return None

    if isinstance(class_node, URIRef):
        return None  # Simple class, not an or-pattern

    # Check for sh:or on the class node (blank node)
    or_list_head = g.value(class_node, SH["or"])
    if or_list_head is None:
        return None

    items = _parse_rdf_list(g, or_list_head)
    return [_uri_to_iri(item) for item in items if isinstance(item, URIRef)]


def _parse_property_shape(g: Graph, prop_node) -> PropertyShape:
    """Parse a single property shape blank node."""
    # sh:path
    path_node = g.value(prop_node, SH.path)
    path_iri = _uri_to_iri(path_node) if isinstance(path_node, URIRef) else IRI(str(path_node))
    path = Path(iri=path_iri)

    # sh:datatype
    dt = g.value(prop_node, SH.datatype)
    datatype = _uri_to_iri(dt) if dt else None

    # sh:class — simple class or sh:or pattern
    or_classes = _parse_or_classes(g, prop_node)
    class_ = None
    or_constraints = None
    if or_classes:
        or_constraints = or_classes
    else:
        cls = g.value(prop_node, SH["class"])
        if cls and isinstance(cls, URIRef):
            class_ = _uri_to_iri(cls)

    # sh:nodeKind
    nk = g.value(prop_node, SH.nodeKind)
    node_kind = NODE_KIND_MAP.get(nk) if nk else None

    # sh:minCount, sh:maxCount
    min_c = g.value(prop_node, SH.minCount)
    min_count = int(min_c) if min_c is not None else None
    max_c = g.value(prop_node, SH.maxCount)
    max_count = int(max_c) if max_c is not None else None

    # sh:pattern
    pat = g.value(prop_node, SH.pattern)
    pattern = str(pat) if pat else None

    # sh:hasValue
    hv = g.value(prop_node, SH.hasValue)
    has_value = _rdf_to_value(g, hv) if hv else None

    # sh:in
    in_head = g.value(prop_node, SH["in"])
    in_values = None
    if in_head:
        items = _parse_rdf_list(g, in_head)
        in_values = [_rdf_to_value(g, item) for item in items]

    # sh:node
    node_ref = g.value(prop_node, SH.node)
    node = _uri_to_iri(node_ref) if node_ref and isinstance(node_ref, URIRef) else None

    return PropertyShape(
        path=path,
        datatype=datatype,
        class_=class_,
        node_kind=node_kind,
        min_count=min_count,
        max_count=max_count,
        pattern=pattern,
        has_value=has_value,
        in_values=in_values,
        node=node,
        or_constraints=or_constraints,
    )


def _extract_prefixes(g: Graph) -> list[Prefix]:
    """Extract prefix mappings from the graph."""
    prefixes = []
    for name, uri in g.namespaces():
        prefixes.append(Prefix(name=str(name), iri=str(uri)))
    return prefixes


def parse_shacl(source: str, format: str = "turtle") -> SHACLSchema:
    """Parse a SHACL file (Turtle string or file path) into SHACLSchema.

    Args:
        source: File path or Turtle string.
        format: RDF format (default: turtle).

    Returns:
        SHACLSchema with parsed shapes and prefixes.
    """
    g = Graph()
    # Try as file path first, then as data
    try:
        g.parse(source=source, format=format)
    except Exception:
        g.parse(data=source, format=format)

    prefixes = _extract_prefixes(g)
    shapes = []

    for shape_node in g.subjects(RDF.type, SH.NodeShape):
        shape_iri = _uri_to_iri(shape_node) if isinstance(shape_node, URIRef) else IRI(str(shape_node))

        # sh:targetClass
        tc = g.value(shape_node, SH.targetClass)
        target_class = _uri_to_iri(tc) if tc else None

        # sh:closed
        closed_val = g.value(shape_node, SH.closed)
        closed = bool(closed_val) if closed_val is not None else False

        # sh:ignoredProperties
        ignored_head = g.value(shape_node, SH.ignoredProperties)
        ignored_properties = []
        if ignored_head:
            items = _parse_rdf_list(g, ignored_head)
            ignored_properties = [_uri_to_iri(i) for i in items if isinstance(i, URIRef)]

        # Property shapes
        properties = []
        for prop_node in g.objects(shape_node, SH.property):
            ps = _parse_property_shape(g, prop_node)
            properties.append(ps)

        shapes.append(NodeShape(
            iri=shape_iri,
            target_class=target_class,
            properties=properties,
            closed=closed,
            ignored_properties=ignored_properties,
        ))

    return SHACLSchema(shapes=shapes, prefixes=prefixes)


def parse_shacl_file(filepath: str) -> SHACLSchema:
    """Parse a SHACL Turtle file from a file path."""
    return parse_shacl(filepath, format="turtle")
