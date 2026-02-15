"""Parse ShExC compact syntax files into ShEx model.

Custom parser for the YAGO subset of ShExC, since pyshexc doesn't support
Python 3.14. Handles: PREFIX, start, shape declarations with EXTRA/CLOSED,
triple constraints with cardinality, node constraints (datatypes, IRI,
value sets, IRI stems), and shape references.
"""
from __future__ import annotations

import re
from typing import Optional, Union

from shaclex_py.schema.common import IRI, UNBOUNDED, Cardinality, IriStem, Literal, NodeKind, Prefix
from shaclex_py.schema.shex import (
    EachOf,
    NodeConstraint,
    Shape,
    ShapeRef,
    ShExSchema,
    TripleConstraint,
    ValueSetValue,
)


class ShExParseError(Exception):
    pass


class ShExCTokenizer:
    """Simple tokenizer for ShExC format."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def _skip_ws_and_comments(self):
        while self.pos < len(self.text):
            if self.text[self.pos] in ' \t\n\r':
                self.pos += 1
            elif self.text[self.pos] == '#':
                # Skip to end of line
                while self.pos < len(self.text) and self.text[self.pos] != '\n':
                    self.pos += 1
            else:
                break

    def peek(self) -> Optional[str]:
        self._skip_ws_and_comments()
        if self.pos >= len(self.text):
            return None
        return self.text[self.pos]

    def at_end(self) -> bool:
        self._skip_ws_and_comments()
        return self.pos >= len(self.text)

    def expect(self, s: str):
        self._skip_ws_and_comments()
        if not self.text[self.pos:].startswith(s):
            context = self.text[max(0, self.pos - 20):self.pos + 30]
            raise ShExParseError(
                f"Expected {s!r} at pos {self.pos}, got: ...{context}..."
            )
        self.pos += len(s)

    def try_consume(self, s: str) -> bool:
        self._skip_ws_and_comments()
        if self.text[self.pos:].startswith(s):
            self.pos += len(s)
            return True
        return False

    def read_until(self, chars: str) -> str:
        self._skip_ws_and_comments()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in chars:
            self.pos += 1
        return self.text[start:self.pos]

    def read_iri_ref(self) -> str:
        """Read <...> IRI reference."""
        self._skip_ws_and_comments()
        if self.text[self.pos] != '<':
            raise ShExParseError(f"Expected '<' at pos {self.pos}")
        self.pos += 1
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] != '>':
            self.pos += 1
        iri = self.text[start:self.pos]
        self.pos += 1  # skip '>'
        return iri

    def read_prefixed_name(self, prefixes: dict[str, str]) -> str:
        """Read prefix:local and resolve to full IRI."""
        self._skip_ws_and_comments()
        # Match prefix:local
        m = re.match(r'([a-zA-Z_][\w.-]*)?:([\w.-]*)', self.text[self.pos:])
        if not m:
            raise ShExParseError(f"Expected prefixed name at pos {self.pos}")
        self.pos += m.end()
        prefix = m.group(1) or ''
        local = m.group(2) or ''
        if prefix not in prefixes:
            raise ShExParseError(f"Unknown prefix {prefix!r}")
        return prefixes[prefix] + local

    def read_iri_or_prefixed(self, prefixes: dict[str, str]) -> str:
        """Read either <IRI> or prefix:local."""
        self._skip_ws_and_comments()
        if self.text[self.pos] == '<':
            return self.read_iri_ref()
        return self.read_prefixed_name(prefixes)

    def read_keyword(self) -> Optional[str]:
        """Read an uppercase keyword like EXTRA, CLOSED, IRI, etc."""
        self._skip_ws_and_comments()
        m = re.match(r'[A-Z][A-Za-z_]*', self.text[self.pos:])
        if m:
            return m.group(0)
        return None

    def consume_keyword(self, kw: str):
        self._skip_ws_and_comments()
        if not self.text[self.pos:].startswith(kw):
            raise ShExParseError(f"Expected keyword {kw!r} at pos {self.pos}")
        # Make sure it's not a prefix of a longer word
        end = self.pos + len(kw)
        if end < len(self.text) and self.text[end].isalpha():
            raise ShExParseError(f"Expected keyword {kw!r} at pos {self.pos}")
        self.pos = end


def _parse_cardinality(tok: ShExCTokenizer) -> Cardinality:
    """Parse optional cardinality: ?, *, +, {m,n}, {m,}, {m}."""
    if tok.at_end():
        return Cardinality()

    c = tok.peek()
    if c == '?':
        tok.pos += 1
        return Cardinality(min=0, max=1)
    elif c == '*':
        tok.pos += 1
        return Cardinality(min=0, max=UNBOUNDED)
    elif c == '+':
        tok.pos += 1
        return Cardinality(min=1, max=UNBOUNDED)
    elif c == '{':
        tok.pos += 1
        tok._skip_ws_and_comments()
        # Read min
        m = re.match(r'(\d+)', tok.text[tok.pos:])
        if not m:
            raise ShExParseError(f"Expected number in cardinality at pos {tok.pos}")
        mn = int(m.group(1))
        tok.pos += m.end()
        tok._skip_ws_and_comments()
        if tok.text[tok.pos] == ',':
            tok.pos += 1
            tok._skip_ws_and_comments()
            m2 = re.match(r'(\d+)', tok.text[tok.pos:])
            if m2:
                mx = int(m2.group(1))
                tok.pos += m2.end()
            else:
                mx = UNBOUNDED
        else:
            mx = mn  # {n} means exactly n
        tok._skip_ws_and_comments()
        tok.expect('}')
        return Cardinality(min=mn, max=mx)
    return Cardinality()  # default


def _parse_value_set(
    tok: ShExCTokenizer, prefixes: dict[str, str]
) -> list[ValueSetValue]:
    """Parse a value set: [ v1 v2 ... ] or [ <iri>~ ]."""
    tok.expect('[')
    values = []
    while not tok.try_consume(']'):
        tok._skip_ws_and_comments()
        # Check for IRI stem: <iri>~ or prefix:local~
        pos_save = tok.pos
        try:
            iri = tok.read_iri_or_prefixed(prefixes)
            tok._skip_ws_and_comments()
            if tok.pos < len(tok.text) and tok.text[tok.pos] == '~':
                tok.pos += 1
                values.append(ValueSetValue(value=IriStem(stem=iri)))
            else:
                values.append(ValueSetValue(value=IRI(iri)))
        except ShExParseError:
            tok.pos = pos_save
            # Try reading a literal
            if tok.text[tok.pos] in '"\'':
                lit = _parse_literal(tok, prefixes)
                values.append(ValueSetValue(value=lit))
            else:
                raise
    return values


def _parse_literal(tok: ShExCTokenizer, prefixes: dict[str, str]) -> Literal:
    """Parse a literal value: "string"^^datatype or "string"@lang."""
    tok._skip_ws_and_comments()
    quote = tok.text[tok.pos]
    tok.pos += 1
    start = tok.pos
    while tok.pos < len(tok.text) and tok.text[tok.pos] != quote:
        if tok.text[tok.pos] == '\\':
            tok.pos += 1  # skip escaped char
        tok.pos += 1
    value = tok.text[start:tok.pos]
    tok.pos += 1  # skip closing quote

    datatype = None
    language = None
    tok._skip_ws_and_comments()
    if tok.pos < len(tok.text) and tok.text[tok.pos:tok.pos + 2] == '^^':
        tok.pos += 2
        dt_iri = tok.read_iri_or_prefixed(prefixes)
        datatype = IRI(dt_iri)
    elif tok.pos < len(tok.text) and tok.text[tok.pos] == '@':
        tok.pos += 1
        m = re.match(r'[a-zA-Z-]+', tok.text[tok.pos:])
        if m:
            language = m.group(0)
            tok.pos += m.end()

    return Literal(value=value, datatype=datatype, language=language)


def _parse_node_constraint(
    tok: ShExCTokenizer, prefixes: dict[str, str]
) -> Union[NodeConstraint, ShapeRef]:
    """Parse constraint after predicate: datatype, IRI, @<shape>, or [values]."""
    tok._skip_ws_and_comments()
    c = tok.peek()

    # Shape reference: @<ShapeName>
    if c == '@':
        tok.pos += 1
        shape_iri = tok.read_iri_ref()
        return ShapeRef(name=IRI(shape_iri))

    # Value set: [ ... ]
    if c == '[':
        values = _parse_value_set(tok, prefixes)
        return NodeConstraint(values=values)

    # Keyword: IRI, LITERAL, BNODE, NONLITERAL
    kw = tok.read_keyword()
    if kw in ('IRI', 'LITERAL', 'BNODE', 'NONLITERAL'):
        tok.consume_keyword(kw)
        nk_map = {
            'IRI': NodeKind.IRI,
            'LITERAL': NodeKind.LITERAL,
            'BNODE': NodeKind.BLANK_NODE,
            'NONLITERAL': NodeKind.BLANK_NODE_OR_IRI,
        }
        return NodeConstraint(node_kind=nk_map[kw])

    # Dot (wildcard / no constraint)
    if c == '.':
        tok.pos += 1
        return NodeConstraint()

    # Datatype: prefix:local or <iri>
    iri = tok.read_iri_or_prefixed(prefixes)
    return NodeConstraint(datatype=IRI(iri))


def _parse_triple_constraint(
    tok: ShExCTokenizer, prefixes: dict[str, str]
) -> TripleConstraint:
    """Parse a single triple constraint line."""
    # Predicate
    pred_iri = tok.read_iri_or_prefixed(prefixes)

    # Constraint (optional)
    tok._skip_ws_and_comments()
    c = tok.peek()
    constraint = None
    if c not in (';', '}', '?', '*', '+', '{', None):
        constraint = _parse_node_constraint(tok, prefixes)

    # Cardinality
    card = _parse_cardinality(tok)

    return TripleConstraint(
        predicate=IRI(pred_iri),
        constraint=constraint,
        cardinality=card,
    )


def parse_shex(source: str) -> ShExSchema:
    """Parse a ShExC string or file path into ShExSchema.

    Args:
        source: File path or ShExC string.

    Returns:
        ShExSchema with parsed shapes and prefixes.
    """
    # Try to read as file
    try:
        with open(source, 'r', encoding='utf-8') as f:
            text = f.read()
    except (FileNotFoundError, OSError):
        text = source

    tok = ShExCTokenizer(text)
    prefixes_dict: dict[str, str] = {}
    prefix_list: list[Prefix] = []
    start: Optional[IRI] = None
    shapes: list[Shape] = []

    while not tok.at_end():
        tok._skip_ws_and_comments()
        if tok.at_end():
            break

        # Peek at what's next
        remaining = tok.text[tok.pos:]

        # PREFIX
        if remaining.startswith('PREFIX'):
            tok.consume_keyword('PREFIX')
            tok._skip_ws_and_comments()
            m = re.match(r'([a-zA-Z_][\w.-]*)?:', tok.text[tok.pos:])
            if not m:
                raise ShExParseError(f"Expected prefix name at pos {tok.pos}")
            pname = m.group(1) or ''
            tok.pos += m.end()
            tok._skip_ws_and_comments()
            piri = tok.read_iri_ref()
            prefixes_dict[pname] = piri
            prefix_list.append(Prefix(name=pname, iri=piri))
            continue

        # start = @<Shape>
        if remaining.startswith('start') and not remaining[5:6].isalpha():
            tok.pos += 5
            tok._skip_ws_and_comments()
            tok.expect('=')
            tok._skip_ws_and_comments()
            tok.expect('@')
            start_iri = tok.read_iri_ref()
            start = IRI(start_iri)
            continue

        # Shape definition: <Name> EXTRA/CLOSED? { ... }
        if tok.peek() == '<':
            shape_iri = tok.read_iri_ref()
            tok._skip_ws_and_comments()

            # EXTRA and CLOSED
            extra_preds: list[IRI] = []
            closed = False
            while True:
                r = tok.text[tok.pos:]
                if r.startswith('EXTRA') and not r[5:6].isalpha():
                    tok.pos += 5
                    # Read predicates until { or CLOSED
                    while tok.peek() not in ('{', None):
                        r2 = tok.text[tok.pos:]
                        if r2.startswith('CLOSED') or r2.startswith('EXTRA'):
                            break
                        pred = tok.read_iri_or_prefixed(prefixes_dict)
                        extra_preds.append(IRI(pred))
                    continue
                elif r.startswith('CLOSED') and not r[6:7].isalpha():
                    tok.pos += 6
                    closed = True
                    continue
                else:
                    break

            tok.expect('{')

            # Parse triple constraints
            constraints: list[TripleConstraint] = []
            while not tok.try_consume('}'):
                tok._skip_ws_and_comments()
                if tok.peek() == '}':
                    continue
                tc = _parse_triple_constraint(tok, prefixes_dict)
                constraints.append(tc)
                tok._skip_ws_and_comments()
                tok.try_consume(';')  # optional semicolon separator
                tok.try_consume('.')  # tolerate stray periods (data errors)

            expr = None
            if len(constraints) == 1:
                expr = constraints[0]
            elif len(constraints) > 1:
                expr = EachOf(expressions=constraints)

            shapes.append(Shape(
                name=IRI(shape_iri),
                expression=expr,
                closed=closed,
                extra=extra_preds,
            ))
            continue

        raise ShExParseError(
            f"Unexpected token at pos {tok.pos}: {tok.text[tok.pos:tok.pos+20]!r}"
        )

    return ShExSchema(shapes=shapes, prefixes=prefix_list, start=start)


def parse_shex_file(filepath: str) -> ShExSchema:
    """Parse a ShEx file from a file path."""
    return parse_shex(filepath)
