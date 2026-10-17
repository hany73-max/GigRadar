#!/usr/bin/env bash
set -e

echo "==> Running Ruff (Linting)..."
uv run ruff check .

echo "==> Running Mypy (Type checking)..."
uv run mypy src tests

echo "==> Running Pytest (Test suite)..."
uv run pytest

echo "==> All checks passed successfully!"
