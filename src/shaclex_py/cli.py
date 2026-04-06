"""SHACL <-> ShEx <-> ShexJE Translator -- CLI entry point.

Usage:
    shaclex-py --input FILE --direction DIRECTION [--output FILE]
    shaclex-py --input-dir DIR --output-dir DIR --direction DIRECTION
    shaclex-py --batch   # Run full YAGO batch in both directions

Directions:
    shacl2shex      SHACL (Turtle) → ShEx (ShExC)
    shex2shacl      ShEx  (ShExC)  → SHACL (Turtle)
    shacl2shexje    SHACL (Turtle) → ShexJE JSON
    shex2shexje     ShEx  (ShExC)  → ShexJE JSON
    shexje2shacl    ShexJE JSON    → SHACL (Turtle)
    shexje2shex     ShexJE JSON    → ShEx (ShExC)

ShexJE is the canonical intermediate format.  Every SHACL ↔ ShEx conversion
passes through ShexJE internally.
"""
from __future__ import annotations

import argparse
import os
import sys


def _maybe_fetch_labels(schema, direction: str, wikidata_labels: bool) -> dict:
    """Fetch Wikidata labels when ``--wikidata-labels`` is set and the output
    is ShEx.  Returns an empty dict otherwise (labels disabled by default).

    Only targets ShEx-producing directions: ``shacl2shex``.
    The label map is built lazily from the already-parsed schema so we make
    exactly one SPARQL round-trip per file.
    """
    if not wikidata_labels:
        return {}
    if direction != "shacl2shex":
        return {}
    try:
        from shaclex_py.utils.wikidata import (
            collect_iris_from_shacl,
            fetch_labels,
        )
        from shaclex_py.schema.shacl import SHACLSchema

        if isinstance(schema, SHACLSchema):
            iris = collect_iris_from_shacl(schema)
        else:
            iris = []

        if not iris:
            return {}
        print(f"  [wikidata-labels] fetching labels for {len(iris)} IRIs …",
              flush=True)
        return fetch_labels(iris)
    except Exception as exc:
        print(f"  [wikidata-labels] WARNING: label fetch failed: {exc}",
              flush=True)
        return {}


def convert_file(
    input_path: str,
    direction: str,
    output_path: str | None = None,
    wikidata_labels: bool = False,
) -> str:
    """Convert a single file.

    Args:
        input_path:       Path to input file.
        direction:        Conversion direction.
        output_path:      Optional output file path. If None, prints to stdout.
        wikidata_labels:  When True and direction produces ShEx, fetch English
                          labels from the Wikidata SPARQL endpoint and use them
                          for ``@<ShapeName>`` references and inline comments.
                          Disabled by default.

    Returns:
        The converted output string.
    """
    if direction == "shacl2shex":
        from shaclex_py.parser.shacl_parser import parse_shacl_file
        from shaclex_py.converter.shacl_to_shex import convert_shacl_to_shex
        from shaclex_py.serializer.shex_serializer import serialize_shex

        shacl = parse_shacl_file(input_path)
        label_map = _maybe_fetch_labels(shacl, direction, wikidata_labels)
        shex = convert_shacl_to_shex(shacl, label_map=label_map or None)
        result = serialize_shex(shex, label_map=label_map or None)
    elif direction == "shex2shacl":
        from shaclex_py.parser.shex_parser import parse_shex_file
        from shaclex_py.converter.shex_to_shacl import convert_shex_to_shacl
        from shaclex_py.serializer.shacl_serializer import serialize_shacl

        shex = parse_shex_file(input_path)
        shacl = convert_shex_to_shacl(shex)
        result = serialize_shacl(shacl)
    elif direction == "shacl2shexje":
        from shaclex_py.parser.shacl_parser import parse_shacl_file
        from shaclex_py.converter.shacl_to_shexje import convert_shacl_to_shexje
        from shaclex_py.serializer.shexje_serializer import serialize_shexje

        shacl = parse_shacl_file(input_path)
        shexje = convert_shacl_to_shexje(shacl)
        result = serialize_shexje(shexje)
    elif direction == "shex2shexje":
        from shaclex_py.parser.shex_parser import parse_shex_file
        from shaclex_py.converter.shex_to_shexje import convert_shex_to_shexje
        from shaclex_py.serializer.shexje_serializer import serialize_shexje

        shex = parse_shex_file(input_path)
        shexje = convert_shex_to_shexje(shex)
        result = serialize_shexje(shexje)
    elif direction == "shexje2shacl":
        from shaclex_py.parser.shexje_parser import parse_shexje_file
        from shaclex_py.converter.shexje_to_shacl import convert_shexje_to_shacl
        from shaclex_py.serializer.shacl_serializer import serialize_shacl

        shexje = parse_shexje_file(input_path)
        shacl = convert_shexje_to_shacl(shexje)
        result = serialize_shacl(shacl)
    elif direction == "shexje2shex":
        from shaclex_py.parser.shexje_parser import parse_shexje_file
        from shaclex_py.converter.shexje_to_shex import convert_shexje_to_shex
        from shaclex_py.serializer.shex_serializer import serialize_shex

        shexje = parse_shexje_file(input_path)
        shex = convert_shexje_to_shex(shexje)
        result = serialize_shex(shex)
    else:
        raise ValueError(f"Unknown direction: {direction!r}")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

    return result


