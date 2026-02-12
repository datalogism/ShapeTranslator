"""SHACL <-> ShEx Translator — CLI entry point.

Usage:
    python main.py --input FILE --direction shacl2shex|shex2shacl [--output FILE]
    python main.py --input-dir DIR --output-dir DIR --direction shacl2shex|shex2shacl
    python main.py --batch   # Run full YAGO batch in both directions
"""
from __future__ import annotations

import argparse
import os
import sys


def convert_file(input_path: str, direction: str, output_path: str | None = None) -> str:
    """Convert a single file.

    Args:
        input_path: Path to input file.
        direction: 'shacl2shex' or 'shex2shacl'.
        output_path: Optional output file path. If None, prints to stdout.

    Returns:
        The converted output string.
    """
    if direction == "shacl2shex":
        from parsers.shacl_parser import parse_shacl_file
        from converters.shacl_to_shex import convert_shacl_to_shex
        from serializers.shex_serializer import serialize_shex

        shacl = parse_shacl_file(input_path)
        shex = convert_shacl_to_shex(shacl)
        result = serialize_shex(shex)
    elif direction == "shex2shacl":
        from parsers.shex_parser import parse_shex_file
        from converters.shex_to_shacl import convert_shex_to_shacl
        from serializers.shacl_serializer import serialize_shacl

        shex = parse_shex_file(input_path)
        shacl = convert_shex_to_shacl(shex)
        result = serialize_shacl(shacl)
    else:
        raise ValueError(f"Unknown direction: {direction!r}")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

    return result


def convert_batch(input_dir: str, output_dir: str, direction: str) -> tuple[int, int]:
    """Convert all files in a directory.

    Returns:
        (success_count, failure_count)
    """
    os.makedirs(output_dir, exist_ok=True)

    if direction == "shacl2shex":
        ext_in, ext_out = ".ttl", ".shex"
    else:
        ext_in, ext_out = ".shex", ".ttl"

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
            convert_file(input_path, direction, output_path)
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
        description="SHACL <-> ShEx Translator",
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
        choices=["shacl2shex", "shex2shacl"],
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

    args = parser.parse_args()

    if args.batch:
        run_yago_batch()
        return

    if args.input_dir and args.output_dir and args.direction:
        ok, fail = convert_batch(args.input_dir, args.output_dir, args.direction)
        print(f"\nConverted {ok} files, {fail} failed")
        return

    if args.input and args.direction:
        result = convert_file(args.input, args.direction, args.output)
        if not args.output:
            print(result)
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
