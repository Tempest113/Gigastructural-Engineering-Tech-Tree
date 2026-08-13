"""Character-level tokeniser for Clausewitz script.

Scope and evidence: the token grammar below (identifier characters including `/`, the operator
set, number and string forms) was derived from what actually appears in
tests/fixtures/{gigastructures,stellaris,acot,aot}/ — see tests/fixtures/NOTES.md and
tests/clausewitz/test_fixtures.py's docstring for the specific evidence (e.g. unquoted
`inline_script` path values containing `/`; comparison operators `<`, `>`, `<=`, `>=` but never
`!=` in real data, though `!=` is still supported here since nothing rules it out). This does
NOT tokenise localisation YAML (`§`/`£`/`$VAR$` never appear in Clausewitz script fixtures).
"""

from __future__ import annotations

from .errors import ClausewitzError
from .tokens import Token, TokenType

_IDENTIFIER_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
# '/' - unquoted inline_script-style paths (e.g. technology/tech_weight_boni/x).
# ':' - scripted-value references (e.g. `value:storm_callers_councilor_tech_discovery_chance_multiplier`).
# '?' - the "safe scope" suffix (e.g. `space_owner? = { ... }`); only ever trailing, but
#       allowing it as a continuation char (not a start char) is sufficient and simplest.
# All three confirmed against real fixture content — see tests/fixtures/NOTES.md and this
# module's docstring.
_IDENTIFIER_CONT = _IDENTIFIER_START | set("0123456789/:?")
_DIGITS = set("0123456789")
_WHITESPACE = set(" \t\n")


