from __future__ import annotations

import os
from pathlib import Path

import pytest

from fastvex.templates import DEFAULT_CONFIG_TEXT
from fastvex import toolchain


@pytest.fixture
def robot_project(tmp_path: Path) -> Path:
    root = tmp_path / "robot"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.cpp").write_text(
        "bool red = kIsRed;\nint route = kRoute;\n",
        encoding="utf-8",
    )
    (root / "project.pros").write_text('{"project_name":"fake"}\n', encoding="utf-8")
    (root / "Makefile").write_text("all:\n\t@echo fake\n", encoding="utf-8")
    (root / "fastvex.yaml").write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return root


@pytest.fixture
def fake_tool_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "fake_bin"
    bin_dir.mkdir()
    log_path = tmp_path / "commands.log"
    monkeypatch.setenv("FASTVEX_FAKE_LOG", str(log_path))

    if os.name == "nt":
        pros = bin_dir / "pros.cmd"
        make = bin_dir / "make.cmd"
        pros.write_text(
            "@echo off\n"
            ">> \"%FASTVEX_FAKE_LOG%\" echo pros %*\n"
            "if \"%FASTVEX_PROS_MAKE_FAIL%\"==\"1\" if \"%1\"==\"make\" exit /b 1\n"
            "if \"%FASTVEX_PROS_UPLOAD_FAIL%\"==\"1\" if \"%1\"==\"upload\" exit /b 1\n"
            "exit /b 0\n",
            encoding="utf-8",
        )
        make.write_text(
            "@echo off\n"
            ">> \"%FASTVEX_FAKE_LOG%\" echo make %*\n"
            "if \"%FASTVEX_MAKE_FAIL%\"==\"1\" exit /b 1\n"
            "exit /b 0\n",
            encoding="utf-8",
        )
    else:
        pros = bin_dir / "pros"
        make = bin_dir / "make"
        pros.write_text(
            "#!/usr/bin/env sh\n"
            "echo \"pros $*\" >> \"$FASTVEX_FAKE_LOG\"\n"
            "if [ \"$FASTVEX_PROS_MAKE_FAIL\" = \"1\" ] && [ \"$1\" = \"make\" ]; then exit 1; fi\n"
            "if [ \"$FASTVEX_PROS_UPLOAD_FAIL\" = \"1\" ] && [ \"$1\" = \"upload\" ]; then exit 1; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        make.write_text(
            "#!/usr/bin/env sh\n"
            "echo \"make $*\" >> \"$FASTVEX_FAKE_LOG\"\n"
            "if [ \"$FASTVEX_MAKE_FAIL\" = \"1\" ]; then exit 1; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        pros.chmod(0o755)
        make.chmod(0o755)

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    toolchain.invalidate_toolchain_cache()
    yield log_path
    toolchain.invalidate_toolchain_cache()
