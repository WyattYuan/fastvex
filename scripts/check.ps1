Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

uv run ruff check .
uv run pytest
uv build --wheel --no-sources
uv tool install --force .
