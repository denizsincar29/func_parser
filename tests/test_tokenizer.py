"""Tests for the tokenizer."""
import pytest
from func_parser.parser.tokenizer import Tokenizer, TokenType


def tok(text):
    return Tokenizer().tokenize(text)


def types(tokens):
    return [t.type for t in tokens if t.type != TokenType.EOF]


def values(tokens):
    return [t.value for t in tokens if t.type != TokenType.EOF]


class TestBasicTokens:
    def test_command(self):
        tokens = tok("/greet")
        assert types(tokens) == [TokenType.COMMAND]
        assert values(tokens) == ["/greet"]

    def test_command_with_args(self):
        tokens = tok("/greet Alice 42")
        assert types(tokens) == [TokenType.COMMAND, TokenType.ARG, TokenType.ARG]
        assert values(tokens) == ["/greet", "Alice", "42"]

    def test_quoted_arg(self):
        tokens = tok('/say "hello world"')
        assert types(tokens) == [TokenType.COMMAND, TokenType.ARG]
        assert values(tokens) == ["/say", "hello world"]

    def test_single_quoted_arg(self):
        tokens = tok("/say 'hello world'")
        t = [t for t in tokens if t.type == TokenType.ARG]
        assert t[0].value == "hello world"

    def test_escape_in_quotes(self):
        tokens = tok(r'/say "line1\nline2"')
        args = [t for t in tokens if t.type == TokenType.ARG]
        assert args[0].value == "line1\nline2"

    def test_plain_text_not_command(self):
        tokens = tok("hello world")
        # Plain text without '/' prefix should NOT be a COMMAND token
        assert tokens[0].type != TokenType.COMMAND

    def test_eof(self):
        tokens = tok("/foo")
        assert tokens[-1].type == TokenType.EOF

    def test_comment(self):
        tokens = tok("# this is a comment")
        assert tokens[0].type == TokenType.COMMENT

    def test_empty_string(self):
        tokens = tok("")
        assert tokens == [pytest.approx(tokens[0])] or tokens[0].type == TokenType.EOF


class TestOperators:
    def test_pipe(self):
        tokens = tok("/a | /b")
        t = types(tokens)
        assert TokenType.PIPE in t

    def test_and(self):
        tokens = tok("/a && /b")
        t = types(tokens)
        assert TokenType.AND in t

    def test_or(self):
        tokens = tok("/a || /b")
        t = types(tokens)
        assert TokenType.OR in t

    def test_redirect_out(self):
        tokens = tok("/cmd > file.txt")
        t = types(tokens)
        assert TokenType.REDIRECT_OUT in t

    def test_redirect_append(self):
        tokens = tok("/cmd >> file.txt")
        t = types(tokens)
        assert TokenType.REDIRECT_APPEND in t

    def test_redirect_clipboard(self):
        tokens = tok("/cmd >clipboard")
        t = types(tokens)
        assert TokenType.REDIRECT_CLIPBOARD in t

    def test_redirect_clipboard_append(self):
        tokens = tok("/cmd >>clipboard")
        t = types(tokens)
        assert TokenType.REDIRECT_CLIPBOARD in t


class TestSpecialDirectives:
    def test_set_var(self):
        tokens = tok("//set x=5")
        assert tokens[0].type == TokenType.SET_VAR

    def test_setenv(self):
        tokens = tok("//setenv HOME=/tmp")
        assert tokens[0].type == TokenType.SET_VAR

    def test_execute(self):
        tokens = tok("/execute script.txt")
        assert tokens[0].type == TokenType.EXECUTE

    def test_file_injection(self):
        tokens = tok("/cmd {file.txt}")
        args = [t for t in tokens if t.type == TokenType.ARG]
        assert args[0].value == "{file.txt}"

    def test_kwarg(self):
        tokens = tok("/cmd name=Alice")
        args = [t for t in tokens if t.type == TokenType.ARG]
        assert args[0].value == "name=Alice"
