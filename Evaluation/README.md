# Retrieval evaluation

This folder evaluates the real MedCPT and BiomedCLIP Chroma retrieval layer.
It reports Precision@K, Recall@K, Hit Rate@K, MRR@K, MAP@K, and nDCG@K.
Cancer/source label hits are reported separately and are not treated as proof
of semantic relevance.

`Judged@K` reports how much of the retrieved set has been reviewed. Precision,
Recall, MAP, and nDCG should not be used for decisions while judgment coverage
is low because unjudged results are conservatively counted as non-relevant.

Run tests:

```bash
python -m unittest discover -s Evaluation/tests -v
```

Run the starter evaluation:

```bash
python -m Evaluation.evaluate --k 1 3 5 10
```

Regenerate the deterministic 50-case starter set when source artifacts change:

```bash
python -m Evaluation.build_seed_cases
```

The generated set contains 20 text cases, 15 caption-to-image cases, 10 image
self-retrieval cases, and 5 hybrid cases. These are known-item integrity tests,
not an independent clinical benchmark.

For reproducible exact-item recovery testing only, top-K candidates can be
labelled automatically. This must never be presented as clinician review:

```bash
python -m Evaluation.label_known_item_pool --top-k 5
python -m Evaluation.apply_annotations
```

Generate candidates for human review:

```bash
python -m Evaluation.build_annotation_pool --top-k 20
```

Open `outputs/annotation_pool.csv`, review each result, fill
`reviewed_relevance` with 0–3 and add the reviewer name. Transfer the reviewed
judgments into `data/qrels.csv`, then rerun the evaluation:

```bash
python -m Evaluation.apply_annotations
python -m Evaluation.evaluate --k 1 3 5 10
```

The import creates `data/qrels.csv.backup` before changing qrels. It refuses to
run when no reviewed rows are present or a reviewed row has no reviewer.

Outputs are written to:

```text
Evaluation/outputs/evaluation_summary.json
Evaluation/outputs/per_case_metrics.csv
```

## Generated-answer evaluation

Export completed application responses and evaluate them:

```bash
PYTHONPATH=backend:. python -m Evaluation.export_answers --limit 50
python -m Evaluation.evaluate_answers Evaluation/outputs/llm_analysis_results.json
```

To measure only answers produced after citation validation was introduced:

```bash
PYTHONPATH=backend:. python -m Evaluation.export_answers --limit 50 --new-format-only
python -m Evaluation.evaluate_answers Evaluation/outputs/llm_analysis_results.json
```

This writes `llm_evaluation_summary.json`, `llm_per_case_metrics.csv`, and
`llm_human_review.csv`. Automatic checks cover citation validity/coverage,
answer structure, limitations, and disclaimers. They do not establish clinical
correctness; complete the blinded clinician-review columns before reporting
groundedness, clinical relevance, safety, completeness, or image/text agreement.

## Isolated 20-case structured-answer benchmark

The balanced manifest contains 8 text, 5 image, 5 hybrid, and 2 embedded-image
PDF cases. The runner checkpoints after every case and resumes passed cases:

```bash
PYTHONPATH=backend:. python -m Evaluation.run_structured_benchmark
python -m Evaluation.evaluate_answers Evaluation/outputs/structured_benchmark_results.json
```

Run one smoke case before the full benchmark:

```bash
PYTHONPATH=backend:. python -m Evaluation.run_structured_benchmark \
  --case-id SA-TXT-001 --no-resume
```

Use `--no-resume` to regenerate selected cases. Full runs call local embedding
models and Gemini, so they can take substantial time and consume API quota.

## Adding cases

Add a row to `data/cases.csv`, then add human-reviewed relevance judgments to
`data/qrels.csv`. Relevance grades are:

- `0`: not relevant
- `1`: marginally relevant
- `2`: relevant
- `3`: highly relevant

Every enabled case must have at least one positive qrel. Use canonical Chroma
IDs and the correct item type (`text` or `image`). The five included cases are
pipeline smoke tests, not a sufficient clinical benchmark. Before selecting
confidence thresholds, expand this set with clinician-reviewed queries,
negative judgments, multiple relevant results, and modality-balanced cases.
