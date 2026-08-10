# Oncology query layer

The query models must match the stored embedding spaces:

- MedCPT Query Encoder searches `oncology_text_embeddings` using inner product.
- BiomedCLIP text/image encoders search `oncology_image_embeddings` using cosine.
- Cross-collection results are combined by reciprocal-rank fusion; raw MedCPT
  and BiomedCLIP scores are never compared directly.

Run from the project root with the virtual environment active:

```bash
python -m Query.query_text "EGFR-mutated lung adenocarcinoma"
python -m Query.query_image /absolute/path/to/image.jpg
python -m Query.query_both /absolute/path/to/image.jpg "OCR or report text"
python -m unittest discover -s Query/tests -v
```

`retrieval_score`, `distance`, and `rrf_score` are ranking signals. They are not
diagnostic probabilities or calibrated clinical confidence values.
