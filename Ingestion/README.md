# Oncology AI ingestion

This directory contains the offline dataset preparation pipeline. Raw PMC
packages remain in `Dataset_Downloader/downloads`; processed outputs are
written beneath `Ingestion/processed_dataset`.

## Pipeline

Run commands from the project root:

```bash
venv/bin/python -m Ingestion.parser.xml_parser
venv/bin/python -m Ingestion.Preprocessing.create_image_metadata
venv/bin/python -m Ingestion.Preprocessing.remove_duplicates
venv/bin/python -m unittest discover -s Ingestion/tests -v
```

The parser creates one JSON file per PMCID. If the same article was downloaded
under multiple search categories, `cancer_types` contains every label instead
of duplicating or overwriting the article.

`create_image_metadata` performs caption classification, source lookup, image
validation, SHA-256 hashing, and copies accepted images to
`processed_dataset/medical_images/<PMCID>/`. Its complete decision record is
stored in `processed_dataset/image_metadata.csv`.

To audit the dataset without copying images:

```bash
venv/bin/python -m Ingestion.Preprocessing.create_image_metadata --no-copy
```

Duplicate detection is non-destructive. It writes
`processed_dataset/duplicate_images.csv`; it never deletes raw data.

## Data separation

- `datasets/processed/clean_reports.csv` is the labelled TCGA report corpus.
- `processed_dataset/` is the newer PMC article/figure corpus.
- `datasets/images/oncology_images/` is a legacy unlabelled image collection
  whose rows remain marked as `cancer_type=unknown`. The embedding metadata
  keeps it distinguishable from the labelled PMC corpus.

## Next stage

Generate MedCPT text embeddings and BiomedCLIP image embeddings only after
manually reviewing a stratified sample of accepted and rejected images:

```bash
python -m Ingestion.embeddings.medcpt_encoder --batch-size 16
python -m Ingestion.embeddings.biomedclip_encoder --limit 32
python -m Ingestion.embeddings.biomedclip_encoder --batch-size 32
```

The first BiomedCLIP command is a small smoke test; the final command embeds
the complete PMC and legacy image collections. Store text and image vectors in
separate Chroma collections.

Validate and insert the finished artifacts into ChromaDB:

```bash
python -m Ingestion.embeddings.validate_embeddings
python -m Ingestion.vectordb.insert_text
python -m Ingestion.vectordb.insert_images
python -m Ingestion.vectordb.verify_db
```

Text uses inner-product distance to match the MedCPT manifest. Images use
cosine distance to match normalized BiomedCLIP vectors. Both insertion commands
checkpoint after each batch and safely resume when the same command is rerun.
