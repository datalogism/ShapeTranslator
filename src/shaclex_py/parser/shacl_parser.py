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
    # sh:path — may be a plain IRI or a blank node with sh:alternativePath
    path_node = g.value(prop_node, SH.path)
    alternative_paths = None
    if isinstance(path_node, BNode):
        alt_head = g.value(path_node, SH.alternativePath)
        if alt_head is not None:
            alt_items = _parse_rdf_list(g, alt_head)
            alternative_paths = [_uri_to_iri(i) for i in alt_items if isinstance(i, URIRef)]
            path_iri = alternative_paths[0] if alternative_paths else IRI(str(path_node))
        else:
            path_iri = IRI(str(path_node))
    else:
        path_iri = _uri_to_iri(path_node) if isinstance(path_node, URIRef) else IRI(str(path_node))
    path = Path(iri=path_iri)

    # sh:datatype (also accept sh:dataType — non-standard capitalization used by shexer)
    dt = g.value(prop_node, SH.datatype) or g.value(prop_node, SH["dataType"])
    datatype = _uri_to_iri(dt) if dt else None

    # sh:class — simple class or sh:or pattern
    # Handles two forms:
    #   (a) Custom YAGO form: sh:class [sh:or (class1 class2)]
    #   (b) Standard SHACL form: sh:or ([sh:class class1] [sh:class class2])
    or_classes = _parse_or_classes(g, prop_node)
    class_ = None
    or_constraints = None
    if or_classes:
        or_constraints = or_classes
    else:
        cls = g.value(prop_node, SH["class"])
        if cls and isinstance(cls, URIRef):
            class_ = _uri_to_iri(cls)

    # Standard sh:or at property shape level (pySHACL-compatible form)
    if or_constraints is None and class_ is None:
        or_list_head = g.value(prop_node, SH["or"])
        if or_list_head is not None:
            items = _parse_rdf_list(g, or_list_head)
            classes = [
                _uri_to_iri(g.value(item, SH["class"]))
                for item in items
                if isinstance(g.value(item, SH["class"]), URIRef)
            ]
            if classes:
                or_constraints = classes

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
        alternative_paths=alternative_paths,
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

        # sh:or at NodeShape level — two sub-patterns:
        # (a) sh:or ([ sh:datatype D1 ] [ sh:datatype D2 ] ...) — named value shape
        # (b) sh:or ([ sh:property [...] ] [ sh:property [...] ] ...) — property alternatives
        or_datatypes = None
        or_property_groups = None
        or_head = g.value(shape_node, SH["or"])
        if or_head is not None:
            or_items = _parse_rdf_list(g, or_head)
            # Detect pattern (a): every alternative has sh:datatype
            dt_list = [
                _uri_to_iri(g.value(item, SH.datatype))
                for item in or_items
                if isinstance(g.value(item, SH.datatype), URIRef)
            ]
            if len(dt_list) == len(or_items) and or_items:
                or_datatypes = dt_list
            else:
                # Pattern (b): alternatives may contain sh:property blocks.
                # Flatten all property alternatives into the shape's property list
                # AND record the groups for round-trip fidelity via alternativeGroups.
                groups: list[list] = []
                for item in or_items:
                    group: list = []
                    for prop_node in g.objects(item, SH.property):
                        ps = _parse_property_shape(g, prop_node)
                        properties.append(ps)
                        group.append(ps)
                    if group:
                        groups.append(group)
                or_property_groups = groups or None

        # Node-level constraints (reusable value shapes without sh:property)
        shape_nk = g.value(shape_node, SH.nodeKind)
        shape_node_kind = NODE_KIND_MAP.get(shape_nk) if shape_nk else None

        shape_dt = g.value(shape_node, SH.datatype) or g.value(shape_node, SH["dataType"])
        shape_node_datatype = _uri_to_iri(shape_dt) if shape_dt else None

        shape_in_head = g.value(shape_node, SH["in"])
        shape_node_in_values = None
        if shape_in_head is not None:
            shape_in_items = _parse_rdf_list(g, shape_in_head)
            shape_node_in_values = [_rdf_to_value(g, item) for item in shape_in_items]

        shapes.append(NodeShape(
            iri=shape_iri,
            target_class=target_class,
            properties=properties,
            closed=closed,
            ignored_properties=ignored_properties,
            or_datatypes=or_datatypes,
            node_kind=shape_node_kind,
            node_datatype=shape_node_datatype,
            node_in_values=shape_node_in_values,
            or_property_groups=or_property_groups,
        ))

    return SHACLSchema(shapes=shapes, prefixes=prefixes)


def parse_shacl_file(filepath: str) -> SHACLSchema:
    """Parse a SHACL Turtle file from a file path."""
    return parse_shacl(filepath, format="turtle")
