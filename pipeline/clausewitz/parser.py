"""Recursive-descent parser building the lossless Clausewitz AST from a token stream.

Grammar (informal):

    document   := (statement | COMMENT)* EOF
    statement  := key OPERATOR value            -- bare scalars are NOT valid at document root
    block      := '{' (statement | scalar | COMMENT | conditional)* '}'
    conditional:= '[' '[' '!'? IDENTIFIER ']' (statement | scalar | COMMENT | conditional)* ']'
    value      := scalar | block
    scalar     := IDENTIFIER | STRING | NUMBER | VARIABLE
    key        := IDENTIFIER | STRING | NUMBER

The one asymmetry — bare scalars valid inside a block but not at document root — is deliberate
and evidence-based: every real technology file is a sequence of `tech_id = { ... }` assignments
at the top level, never a loose scalar (see tests/fixtures/malformed/stray-token.txt, which
exists specifically to assert a root-level bare identifier is a parse error). Inside a block,
bare scalars are common and real (`category = { voidcraft }`, `prerequisites = { "x" y }`).
`conditional` shares this same body grammar (and the same asymmetry — it's never valid at
document root, matching the fact that every real occurrence sits inside some `{ }` block).

This parser does not resolve `@variable` references or expand `inline_script` — see
pipeline/clausewitz/nodes.py's module docstring. It likewise doesn't evaluate a `conditional`
block's guard (whether the invocation supplied that parameter) — same deferred-resolution
principle, one later pass's job.
"""

from __future__ import annotations

from .errors import ClausewitzError
from .nodes import (
    Assignment,
    Block,
    Comment,
    ConditionalBlock,
    Document,
    Identifier,
    NumberLiteral,
    ParameterReference,
    StringLiteral,
    VariableReference,
)
from .tokenizer import Tokenizer
from .tokens import Token, TokenType

_COMPARISON_OPERATORS = {"=", "<", ">", "<=", ">=", "!="}
_KEY_TOKEN_TYPES = (TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER, TokenType.VARIABLE, TokenType.PARAMETER)
_SCALAR_TOKEN_TYPES = (TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER, TokenType.VARIABLE, TokenType.PARAMETER)


