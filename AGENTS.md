# fastvex Agent Handoff

## Project Snapshot

`fastvex` is an independent Python CLI/package for VEX V5 / PROS robot projects. It manages slot-oriented build/upload workflows from a robot-project-local config file.

Current package state:

- Package/import/command name: `fastvex`
- Current version: `0.0.2`
- Python: `>=3.11`
- Package manager: `uv`
- Remote: `https://github.com/WyattYuan/fastvex.git`
- Main branch: `main`
- Published/release work has started; recent commits mention PyPI publishing.

The robot repo is a consumer of this package, not the home of its implementation.

## Recent Git Context

Recent commits inspected:

- `e468046` 更新 README 安装和使用说明，改为使用 `uv` / `uv tool`
- `17ebf12` 添加 toolchain 检测功能，版本到 `0.0.2`
- `893f42e` 添加 PyPI 发布相关文件
- `d60b678` 添加 MIT license 并 bump 到 `0.0.1`
- Earlier structural refactors:
  - Pydantic config/state models
  - command-level `services.py`
  - thin Typer shell in `cli.py`

At the time this file was written, `git status --short` in `D:\100Code\VEX\fastvex` was clean before adding this file.

## Repository Layout

- `src/fastvex/cli.py`
  - Typer command shell only: parse options, call services, print output, map exit codes.
- `src/fastvex/services.py`
  - Command-level Python API: `validate_project`, `upload_slots`, `show_toolchain`, `set_route`, etc.
- `src/fastvex/project.py`
  - Project root/config/state path resolution.
  - Config file location defines the robot project root.
- `src/fastvex/models.py`
  - Pydantic config models.
  - Internal fields are snake_case; YAML aliases preserve camelCase such as `robotName`.
- `src/fastvex/state_model.py`
  - Pydantic state/history/execution models.
  - State is read leniently and written in normalized JSON.
- `src/fastvex/executor.py`
  - Build/upload execution logic and `CommandRunner`.
  - Records command, duration, return code, output, and error.
- `src/fastvex/toolchain.py`
  - PROS discovery/cache logic.
  - Cache path is global: `~/.fastvex/toolchain.json`.
- `src/fastvex/display.py`
  - Rich display helpers.
- `src/fastvex/config_edit.py`
  - Text-preserving YAML active route update.
- `tests/`
  - CLI, executor, services, and toolchain tests with fake PROS/make tooling.
- `scripts/check.ps1`
  - Local validation script.

## Design Decisions To Preserve

- The Python package lives outside robot repositories.
- Robot repositories should keep project-specific config such as `fastvex.yaml`.
- Local runtime state belongs under `.fastvex/state.json` and should not be committed by robot projects.
- Legacy config name `vex_upload_config.yaml` remains readable, with a warning.
- Config `slots` must define all V5 Brain slots `1..8`.
- Internal slot keys should be integers, even though JSON writes object keys as strings.
- CLI must remain a thin layer; reusable behavior belongs in `services.py`.
- Public Python API should be command-level services, not direct low-level composition.
- Use Pydantic v2 for YAML/JSON boundary models, not for every internal helper.
- Use `uv` for local development and validation.

## Commands

Development setup:

```powershell
uv sync
```

Validate locally:

```powershell
uv run ruff check .
uv run pytest
.\scripts\check.ps1
```

Smoke test against the VEX robot repo:

```powershell
uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex validate
uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex route show
uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex upload --slots 3 --dry-run --state $env:TEMP\fastvex-test-state.json
```

Toolchain check:

```powershell
uv run fastvex toolchain
uv run fastvex toolchain --rescan
```

## Current Feature Notes

Toolchain detection was recently added:

- `fastvex toolchain` reports cached/discovered PROS path.
- `fastvex toolchain --rescan` clears the cached path and rediscovers.
- Upload service calls `resolve_toolchain()` and passes a PATH override into executor.
- Cache file: `~/.fastvex/toolchain.json`.

Release/publish scaffolding was also recently added:

- `LICENSE`
- `CONTRIBUTING.md`
- `.github/workflows/publish.yml`
- README now recommends `uvx fastvex` and `uv tool install fastvex`.

## Things To Check Next

1. Run the full local checks after any change:

   ```powershell
   .\scripts\check.ps1
   ```

   Current local checks were clean after the Rich output cleanup:

   - `uv run ruff check .`
   - `uv run pytest`

2. Re-check the toolchain tests if changing command execution or PATH behavior:

   ```powershell
   uv run pytest tests\test_toolchain.py
   ```

3. Be careful with GitHub workflow changes. Earlier push attempts failed when the token lacked `workflow` scope. If editing `.github/workflows/*`, verify the authenticated token can push workflow files.

4. The robot repo at `D:\100Code\VEX\VEX-PushBack-Linyun` currently uses the legacy `vex_upload_config.yaml`. `fastvex` can read it, but the eventual migration should rename it to `fastvex.yaml` and add `.fastvex/` to that repo's `.gitignore`.

5. Do not accidentally write test state into robot repos. Prefer `--state $env:TEMP\...` for smoke tests.

## Collaboration Notes

- Prefer small commits with Conventional Commit style when committing from this repo.
- Keep README in Chinese unless the user asks otherwise.
- Avoid moving robot-specific behavior into this package. `fastvex` should remain a generic VEX/PROS deployment helper.
- When unsure whether a behavior belongs in CLI or services, put it in services and keep CLI as presentation/argument plumbing.
