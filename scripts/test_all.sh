#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing virtual environment. Run: python3 -m venv venv"
  exit 2
fi

if [[ ! -d "${PROJECT_ROOT}/frontend/node_modules" ]]; then
  echo "Missing frontend dependencies. Run: cd frontend && npm install"
  exit 2
fi

echo "[1/8] Query tests"
cd "${PROJECT_ROOT}"
"${PYTHON_BIN}" -m unittest discover -s Query/tests -v

echo "[2/8] Ingestion tests"
"${PYTHON_BIN}" -m unittest discover -s Ingestion/tests -v

echo "[3/8] Backend tests"
PYTHONPATH="${PROJECT_ROOT}/backend:${PROJECT_ROOT}" \
  "${PYTHON_BIN}" -m unittest discover -s backend/tests -p "test_*.py" -v

echo "[4/8] Evaluation tests"
PYTHONPATH="${PROJECT_ROOT}/backend:${PROJECT_ROOT}" \
  "${PYTHON_BIN}" -m unittest discover -s Evaluation/tests -v

echo "[5/8] Legacy LangChain layer tests"
cd "${PROJECT_ROOT}/LangChain_Layer"
"${PYTHON_BIN}" -m unittest discover -s tests -v

echo "[6/8] Python syntax compilation"
cd "${PROJECT_ROOT}"
"${PYTHON_BIN}" -m compileall -q \
  Query Ingestion LangChain_Layer Evaluation backend/app

echo "[7/8] Frontend tests"
cd "${PROJECT_ROOT}/frontend"
CI=true npm test -- --watchAll=false

echo "[8/8] Frontend production build"
npm run build

echo "All local tests and the production build passed."
