# Oncology AI

Multimodal oncology evidence-retrieval and clinical explanation prototype using
MedCPT text retrieval, BiomedCLIP image retrieval, Chroma, weighted reciprocal
rank fusion, Gemini-generated structured answers, FastAPI, PostgreSQL, and React.

> This project is clinical decision-support research software. It is not a
> validated diagnostic device and must not replace qualified medical judgment.

## Repository structure

- `Dataset_Downloader/` — reproducible data acquisition scripts
- `Ingestion/` — preprocessing, embeddings, and Chroma ingestion
- `Query/` — semantic, lexical, image, and multimodal retrieval
- `backend/` — FastAPI authentication, upload, analysis, safety, and history APIs
- `frontend/` — React application
- `Evaluation/` — retrieval, answer, acceptance, and performance evaluation

Downloaded datasets, embeddings, Chroma indexes, user uploads, API keys,
virtual environments, and generated outputs are intentionally excluded from Git.

## Documentation map

`README.md` is the primary project guide. The additional README files are
component-specific documentation rather than duplicate project introductions:

- [`Query/README.md`](Query/README.md) — retrieval models, score semantics, and query commands
- [`Ingestion/README.md`](Ingestion/README.md) — dataset preparation, embeddings, and Chroma ingestion
- [`Evaluation/README.md`](Evaluation/README.md) — retrieval and structured-answer evaluation
- [`backend/alembic/README.md`](backend/alembic/README.md) — PostgreSQL migration procedure
- [`TESTING.md`](TESTING.md) — complete local, live, and performance verification

`frontend/README.md` contains the Create React App command reference for the
frontend package.

## Database migration layout

Alembic is the canonical deployment migration system:

- `alembic.ini` — project-level Alembic configuration
- `backend/alembic/env.py` — database connection and SQLAlchemy metadata integration
- `backend/alembic/script.py.mako` — template used when creating revisions
- `backend/alembic/versions/` — ordered, immutable migration revisions

The scripts in `backend/migrations/` are preserved compatibility/data-migration
helpers from the pre-Alembic project. They are not a second Alembic installation;
active seed revisions import the shared quick-response catalog from that package.

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env
```

Configure PostgreSQL and the environment variables in `backend/.env`, then run:

```bash
PYTHONPATH=backend:. uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm start
```

## Evaluation

See [`Evaluation/README.md`](Evaluation/README.md) for retrieval metrics,
structured-answer checks, API acceptance tests, and performance commands.

## Testing

See [`TESTING.md`](TESTING.md) for the local regression suite, database and
Chroma verification, live end-to-end checks, acceptance cases, and load tests.
For the complete deterministic local check, run:

```bash
bash scripts/test_all.sh
```
