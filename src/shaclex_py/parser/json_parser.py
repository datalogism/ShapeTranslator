"""Parse canonical JSON into CanonicalSchema."""
from __future__ import annotations

import json
from typing import Union

from shaclex_py.schema.canonical import (
    CanonicalCardinality,
    CanonicalProperty,
    CanonicalSchema,
    CanonicalShape,
)


def _parse_property(d: dict) -> CanonicalProperty:
    """Parse a single property dict into a CanonicalProperty."""
    card_d = d.get("cardinality", {"min": 0, "max": -1})
    cardinality = CanonicalCardinality(min=card_d["min"], max=card_d["max"])

    prop = CanonicalProperty(path=d["path"], cardinality=cardinality)

    if "datatype" in d:
        prop.datatype = d["datatype"]
    elif "classRef" in d:
        prop.classRef = d["classRef"]
    elif "classRefOr" in d:
        prop.classRefOr = d["classRefOr"]
    elif "nodeKind" in d:
        prop.nodeKind = d["nodeKind"]
    elif "hasValue" in d:
        prop.hasValue = d["hasValue"]
    elif "inValues" in d:
        prop.inValues = d["inValues"]
    elif "iriStem" in d:
        prop.iriStem = d["iriStem"]
    elif "pattern" in d:
        prop.pattern = d["pattern"]
    elif "nodeRef" in d:
        prop.nodeRef = d["nodeRef"]

    return prop


def parse_canonical(source: str) -> CanonicalSchema:
    """Parse a canonical JSON string or file path into CanonicalSchema.

    Args:
        source: JSON string or file path.

    Returns:
        CanonicalSchema with parsed shapes.
    """
    try:
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, OSError):
        data = json.loads(source)

    shapes = []
    for shape_d in data.get("shapes", []):
        properties = [_parse_property(p) for p in shape_d.get("properties", [])]
        shapes.append(CanonicalShape(
            name=shape_d["name"],
            targetClass=shape_d.get("targetClass"),
            closed=shape_d.get("closed", False),
            properties=properties,
        ))

    return CanonicalSchema(shapes=shapes)


def parse_canonical_file(filepath: str) -> CanonicalSchema:
    """Parse a canonical JSON file from a file path."""
    return parse_canonical(filepath)