class Tokenizer:
    def __init__(self, text: str, path: str):
        self._text = text
        self._path = path
        self._pos = 0
        self._line = 1
        self._column = 1
        self._length = len(text)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            token = self._next_token()
            tokens.append(token)
            if token.type is TokenType.EOF:
                return tokens

    # -- low-level cursor helpers -----------------------------------------------------------

    def _peek(self, offset: int = 0) -> str:
        i = self._pos + offset
        return self._text[i] if i < self._length else ""

    def _advance(self) -> str:
        ch = self._text[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1
        return ch

    def _at_end(self) -> bool:
        return self._pos >= self._length

    def _error(self, message: str, line: int | None = None, column: int | None = None) -> ClausewitzError:
        return ClausewitzError(message, self._path, line if line is not None else self._line, column if column is not None else self._column)

    # -- scanning -----------------------------------------------------------------------------

    def _skip_whitespace(self) -> None:
        while not self._at_end() and self._peek() in _WHITESPACE:
            self._advance()

    def _next_token(self) -> Token:
        self._skip_whitespace()
        if self._at_end():
            return Token(TokenType.EOF, "", self._line, self._column)

        start_line, start_column = self._line, self._column
        ch = self._peek()

        if ch == "#":
            return self._scan_comment(start_line, start_column)
        if ch == '"':
            return self._scan_string(start_line, start_column)
        if ch == "{":
            self._advance()
            return Token(TokenType.LBRACE, "{", start_line, start_column)
        if ch == "}":
            self._advance()
            return Token(TokenType.RBRACE, "}", start_line, start_column)
        if ch == "@":
            return self._scan_variable(start_line, start_column)
        if ch == "$":
            return self._scan_parameter(start_line, start_column)
        if ch in ("=", "<", ">", "!"):
            return self._scan_operator(start_line, start_column)
        if ch in _DIGITS or (ch == "-" and self._peek(1) in _DIGITS):
            return self._scan_number(start_line, start_column)
        if ch in _IDENTIFIER_START:
            return self._scan_identifier(start_line, start_column)

        raise self._error(f"unexpected character {ch!r}", start_line, start_column)

    def _scan_comment(self, line: int, column: int) -> Token:
        self._advance()  # consume '#'
        chars = []
        while not self._at_end() and self._peek() != "\n":
            chars.append(self._advance())
        return Token(TokenType.COMMENT, "".join(chars), line, column)

    def _scan_string(self, line: int, column: int) -> Token:
        # Strings CAN span multiple lines — confirmed in real content (e.g.
        # `BUILDING_SETS = "\n    industrial\n    ...\n"` and the `code = "..."`
        # embedded-script-as-string idiom in zzz_overwrites.txt; see
        # tests/fixtures/NOTES.md). Scan to the next unescaped '"' or EOF, never stopping at
        # '\n' — only EOF with no closing quote found is actually unterminated.
        #
        # Token.text carries the RAW content between the quotes (escapes left un-resolved);
        # the parser resolves \" and \\ when building StringLiteral.value. Only the escaped
        # quote is treated specially here, and only to avoid ending the string on it.
        self._advance()  # consume opening '"'
        chars = []
        while True:
            if self._at_end():
                raise self._error("unterminated string (no closing '\"' before end of file)", line, column)
            ch = self._advance()
            if ch == '"':
                break
            if ch == "\\" and self._peek() == '"':
                chars.append(ch)
                chars.append(self._advance())
            else:
                chars.append(ch)
        return Token(TokenType.STRING, "".join(chars), line, column)

    def _scan_variable(self, line: int, column: int) -> Token:
        self._advance()  # consume '@'
        if self._peek() not in _IDENTIFIER_START:
            raise self._error("'@' must be followed by a variable name", line, column)
        chars = []
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
        return Token(TokenType.VARIABLE, "".join(chars), line, column)

    def _scan_parameter(self, line: int, column: int) -> Token:
        self._advance()  # consume opening '$'
        if self._peek() not in _IDENTIFIER_START:
            raise self._error("'$' must be followed by a parameter name", line, column)
        chars = []
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
        if self._peek() != "$":
            raise self._error(f"unterminated parameter reference '${''.join(chars)}' (expected closing '$')", line, column)
        self._advance()  # consume closing '$'
        return Token(TokenType.PARAMETER, "".join(chars), line, column)

    def _scan_operator(self, line: int, column: int) -> Token:
        ch = self._advance()
        if ch == "!":
            if self._peek() == "=":
                self._advance()
                return Token(TokenType.OPERATOR, "!=", line, column)
            raise self._error("unexpected character '!' (did you mean '!='?)", line, column)
        if ch in ("<", ">") and self._peek() == "=":
            self._advance()
            return Token(TokenType.OPERATOR, ch + "=", line, column)
        return Token(TokenType.OPERATOR, ch, line, column)

    def _scan_number(self, line: int, column: int) -> Token:
        chars = []
        if self._peek() == "-":
            chars.append(self._advance())
        while not self._at_end() and self._peek() in _DIGITS:
            chars.append(self._advance())
        if self._peek() == "." and self._peek(1) in _DIGITS:
            chars.append(self._advance())  # '.'
            while not self._at_end() and self._peek() in _DIGITS:
                chars.append(self._advance())
        return Token(TokenType.NUMBER, "".join(chars), line, column)

    def _scan_identifier(self, line: int, column: int) -> Token:
        chars = []
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
        # A '.' immediately attached (no whitespace) to an identifier, followed by another
        # identifier-start char or a digit, chains one more identifier-shaped segment onto this
        # token — repeatable. Two confirmed real, common idioms share this exact shape:
        #   - event-id namespace.number, e.g. `id = bio.1`, `id = timeline.69`, chainable as
        #     `crisis.8060.1` (2,142 distinct namespace.number values across scripted_triggers/
        #     and ascension_perks/ in all four sources — every `country_event = { id = ... }`).
        #   - scope-chain references used as plain values, e.g. `is_same_species = root.owner`,
        #     chainable as `root.owner.overlord` (129 occurrences across the rescoped corpus,
        #     dominated by `from.owner`/`root.owner`; needed to parse ascension_perks/, which
        #     feeds P-3's gate identities).
        # Requiring an identifier-start char or digit immediately after the '.' (never
        # whitespace/EOF/punctuation) avoids swallowing an unrelated trailing '.' — e.g.
        # end-of-sentence punctuation that might otherwise leak out of a comment into a scan.
        while self._peek() == "." and (self._peek(1) in _IDENTIFIER_START or self._peek(1) in _DIGITS):
            chars.append(self._advance())  # '.'
            while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
                chars.append(self._advance())
        # A '@' immediately attached to the end of an identifier (no intervening whitespace) is
        # a scope suffix, not a scripted-variable reference — e.g. `has_star_flag =
        # ehof_system_created_by_@root`, `has_country_flag = marauder_tribute_6@event_target:x`.
        # Confirmed in real corpus content (scripted_triggers/, several sources); the flag name
        # and its scope are one inseparable token. A *leading* '@' (nothing consumed above) is
        # unaffected — that's still `_scan_variable`'s ordinary scripted-variable case, since
        # `_next_token` only reaches here when the first character was an identifier-start char.
        # Without this, the tokeniser silently splits the flag name and misreads the scope as an
        # unrelated top-level `@variable` reference instead of failing loudly — worse than an
        # honest parse error.
        if chars and self._peek() == "@" and self._peek(1) in _IDENTIFIER_START:
            chars.append(self._advance())  # '@'
            while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
                chars.append(self._advance())
        return Token(TokenType.IDENTIFIER, "".join(chars), line, column)
