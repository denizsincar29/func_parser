"""Tokenizer for the func_parser command language."""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import List

__all__ = ["TokenType", "Token", "Tokenizer"]


class TokenType(enum.Enum):
    """All token types produced by the tokenizer."""
    COMMAND = "command"
    ARG = "arg"
    PIPE = "pipe"
    AND = "and"
    OR = "or"
    REDIRECT_OUT = "redirect_out"
    REDIRECT_APPEND = "redirect_append"
    REDIRECT_CLIPBOARD = "redirect_clipboard"
    SET_VAR = "set_var"
    EXECUTE = "execute"
    COMMENT = "comment"
    EOF = "eof"


@dataclass
class Token:
    """A single token produced by the tokenizer."""
    type: TokenType
    value: str
    pos: int


class Tokenizer:
    """Converts a raw input string into a list of :class:`Token` objects.

    Handles:
    - Quoted strings (``"..."`` and ``'...'``)
    - Escape sequences inside quotes
    - ``{file.txt}`` argument injection markers
    - ``${var}`` / ``$VAR`` substitution markers (preserved as-is)
    - Operators: ``|``, ``&&``, ``||``, ``>``, ``>>``, ``>clipboard``
    - Special commands: ``//set``, ``//setenv``, ``/execute``
    - Comments (``#``)
    """

    def tokenize(self, text: str) -> List[Token]:
        """Parse *text* and return a list of tokens."""
        tokens: List[Token] = []
        i = 0
        length = len(text)

        while i < length:
            # Skip leading whitespace
            if text[i].isspace():
                i += 1
                continue

            # Comment
            if text[i] == "#":
                tokens.append(Token(TokenType.COMMENT, text[i:], i))
                break

            # >>clipboard / >> (must check >> before >)
            if text[i:i+2] == ">>":
                rest = text[i+2:].lstrip()
                if rest.startswith("clipboard"):
                    tokens.append(Token(TokenType.REDIRECT_CLIPBOARD, ">>clipboard", i))
                    i += 2 + len(text[i+2:]) - len(rest) + len("clipboard")
                else:
                    tokens.append(Token(TokenType.REDIRECT_APPEND, ">>", i))
                    i += 2
                continue

            # >clipboard / >
            if text[i] == ">" and text[i:i+2] != ">>":
                rest = text[i+1:].lstrip()
                if rest.startswith("clipboard"):
                    tokens.append(Token(TokenType.REDIRECT_CLIPBOARD, ">clipboard", i))
                    i += 1 + len(text[i+1:]) - len(rest) + len("clipboard")
                else:
                    tokens.append(Token(TokenType.REDIRECT_OUT, ">", i))
                    i += 1
                continue

            # || (before |)
            if text[i:i+2] == "||":
                tokens.append(Token(TokenType.OR, "||", i))
                i += 2
                continue

            # &&
            if text[i:i+2] == "&&":
                tokens.append(Token(TokenType.AND, "&&", i))
                i += 2
                continue

            # |
            if text[i] == "|":
                tokens.append(Token(TokenType.PIPE, "|", i))
                i += 1
                continue

            # Quoted string
            if text[i] in ('"', "'"):
                value, new_i = self._read_quoted(text, i)
                tokens.append(Token(TokenType.ARG, value, i))
                i = new_i
                continue

            # {file.txt} injection marker
            if text[i] == "{":
                end = text.find("}", i)
                if end != -1:
                    value = text[i:end+1]
                    tokens.append(Token(TokenType.ARG, value, i))
                    i = end + 1
                    continue

            # Word token (command, arg, set, execute, …)
            word, new_i = self._read_word(text, i)
            token_type = self._classify_word(word, tokens)
            tokens.append(Token(token_type, word, i))
            i = new_i

        tokens.append(Token(TokenType.EOF, "", length))
        return tokens

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_quoted(self, text: str, start: int) -> tuple[str, int]:
        """Read a quoted string starting at *start*.  Returns (value, next_index)."""
        quote = text[start]
        i = start + 1
        buf: list[str] = []
        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                next_ch = text[i + 1]
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", quote: quote}
                buf.append(escape_map.get(next_ch, next_ch))
                i += 2
            elif ch == quote:
                i += 1
                break
            else:
                buf.append(ch)
                i += 1
        return "".join(buf), i

    def _read_word(self, text: str, start: int) -> tuple[str, int]:
        """Read a non-quoted word (stops at whitespace or operators)."""
        i = start
        while i < len(text):
            ch = text[i]
            if ch.isspace():
                break
            if ch in ("|", "&", ">", "#"):
                # Don't consume operator characters as part of a word
                # unless they're part of a //-prefixed directive
                if i == start:
                    i += 1  # consume at least one char to avoid infinite loop
                break
            i += 1
        return text[start:i], i

    def _classify_word(self, word: str, preceding: List[Token]) -> TokenType:
        """Determine the token type for *word* given what has been seen so far."""
        # Special directives
        low = word.lower()
        if low in ("//set", "//setenv"):
            return TokenType.SET_VAR
        if low == "/execute":
            return TokenType.EXECUTE

        # First real token on line (or after operator) → COMMAND if starts with /
        meaningful = [t for t in preceding if t.type not in (TokenType.EOF, TokenType.COMMENT)]
        if not meaningful:
            return TokenType.COMMAND

        last = meaningful[-1]
        if last.type in (TokenType.PIPE, TokenType.AND, TokenType.OR):
            return TokenType.COMMAND

        return TokenType.ARG