def convert_batch(
    input_dir: str,
    output_dir: str,
    direction: str,
    wikidata_labels: bool = False,
) -> tuple[int, int]:
    """Convert all files in a directory.

    Returns:
        (success_count, failure_count)
    """
    os.makedirs(output_dir, exist_ok=True)

    ext_map = {
        "shacl2shex":   (".ttl",    ".shex"),
        "shex2shacl":   (".shex",   ".ttl"),
        "shacl2shexje": (".ttl",    ".shexje"),
        "shex2shexje":  (".shex",   ".shexje"),
        "shexje2shacl": (".shexje", ".ttl"),
        "shexje2shex":  (".shexje", ".shex"),
    }
    ext_in, ext_out = ext_map[direction]

    ok = 0
    fail = 0
    warnings: list[str] = []

    for filename in sorted(os.listdir(input_dir)):
        if not filename.endswith(ext_in):
            continue

        input_path = os.path.join(input_dir, filename)
        output_name = filename.replace(ext_in, ext_out)
        output_path = os.path.join(output_dir, output_name)

        try:
            convert_file(input_path, direction, output_path,
                         wikidata_labels=wikidata_labels)
            print(f"  OK  {filename} -> {output_name}")
            ok += 1
        except Exception as e:
            print(f"  FAIL {filename}: {e}")
            warnings.append(f"{filename}: {e}")
            fail += 1

    return ok, fail


def run_yago_batch():
    """Run full YAGO dataset conversion in both directions."""
    print("=" * 60)
    print("SHACL -> ShEx (dataset/shacl_yago -> shacl_to_shex)")
    print("=" * 60)
    ok1, fail1 = convert_batch("dataset/shacl_yago", "shacl_to_shex", "shacl2shex")
    print(f"\nResult: {ok1} converted, {fail1} failed\n")

    print("=" * 60)
    print("ShEx -> SHACL (dataset/shex_yago -> shex_to_shacl)")
    print("=" * 60)
    ok2, fail2 = convert_batch("dataset/shex_yago", "shex_to_shacl", "shex2shacl")
    print(f"\nResult: {ok2} converted, {fail2} failed\n")

    print("=" * 60)
    print(f"TOTAL: {ok1 + ok2} converted, {fail1 + fail2} failed")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="SHACL <-> ShEx Translator (ShexJE canonical format)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--input", "-i",
        help="Input file path",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--direction", "-d",
        choices=[
            "shacl2shex", "shex2shacl",
            "shacl2shexje", "shex2shexje", "shexje2shacl", "shexje2shex",
        ],
        help="Conversion direction",
    )
    parser.add_argument(
        "--input-dir",
        help="Input directory for batch conversion",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for batch conversion",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run full YAGO batch conversion in both directions",
    )
    parser.add_argument(
        "--wikidata-labels",
        action="store_true",
        default=False,
        help=(
            "Fetch English labels from the Wikidata SPARQL endpoint and use "
            "them for @<ShapeName> references and inline comments in ShEx "
            "output.  Only applies to shacl2shex direction. "
            "Disabled by default."
        ),
    )

    args = parser.parse_args()

    if args.batch:
        run_yago_batch()
        return

    wikidata_labels = getattr(args, "wikidata_labels", False)

    if args.input_dir and args.output_dir and args.direction:
        ok, fail = convert_batch(
            args.input_dir, args.output_dir, args.direction,
            wikidata_labels=wikidata_labels,
        )
        print(f"\nConverted {ok} files, {fail} failed")
        return

    if args.input and args.direction:
        result = convert_file(
            args.input, args.direction, args.output,
            wikidata_labels=wikidata_labels,
        )
        if not args.output:
            print(result)
        return

    parser.print_help()
    sys.exit(1)
