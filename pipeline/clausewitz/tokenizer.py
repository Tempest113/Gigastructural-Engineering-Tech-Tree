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
        if ch == "[":
            self._advance()
            return Token(TokenType.LBRACKET, "[", start_line, start_column)
        if ch == "]":
            self._advance()
            return Token(TokenType.RBRACKET, "]", start_line, start_column)
        if ch == "@":
            if self._peek(1) == "[":
                return self._scan_arithmetic_expression(start_line, start_column)
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

    def _has_attached_continuation(self) -> bool:
        """True if the character right under the cursor starts one of the "attached, no
        whitespace" continuation shapes handled by `_consume_attached_continuations` — used by
        `_scan_variable`/`_scan_parameter` to decide whether their token stays a distinct
        VARIABLE/PARAMETER node (the ordinary, overwhelmingly common case) or gets flattened
        into opaque identifier-shaped text together with the attached continuation (see
        `_consume_attached_continuations`'s docstring for why flattening is safe there)."""
        if self._peek() in _IDENTIFIER_CONT:
            return True
        if self._peek() == "." and (self._peek(1) in _IDENTIFIER_START or self._peek(1) in _DIGITS):
            return True
        if self._peek() == "@" and (self._peek(1) in _IDENTIFIER_START or self._peek(1) == "$"):
            return True
        if self._peek() in ("|", "$"):
            return True
        return False

    def _consume_attached_continuations(self, chars: list[str]) -> None:
        """Extends `chars` in place with every "attached, no intervening whitespace" suffix
        following it — repeatable, since they compose (e.g. mid-token substitution like
        `planet_$JOB$_$RESOURCE$` chains plain text and two separate `$PARAM$` spans; a
        '@'-suffix whose scope is itself a dotted chain chains those two). Four shapes, all
        confirmed real, all sharing one governing idea: a scope suffix, dotted chain,
        pipe-parameterised call, or bare mid-token `$PARAM$` substitution can attach directly to
        *any* reference-shaped token — a plain identifier, a `$parameter$` reference, or an
        `@variable` reference — not just plain identifier text on both sides. The whole compound
        is flattened into one opaque identifier-shaped token rather than decomposed into
        structured sub-nodes: no current or near-term pass needs to walk into an attached
        `$PARAM$`/`@variable` span to find it — inline_script's own `$PARAM$` substitution runs
        as text substitution on raw source before parsing (see inline_scripts.py), so it finds
        e.g. `$OWNER$` the same way regardless of how the parsed AST represents it, and an
        attached `@name` is never a genuine scripted-variable reference in the first place (a
        real one is always unattached — see the '@'-suffix case below). Same "opaque when
        embedded" precedent as a quoted string whose contents happen to look like script.

        - Plain identifier-continuation characters: resumes ordinary identifier text after any
          of the special spans below (e.g. the `_cap` in `giga_tech_repeatable_$name$_cap`, or
          the second `_$RESOURCE$` in `planet_$JOB$_$RESOURCE$`) — without this, a compound with
          a `$PARAM$`/`.`/`@`/`|` span in the *middle* rather than at the end would stop short.
        - Bare '$': a `$PARAM$` reference embedded directly in running identifier text, no
          connecting sigil — e.g. `has_global_flag = crisis_stage_$STAGE|1$`,
          `planet_$JOB$_$RESOURCE$`. Confirmed real and common across scripted_triggers/ in all
          four sources — this is the same mid-token substitution idiom already documented for
          `inline_script` target files (`giga_tech_repeatable_$name$_cap`), just occurring in a
          file parsed directly rather than reached through inline_script's own text
          substitution. Without this, `crisis_stage_` and the following `$STAGE|1$` silently
          became two disconnected top-level items instead of one value — a real, previously
          undetected data-corrupting bug, not merely a parse failure.
        - '.' + (identifier-start char | digit): chains one more identifier-shaped segment,
          repeatable. Two idioms share this shape: event-id namespace.number (`id = bio.1`,
          chainable as `crisis.8060.1` — 2,142 distinct values across scripted_triggers/ and
          ascension_perks/ in all four sources) and scope-chain values (`is_same_species =
          root.owner`, chainable as `root.owner.overlord`, also as a `$parameter$` reference's
          scope, e.g. `$TARGET$.trigger:empire_size` — needed to parse ascension_perks/, which
          feeds P-3's gate identities).
        - '@' + (identifier-start char | '$'): a scope suffix, not a scripted-variable
          reference — e.g. `has_star_flag = ehof_system_created_by_@root`, or
          `broken_shackles_parent_of@$SCOPE$` where the scope is itself a parameter. The flag
          name and its scope are one inseparable token; splitting them (as a leading, unattached
          '@' correctly does) previously misread the scope as an unrelated top-level `@variable`
          reference instead of failing loudly.
        - '|' + segment, repeatable, segment optionally a full `$PARAM$`/`@variable`-shaped span
          rather than plain identifier text: the parameterised scripted-value call idiom,
          `value:name|KEY|value|KEY2|value2|` (confirmed real, common/scripted_triggers/ in all
          four sources), including cases where a value segment is itself a live parameter
          reference (`value:x|OWNER|$OWNER$|`).
        """
        while True:
            progressed = False
            while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
                chars.append(self._advance())
                progressed = True
            if self._peek() == "." and (self._peek(1) in _IDENTIFIER_START or self._peek(1) in _DIGITS):
                chars.append(self._advance())  # '.'
                progressed = True
                continue
            if self._peek() == "@" and (self._peek(1) in _IDENTIFIER_START or self._peek(1) == "$"):
                chars.append(self._advance())  # '@'
                if self._peek() == "$":
                    self._consume_dollar_span(chars)
                progressed = True
                continue
            if self._peek() == "|":
                chars.append(self._advance())  # '|'
                if self._peek() == "$":
                    self._consume_dollar_span(chars)
                elif self._peek() == "@":
                    chars.append(self._advance())
                progressed = True
                continue
            if self._peek() == "$":
                self._consume_dollar_span(chars)
                progressed = True
                continue
            if not progressed:
                break

    def _consume_dollar_span(self, chars: list[str]) -> None:
        """Appends a `$...$` span (delimiters included) verbatim to `chars`, for when a
        `$PARAM$` reference is embedded mid-compound rather than standing alone."""
        chars.append(self._advance())  # opening '$'
        while not self._at_end() and self._peek() != "$":
            chars.append(self._advance())
        if self._peek() == "$":
            chars.append(self._advance())  # closing '$'

    def _scan_arithmetic_expression(self, line: int, column: int) -> Token:
        """`@[ expression ]` — an inline arithmetic expression, evaluated (by the game engine,
        or by whatever textually substitutes `$param$` references inside it first) to a number.
        Confirmed real: `generic_parts/giga_toggled_code.txt`'s `value = @[ (-1 * (...)) ]`,
        computing a 0/1 selector from a `$toggle$` parameter. Distinct from `_scan_variable`'s
        ordinary `@name` case — dispatched separately in `_next_token` before reaching it, since
        `[` is never a valid variable-name start character.

        Scanned as one opaque token, bracket-depth-aware (so a nested `[`/`]` inside the
        expression, if one ever appears, doesn't close it early) — same "opaque when embedded"
        treatment as the other attached-continuation shapes: nothing currently needs to walk
        into this expression structurally, only preserve it losslessly."""
        chars = [self._advance(), self._advance()]  # '@', '['
        depth = 1
        while depth > 0:
            if self._at_end():
                raise self._error("unterminated arithmetic expression (no matching ']' for '@[')", line, column)
            ch = self._advance()
            chars.append(ch)
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
        return Token(TokenType.IDENTIFIER, "".join(chars), line, column)

    def _scan_variable(self, line: int, column: int) -> Token:
        self._advance()  # consume '@'
        if self._peek() not in _IDENTIFIER_START:
            raise self._error("'@' must be followed by a variable name", line, column)
        chars = []
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
        if self._has_attached_continuation():
            flattened = ["@", *chars]
            self._consume_attached_continuations(flattened)
            return Token(TokenType.IDENTIFIER, "".join(flattened), line, column)
        return Token(TokenType.VARIABLE, "".join(chars), line, column)

    def _scan_parameter(self, line: int, column: int) -> Token:
        self._advance()  # consume opening '$'
        if self._peek() not in _IDENTIFIER_START:
            raise self._error("'$' must be followed by a parameter name", line, column)
        chars = []
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
        # `$NAME|default$` — a fallback value used when the invocation doesn't supply NAME.
        # Confirmed real: `$STAGE|1$`, `$condition|always$` (scripted_triggers/, both sources).
        # The default text isn't restricted to identifier characters — read up to the closing
        # '$' verbatim, same "scan to the delimiter" approach as string literals, rather than
        # guessing a charset from the handful of examples seen so far.
        default = None
        if self._peek() == "|":
            self._advance()  # '|'
            default_chars = []
            while not self._at_end() and self._peek() != "$":
                default_chars.append(self._advance())
            default = "".join(default_chars)
        if self._peek() != "$":
            raise self._error(f"unterminated parameter reference '${''.join(chars)}' (expected closing '$')", line, column)
        self._advance()  # consume closing '$'
        # A '?' immediately after the closing '$' is the same "safe scope" suffix already
        # recognised on bare identifiers (`space_owner? = { ... }`) — confirmed real on a
        # parameter reference too: `$SCOPE$? = { ... }`. Kept out of `.text` (the parameter
        # *name* other passes look up by) since, unlike a literal identifier, corrupting the
        # name would break parameter-table lookups; carried as a separate flag instead.
        safe = False
        if self._peek() == "?":
            self._advance()
            safe = True
        if self._has_attached_continuation():
            flattened = ["$", *chars]
            if default is not None:
                flattened.append("|")
                flattened.extend(default)
            flattened.append("$")
            if safe:
                flattened.append("?")
            self._consume_attached_continuations(flattened)
            return Token(TokenType.IDENTIFIER, "".join(flattened), line, column)
        return Token(TokenType.PARAMETER, "".join(chars), line, column, default=default, safe=safe)

    def _scan_operator(self, line: int, column: int) -> Token:
        ch = self._advance()
        if ch == "!":
            if self._peek() == "=":
                self._advance()
                return Token(TokenType.OPERATOR, "!=", line, column)
            if self._peek() in _IDENTIFIER_START:
                # Bare '!' immediately before a name is only valid as the negation marker
                # opening a `[[!NAME]` conditional-block guard (confirmed real:
                # `[[!SPECIES]`, `[[!WHO]`, several others). The parser is what actually
                # requires the `[[` context; the tokeniser just stops rejecting this shape.
                return Token(TokenType.OPERATOR, "!", line, column)
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
        self._consume_attached_continuations(chars)
        return Token(TokenType.IDENTIFIER, "".join(chars), line, column)
