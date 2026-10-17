# GigRadar CI/pre-commit verification script
$ErrorActionPreference = "Stop"

Write-Host "==> Running Ruff (Linting)..." -ForegroundColor Cyan
uv run ruff check .

Write-Host "==> Running Mypy (Type checking)..." -ForegroundColor Cyan
uv run mypy src tests

Write-Host "==> Running Pytest (Test suite)..." -ForegroundColor Cyan
uv run pytest

Write-Host "==> All checks passed successfully!" -ForegroundColor Green
