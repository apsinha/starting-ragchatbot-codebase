#!/bin/bash
# Code quality checks for the RAG chatbot project
# Usage:
#   ./scripts/quality.sh          Run all checks
#   ./scripts/quality.sh format   Auto-format code with Black
#   ./scripts/quality.sh check    Check formatting without modifying files

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_DIRS="backend main.py"

format() {
    echo "=== Formatting code with Black ==="
    uv run black $PYTHON_DIRS
    echo "Done."
}

check() {
    echo "=== Checking code formatting with Black ==="
    uv run black --check --diff $PYTHON_DIRS
    echo "All files are properly formatted."
}

run_all() {
    check
}

case "${1:-all}" in
    format)
        format
        ;;
    check)
        check
        ;;
    all)
        run_all
        ;;
    *)
        echo "Usage: $0 {format|check|all}"
        exit 1
        ;;
esac
