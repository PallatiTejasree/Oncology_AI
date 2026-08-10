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

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
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
