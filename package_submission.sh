#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
rm -f code.zip
zip -r code.zip code README.md docs requirements.txt data .gitignore \
  -x '*/__pycache__/*' '*/.pytest_cache/*' '*.pyc' 'dataset/*' 'data/raw/*' 'node_modules/*' '.venv/*'

echo "Created $ROOT/code.zip"
