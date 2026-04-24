"""Tests for validators, permissions, variables, scheduler, and I/O."""
import asyncio
import pytest
import pytest_asyncio
from func_parser.core.validation import coerce_type, validate_arg, PRESETS
from func_parser.core.models import ArgDef
from func_parser.core.errors import InvalidArgError, ValidationError
from func_parser.core.permissions import PermissionChecker
from func_parser.core.errors import PermissionDeniedError
from func_parser.core.variables import VariableStore
from func_parser.scheduler import Scheduler
from func_parser.core.errors import SchedulerError


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------

class TestCoercion:
    def _arg(self, t):
        return ArgDef(name="x", type=t)

    def test_int(self):
        assert coerce_type("42", self._arg(int)) == 42

    def test_float(self):
        assert coerce_type("3.14", self._arg(float)) == pytest.approx(3.14)

    def test_bool_true(self):
        for v in ("true", "yes", "1", "on"):
            assert coerce_type(v, self._arg(bool)) is True

    def test_bool_false(self):
        for v in ("false", "no", "0", "off"):
            assert coerce_type(v, self._arg(bool)) is False

    def test_bool_invalid(self):
        with pytest.raises(InvalidArgError):
            coerce_type("maybe", self._arg(bool))

    def test_str_passthrough(self):
        assert coerce_type("hello", self._arg(str)) == "hello"

    def test_invalid_int(self):
        with pytest.raises(InvalidArgError):
            coerce_type("abc", self._arg(int))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def _arg(self, **kwargs):
        return ArgDef(name="x", **kwargs)

    def test_choices_valid(self):
        arg = self._arg(choices=["a", "b", "c"])
        assert validate_arg("x", "a", arg) == "a"

    def test_choices_invalid(self):
        arg = self._arg(choices=["a", "b"])
        with pytest.raises(InvalidArgError):
            validate_arg("x", "z", arg)

    def test_min_range(self):
        arg = self._arg(type=int, min=1.0)
        with pytest.raises(InvalidArgError):
            validate_arg("x", 0, arg)

    def test_max_range(self):
        arg = self._arg(type=int, max=10.0)
        with pytest.raises(InvalidArgError):
            validate_arg("x", 11, arg)

    def test_range_valid(self):
        arg = self._arg(type=int, min=1.0, max=10.0)
        assert validate_arg("x", 5, arg) == 5

    def test_regex_valid(self):
        arg = self._arg(regex=r"^\d{3}$")
        assert validate_arg("x", "123", arg) == "123"

    def test_regex_invalid(self):
        arg = self._arg(regex=r"^\d{3}$")
        with pytest.raises(ValidationError):
            validate_arg("x", "12x", arg)

    def test_preset_email_valid(self):
        arg = self._arg(preset="email")
        assert validate_arg("x", "user@example.com", arg) == "user@example.com"

    def test_preset_email_invalid(self):
        arg = self._arg(preset="email")
        with pytest.raises(ValidationError):
            validate_arg("x", "notanemail", arg)

    def test_preset_url_valid(self):
        arg = self._arg(preset="url")
        assert validate_arg("x", "https://example.com", arg) == "https://example.com"

    def test_custom_validator_pass(self):
        def is_even(v):
            return v % 2 == 0

        arg = self._arg(type=int, validators=[is_even])
        assert validate_arg("x", 4, arg) == 4

    def test_custom_validator_fail(self):
        def is_even(v):
            return v % 2 == 0

        arg = self._arg(type=int, validators=[is_even])
        with pytest.raises(ValidationError):
            validate_arg("x", 3, arg)

    def test_custom_validator_string_message(self):
        def check(v):
            return "too short" if len(str(v)) < 3 else None

        arg = self._arg(validators=[check])
        with pytest.raises(ValidationError, match="too short"):
            validate_arg("x", "ab", arg)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class TestPermissions:
    def setup_method(self):
        self.checker = PermissionChecker()

    def test_admin_can_do_anything(self):
        assert self.checker.check(["admin"], ["whatever"], "u1")

    def test_user_has_no_perms_by_default(self):
        assert not self.checker.check(["user"], ["admin"], "u1")

    def test_require_raises_on_missing(self):
        with pytest.raises(PermissionDeniedError):
            self.checker.require(["user"], ["admin"], "u1")

    def test_grant_user_permission(self):
        self.checker.grant("u1", "write")
        assert self.checker.check(["user"], ["write"], "u1")

    def test_revoke_permission(self):
        self.checker.grant("u1", "write")
        self.checker.revoke("u1", "write")
        assert not self.checker.check(["user"], ["write"], "u1")

    def test_add_role(self):
        self.checker.add_role("moderator", ["moderate"])
        assert self.checker.check(["moderator"], ["moderate"], "u1")

    def test_no_required_perms_always_passes(self):
        assert self.checker.check(["user"], [], "u1")


# ---------------------------------------------------------------------------
# VariableStore
# ---------------------------------------------------------------------------

class TestVariableStore:
    def test_set_get_local(self):
        vs = VariableStore()
        vs.set("x", 42)
        assert vs.get("x") == 42

    def test_expand_braces(self):
        vs = VariableStore()
        vs.set("name", "Alice")
        assert vs.expand("Hello ${name}!") == "Hello Alice!"

    def test_expand_dollar_upper(self):
        import os
        os.environ["TEST_FUNC_PARSER_VAR"] = "found"
        vs = VariableStore()
        result = vs.expand("$TEST_FUNC_PARSER_VAR")
        assert result == "found"

    def test_expand_unknown_unchanged(self):
        vs = VariableStore()
        assert vs.expand("${undefined_xyz}") == "${undefined_xyz}"

    def test_child_scope_inherits(self):
        parent = VariableStore()
        parent.set("x", 10)
        child = parent.child()
        assert child.get("x") == 10

    def test_child_scope_shadows(self):
        parent = VariableStore()
        parent.set("x", 10)
        child = parent.child()
        child.set("x", 99)
        assert child.get("x") == 99
        assert parent.get("x") == 10

    def test_all_vars(self):
        vs = VariableStore()
        vs.set("a", 1)
        vs.set("b", 2)
        all_v = vs.all_vars()
        assert all_v["a"] == 1
        assert all_v["b"] == 2


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestScheduler:
    def test_interval_seconds(self):
        s = Scheduler(lambda cmd: None)
        assert s.parse_spec("every 30s") == 30.0

    def test_interval_minutes(self):
        s = Scheduler(lambda cmd: None)
        assert s.parse_spec("every 5m") == 300.0

    def test_interval_hours(self):
        s = Scheduler(lambda cmd: None)
        assert s.parse_spec("every 2h") == 7200.0

    def test_at_spec_positive_delay(self):
        from datetime import datetime, timedelta
        s = Scheduler(lambda cmd: None)
        # Test with a time slightly in the future (avoid exact match edge cases)
        now = datetime.now()
        future = now + timedelta(minutes=5)
        spec = f"at {future.hour:02d}:{future.minute:02d}"
        delay = s.parse_spec(spec)
        # Should be roughly 5 minutes (±60 s due to second rounding)
        assert 200 <= delay <= 400

    def test_at_invalid_hour(self):
        s = Scheduler(lambda cmd: None)
        with pytest.raises(SchedulerError):
            s.parse_spec("at 25:00")

    def test_at_invalid_minute(self):
        s = Scheduler(lambda cmd: None)
        with pytest.raises(SchedulerError):
            s.parse_spec("at 12:60")

    def test_invalid_spec(self):
        s = Scheduler(lambda cmd: None)
        with pytest.raises(SchedulerError):
            s.parse_spec("whenever I feel like it")
