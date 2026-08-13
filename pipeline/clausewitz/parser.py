"""Recursive-descent parser building the lossless Clausewitz AST from a token stream.

Grammar (informal):

    document   := (statement | COMMENT)* EOF
    statement  := key OPERATOR value            -- bare scalars are NOT valid at document root
    block      := '{' (statement | scalar | COMMENT)* '}'
    value      := scalar | block
    scalar     := IDENTIFIER | STRING | NUMBER | VARIABLE
    key        := IDENTIFIER | STRING | NUMBER

The one asymmetry — bare scalars valid inside a block but not at document root — is deliberate
and evidence-based: every real technology file is a sequence of `tech_id = { ... }` assignments
at the top level, never a loose scalar (see tests/fixtures/malformed/stray-token.txt, which
exists specifically to assert a root-level bare identifier is a parse error). Inside a block,
bare scalars are common and real (`category = { voidcraft }`, `prerequisites = { "x" y }`).

This parser does not resolve `@variable` references or expand `inline_script` — see
pipeline/clausewitz/nodes.py's module docstring.
"""

from __future__ import annotations

from .errors import ClausewitzError
from .nodes import (
    Assignment,
    Block,
    Comment,
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
        # Stack of LBRACE tokens for currently-open blocks, used to report every unclosed
        # block (not just the innermost) if EOF arrives before they're all closed.
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
        items = self._parse_items(in_block=False)
        return Document(items=items, path=self._path)

    # -- shared block/document body parsing ----------------------------------------------------

    def _parse_items(self, in_block: bool) -> list:
        items = []
        while True:
            tok = self._peek()

            if tok.type is TokenType.EOF:
                if in_block:
                    raise self._unclosed_block_error()
                return items

            if tok.type is TokenType.RBRACE:
                if in_block:
                    self._advance()
                    self._open_stack.pop()
                    return items
                raise self._error("unexpected '}' with no matching '{'", tok)

            if tok.type is TokenType.COMMENT:
                self._advance()
                items.append(Comment(text=tok.text, line=tok.line, column=tok.column))
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

            if not in_block:
                raise self._error(
                    f"expected '=' (or a comparison operator) after {key_tok.text!r}, "
                    f"found {next_tok.text!r} — a bare value is not valid at document root",
                    key_tok,
                )

            items.append(self._token_to_scalar_node(key_tok))

        # unreachable

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
            block_items = self._parse_items(in_block=True)
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
            return ParameterReference(name=tok.text, line=tok.line, column=tok.column)
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