class Parser:
    def __init__(self, tokens: list[Token], path: str):
        self._tokens = tokens
        self._path = path
        self._pos = 0
        # Stack of opening-bracket tokens (LBRACE for `{ }` blocks, the first LBRACKET for
        # `[[...]` conditional blocks) for currently-open scopes, used to report every unclosed
        # one (not just the innermost) if EOF arrives before they're all closed.
        self._open_stack: list[Token] = []

    # -- token stream helpers -----------------------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        i = self._pos + offset
        if i < len(self._tokens):
            return self._tokens[i]
        return self._tokens[-1]  # EOF token

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.type is not TokenType.EOF:
            self._pos += 1
        return tok

    def _error(self, message: str, tok: Token) -> ClausewitzError:
        return ClausewitzError(message, self._path, tok.line, tok.column)

    # -- entry point --------------------------------------------------------------------------

    def parse_document(self) -> Document:
        items = self._parse_items(closing=None)
        return Document(items=items, path=self._path)

    # -- shared block/document/conditional-block body parsing -----------------------------------

    def _parse_items(self, closing: TokenType | None) -> list:
        """Parses a sequence of statements/scalars/comments/conditional-blocks, terminated by
        `closing` (TokenType.RBRACE for a `{ }` block, TokenType.RBRACKET for a `[[...]`
        conditional block's body) or by EOF at document root (`closing=None`). Bare scalars are
        valid whenever `closing is not None` — both block kinds share that asymmetry with
        document root; see this module's docstring."""
        items = []
        while True:
            tok = self._peek()

            if tok.type is TokenType.EOF:
                if closing is not None:
                    raise self._unclosed_block_error()
                return items

            if tok.type is closing:
                self._advance()
                self._open_stack.pop()
                return items

            if tok.type is TokenType.RBRACE and closing is not TokenType.RBRACE:
                raise self._error("unexpected '}' with no matching '{'", tok)

            if tok.type is TokenType.RBRACKET and closing is not TokenType.RBRACKET:
                raise self._error("unexpected ']' with no matching '[['", tok)

            if tok.type is TokenType.COMMENT:
                self._advance()
                items.append(Comment(text=tok.text, line=tok.line, column=tok.column))
                continue

            if tok.type is TokenType.LBRACKET:
                if closing is None:
                    raise self._error("a conditional '[[...]' block is not valid at document root", tok)
                items.append(self._parse_conditional_block())
                continue

            if tok.type not in _KEY_TOKEN_TYPES:
                raise self._error(f"unexpected token {tok.text!r}", tok)

            key_tok = self._advance()
            next_tok = self._peek()

            if next_tok.type is TokenType.OPERATOR and next_tok.text in _COMPARISON_OPERATORS:
                operator_tok = self._advance()
                value = self._parse_value()
                items.append(
                    Assignment(
                        key=self._token_to_key_node(key_tok),
                        operator=operator_tok.text,
                        value=value,
                        line=key_tok.line,
                        column=key_tok.column,
                    )
                )
                continue

            if closing is None:
                raise self._error(
                    f"expected '=' (or a comparison operator) after {key_tok.text!r}, "
                    f"found {next_tok.text!r} — a bare value is not valid at document root",
                    key_tok,
                )

            items.append(self._token_to_scalar_node(key_tok))

        # unreachable

    def _parse_conditional_block(self) -> ConditionalBlock:
        """`[[GUARD]` (or `[[!GUARD]`) ... `]` — see nodes.ConditionalBlock. Two distinct single
        `]` tokens are involved: one closes the guard header (consumed directly here), the other
        closes the body (consumed by the `_parse_items(closing=RBRACKET)` call, symmetric with
        how `_parse_value`'s LBRACE branch lets `_parse_items(closing=RBRACE)` consume a
        block's own closing `}`)."""
        first_bracket = self._advance()  # first '['
        second = self._peek()
        if second.type is not TokenType.LBRACKET:
            raise self._error("expected a second '[' to open a conditional '[[...]' block", second)
        self._advance()  # second '['

        negated = False
        guard_tok = self._peek()
        if guard_tok.type is TokenType.OPERATOR and guard_tok.text == "!":
            self._advance()
            negated = True
            guard_tok = self._peek()

        if guard_tok.type is not TokenType.IDENTIFIER:
            raise self._error(
                f"expected a guard name after '[[' (or '[[!'), found {guard_tok.text!r}", guard_tok
            )
        self._advance()

        close_tok = self._peek()
        if close_tok.type is not TokenType.RBRACKET:
            raise self._error(
                f"expected ']' to close the '[[{guard_tok.text}]' guard header, found {close_tok.text!r}",
                close_tok,
            )
        self._advance()  # the guard header's own closing ']' — not the body's

        self._open_stack.append(first_bracket)
        body_items = self._parse_items(closing=TokenType.RBRACKET)
        return ConditionalBlock(
            guard=guard_tok.text, negated=negated, items=body_items, line=first_bracket.line, column=first_bracket.column
        )

    def _unclosed_block_error(self) -> ClausewitzError:
        assert self._open_stack, "unclosed_block_error called with nothing open"
        outermost = self._open_stack[0]
        lines = ", ".join(str(t.line) for t in self._open_stack)
        message = (
            f"unexpected end of file: {len(self._open_stack)} block(s) never closed "
            f"(opened at line(s) {lines}, counting outermost first)"
        )
        return ClausewitzError(message, self._path, outermost.line, outermost.column)

    def _parse_value(self):
        tok = self._peek()
        if tok.type is TokenType.LBRACE:
            open_tok = self._advance()
            self._open_stack.append(open_tok)
            block_items = self._parse_items(closing=TokenType.RBRACE)
            return Block(items=block_items, line=open_tok.line, column=open_tok.column)
        if tok.type in _SCALAR_TOKEN_TYPES:
            self._advance()
            return self._token_to_scalar_node(tok)
        raise self._error(f"expected a value, found {tok.text!r}", tok)

    # -- token -> node conversion --------------------------------------------------------------

    @staticmethod
    def _token_to_key_node(tok: Token):
        return Parser._token_to_scalar_node(tok)

    @staticmethod
    def _token_to_scalar_node(tok: Token):
        if tok.type is TokenType.IDENTIFIER:
            return Identifier(name=tok.text, line=tok.line, column=tok.column)
        if tok.type is TokenType.STRING:
            return Parser._string_node(tok)
        if tok.type is TokenType.NUMBER:
            return Parser._number_node(tok)
        if tok.type is TokenType.VARIABLE:
            return VariableReference(name=tok.text, line=tok.line, column=tok.column)
        if tok.type is TokenType.PARAMETER:
            return ParameterReference(name=tok.text, line=tok.line, column=tok.column, default=tok.default, safe=tok.safe)
        raise AssertionError(f"not a valid key/scalar token type: {tok.type}")

    @staticmethod
    def _string_node(tok: Token) -> StringLiteral:
        resolved = tok.text.replace('\\"', '"')
        return StringLiteral(value=resolved, raw=tok.text, line=tok.line, column=tok.column)

    @staticmethod
    def _number_node(tok: Token) -> NumberLiteral:
        value = float(tok.text) if "." in tok.text else int(tok.text)
        return NumberLiteral(value=value, raw=tok.text, line=tok.line, column=tok.column)


def parse_tokens(tokens: list[Token], path: str) -> Document:
    return Parser(tokens, path).parse_document()


def tokenize_text(text: str, path: str) -> list[Token]:
    return Tokenizer(text, path).tokenize()
