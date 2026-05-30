from __future__ import annotations

from pathlib import Path

import pytest

from fastvex.errors import ValidationError
from fastvex.models import KEY_RE, validate_keys
from fastvex.storage import load_config


# ── KEY_RE pattern tests ─────────────────────────────────────────────────


class TestKeyRe:
    def test_lower_camel_case(self):
        assert KEY_RE.match("redAlliance")
        assert KEY_RE.match("leftRoute")
        assert KEY_RE.match("skillComp")

    def test_snake_case(self):
        assert KEY_RE.match("red_alliance")
        assert KEY_RE.match("left_route")
        assert KEY_RE.match("skill_comp")

    def test_single_word(self):
        assert KEY_RE.match("red")
        assert KEY_RE.match("a")

    def test_uppercase_start_rejected(self):
        assert not KEY_RE.match("RedAlliance")
        assert not KEY_RE.match("Red_Alliance")
        assert not KEY_RE.match("ALL")

    def test_leading_underscore_rejected(self):
        assert not KEY_RE.match("_foo")
        assert not KEY_RE.match("_red")

    def test_trailing_underscore_rejected(self):
        assert not KEY_RE.match("foo_")
        assert not KEY_RE.match("red_")

    def test_double_underscore_rejected(self):
        assert not KEY_RE.match("foo__bar")
        assert not KEY_RE.match("red__alliance")


# ── validate_keys error message tests ────────────────────────────────────


class TestValidateKeys:
    def test_valid_snake_case_passes(self):
        validate_keys({"red_alliance": 1, "blue_comp": 2}, "alliance")

    def test_valid_camel_case_passes(self):
        validate_keys({"redAlliance": 1, "blueComp": 2}, "alliance")

    def test_invalid_key_raises_with_clear_message(self):
        with pytest.raises(ValueError, match="alliance key 'Red_Alliance' is invalid"):
            validate_keys({"Red_Alliance": 1}, "alliance")

    def test_error_message_mentions_camel_and_snake(self):
        with pytest.raises(ValueError, match="camelCase or snake_case"):
            validate_keys({"_bad": 1}, "route")


# ── Config loading: snake_case in dictionary keys ────────────────────────


class TestSnakeCaseConfig:
    def _write_config(self, root: Path, text: str) -> Path:
        path = root / "fastvex.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_snake_case_alliance_name(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
alliances:
  red_alliance:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red_alliance
    buildArgs:
      MODE: COMP
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        config = load_config(path)
        assert "red_alliance" in config.alliances

    def test_snake_case_route_name(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
alliances:
  red:
    routes:
      left_route:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: left_route
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        config = load_config(path)
        assert "left_route" in config.alliances["red"].routes

    def test_snake_case_profile_name(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  red_comp:
    alliance: red
slots:
  1:
    profile: red_comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        config = load_config(path)
        assert "red_comp" in config.profiles

    def test_snake_case_slot_group_name(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
slotGroups:
  all_slots: [1, 2, 3, 4, 5, 6, 7, 8]
""",
        )
        config = load_config(path)
        assert "all_slots" in config.slot_groups


# ── Config loading: error messages ───────────────────────────────────────


class TestConfigErrorMessages:
    def _write_config(self, root: Path, text: str) -> Path:
        path = root / "fastvex.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_uppercase_alliance_key_rejected(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
alliances:
  Red_Alliance:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: Red_Alliance
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        with pytest.raises(ValidationError, match="camelCase or snake_case"):
            load_config(path)

    def test_unknown_top_level_field_suggests(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
SchemaVersion: 2
alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        with pytest.raises(ValidationError, match="did you mean 'schemaVersion'"):
            load_config(path)

    def test_unknown_field_no_suggestion(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
xyzzy: true
alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        with pytest.raises(ValidationError, match="unknown field.*expected one of"):
            load_config(path)

    def test_unknown_robot_field(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
  RobotName: Sparkle
alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        with pytest.raises(ValidationError, match="robot.RobotName.*unknown field"):
            load_config(path)

    def test_bad_template_placeholder(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
programName:
  template: "{foo}-{robot}"
alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: left
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        with pytest.raises(ValidationError, match=r"unknown placeholder '\{foo\}'.*allowed:"):
            load_config(path)

    def test_uppercase_route_key_rejected(self, tmp_path: Path):
        path = self._write_config(
            tmp_path,
            """\
schemaVersion: 2
robot:
  name: Test
alliances:
  red:
    routes:
      Left_Route:
        buildArgs:
          ROUTE: 1
profiles:
  comp:
    alliance: red
slots:
  1:
    profile: comp
    route: Left_Route
  2: empty
  3: empty
  4: empty
  5: empty
  6: empty
  7: empty
  8: empty
""",
        )
        with pytest.raises(ValidationError, match="camelCase or snake_case"):
            load_config(path)
