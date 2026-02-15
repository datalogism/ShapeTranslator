"""shaclex-py: A Python SHACL/ShEx bidirectional translator.

Companion/extension to weso/shaclex (Scala reference implementation).
"""
__version__ = "0.1.0"

from shaclex_py.schema.common import IRI, Cardinality, NodeKind, Prefix
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.shex import Shape, ShExSchema, TripleConstraint
from shaclex_py.schema.canonical import CanonicalSchema, CanonicalShape

from shaclex_py.parser.shacl_parser import parse_shacl, parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex, parse_shex_file

from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
from shaclex_py.converter.shex_to_shacl import convert_shex_to_shacl
from shaclex_py.converter.shacl_to_canonical import convert_shacl_to_canonical
from shaclex_py.converter.shex_to_canonical import convert_shex_to_canonical
from shaclex_py.converter.canonical_to_shacl import convert_canonical_to_shacl
from shaclex_py.converter.canonical_to_shex import convert_canonical_to_shex

from shaclex_py.parser.json_parser import parse_canonical, parse_canonical_file

from shaclex_py.serializer.shacl_serializer import serialize_shacl
from shaclex_py.serializer.shex_serializer import serialize_shex
from shaclex_py.serializer.json_serializer import serialize_json

__all__ = [
    # Schema
    "IRI", "Cardinality", "NodeKind", "Prefix",
    "NodeShape", "PropertyShape", "SHACLSchema",
    "Shape", "ShExSchema", "TripleConstraint",
    "CanonicalSchema", "CanonicalShape",
    # Parsers
    "parse_shacl", "parse_shacl_file",
    "parse_shex", "parse_shex_file",
    # Converters
    "convert_shacl_to_shex", "convert_shex_to_shacl",
    "convert_shacl_to_canonical", "convert_shex_to_canonical",
    "convert_canonical_to_shacl", "convert_canonical_to_shex",
    # Parsers (canonical)
    "parse_canonical", "parse_canonical_file",
    # Serializers
    "serialize_shacl", "serialize_shex", "serialize_json",
]
