"""shaclex-py: A Python SHACL/ShEx bidirectional translator.

Companion/extension to weso/shaclex (Scala reference implementation).

ShexJE is the canonical intermediate format — all conversions between SHACL
and ShEx pass through ShexJE as the single source of truth.
"""
__version__ = "0.1.0"

from shaclex_py.schema.common import IRI, Cardinality, NodeKind, Prefix
from shaclex_py.schema.shacl import NodeShape, PropertyShape, SHACLSchema
from shaclex_py.schema.shex import Shape, ShExSchema, TripleConstraint
from shaclex_py.schema.shexje import (
    ShexJESchema,
    ShapeE,
    NodeConstraintE,
    ShapeOrE,
    ShapeAndE,
    ShapeNotE,
    ShapeXoneE,
    TripleConstraintE,
    EachOfE,
    OneOfE,
    ShapeRefE,
    IriStemValue,
    LiteralValue,
    SparqlConstraintE,
    InversePath,
    SequencePath,
    AlternativePath,
    ZeroOrMorePath,
    OneOrMorePath,
    ZeroOrOnePath,
)

from shaclex_py.parser.shacl_parser import parse_shacl, parse_shacl_file
from shaclex_py.parser.shex_parser import parse_shex, parse_shex_file
from shaclex_py.parser.shexje_parser import parse_shexje, parse_shexje_file

from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
from shaclex_py.converter.shex_to_shacl import convert_shex_to_shacl
from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex

from shaclex_py.serializer.shacl_serializer import serialize_shacl
from shaclex_py.serializer.shex_serializer import serialize_shex
from shaclex_py.serializer.shexje_serializer import serialize_shexje

__all__ = [
    # Schema — common
    "IRI", "Cardinality", "NodeKind", "Prefix",
    # Schema — SHACL
    "NodeShape", "PropertyShape", "SHACLSchema",
    # Schema — ShEx
    "Shape", "ShExSchema", "TripleConstraint",
    # Schema — ShexJE (canonical format)
    "ShexJESchema",
    "ShapeE", "NodeConstraintE",
    "ShapeOrE", "ShapeAndE", "ShapeNotE", "ShapeXoneE",
    "TripleConstraintE", "EachOfE", "OneOfE",
    "ShapeRefE", "IriStemValue", "LiteralValue",
    "SparqlConstraintE",
    "InversePath", "SequencePath", "AlternativePath",
    "ZeroOrMorePath", "OneOrMorePath", "ZeroOrOnePath",
    # Parsers
    "parse_shacl", "parse_shacl_file",
    "parse_shex", "parse_shex_file",
    "parse_shexje", "parse_shexje_file",
    # Converters — direct
    "convert_shacl_to_shex", "convert_shex_to_shacl",
    # Converters — via ShexJE canonical
    "convert_shacl_to_shexje", "convert_shex_to_shexje",
    "convert_shexje_to_shacl", "convert_shexje_to_shex",
    # Serializers
    "serialize_shacl", "serialize_shex", "serialize_shexje",
]
