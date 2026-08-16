# Testing Oncology AI

Run commands from the repository root unless a section says otherwise. These
checks deliberately separate local deterministic tests from tests that need
PostgreSQL, Gemini, or a running API.

## One-command local verification

Install Python and frontend dependencies first, then run:

```bash
bash scripts/test_all.sh
```

This runs Query, ingestion, backend, evaluation, and legacy-layer tests,
compiles the Python packages, runs the React tests, and creates a production
frontend build. The legacy PaddleOCR experiments are skipped by default because
the active upload pipeline uses Tesseract.

## Database and vector-index checks

```bash
venv/bin/alembic current
venv/bin/python -m Ingestion.vectordb.verify_db
```

For an empty database, apply migrations with `venv/bin/alembic upgrade head`.
Do not use `alembic stamp` unless an existing database already has the complete
schema described in `backend/alembic/README.md`.

## Start the application

Terminal 1:

```bash
PYTHONPATH=backend:. venv/bin/uvicorn app.main:app --reload
```

Terminal 2:

```bash
cd frontend
npm start
```

Verify `http://127.0.0.1:8000/health` and
`http://127.0.0.1:8000/analysis/status` before live testing.

## Live end-to-end verification

Use a dedicated test account and keep its credentials out of Git:

```bash
export TEST_USER_EMAIL="test@example.com"
export TEST_USER_PASSWORD="replace-with-test-password"
PYTHONPATH=backend:. venv/bin/python backend/tests/run_live_system_e2e.py
```

Use `--allow-gemini-fallback` only when intentionally testing without generated
Gemini output. The runner removes its test sessions unless `--keep-sessions` is
provided.

Run the acceptance catalog in increasing-cost order:

```bash
PYTHONPATH=backend:. venv/bin/python backend/tests/run_chat_e2e.py --mode smoke --cleanup
PYTHONPATH=backend:. venv/bin/python backend/tests/run_chat_e2e.py --mode uploads --cleanup
PYTHONPATH=backend:. venv/bin/python backend/tests/run_chat_e2e.py --mode full --cleanup
```

## Retrieval, answer, and load evaluation

```bash
venv/bin/python -m Evaluation.evaluate --k 1 3 5 10
PYTHONPATH=backend:. venv/bin/python -m Evaluation.run_structured_benchmark \
  --case-id SA-TXT-001 --no-resume
venv/bin/python -m Evaluation.evaluate_answers \
  Evaluation/outputs/structured_benchmark_results.json
venv/bin/python -m Evaluation.load_test \
  --mode health --requests 100 --concurrency 10
```

The full structured benchmark calls local embedding models and Gemini. Its
automatic scores do not establish clinical correctness; clinician review is
required for medical validity.

## Optional legacy PaddleOCR experiment

The `LangChain_Layer` PaddleOCR path is not used by the current FastAPI upload
pipeline. If its full native dependency stack is installed, run it explicitly:

```bash
cd LangChain_Layer
RUN_PADDLEOCR_TEST=1 RUN_LEGACY_OCR_TESTS=1 \
  ../venv/bin/python -m unittest discover -s tests -v
```
