Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

uv run ruff check .
uv run pytest
