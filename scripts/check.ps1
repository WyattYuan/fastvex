Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

uv run ruff check .
uv run pytest --cov --cov-report=term-missing --cov-report=html
uv build --wheel --no-sources
uv tool install --force .
