# ATAC-seq SRX collector (multi-species, recent years)

This project collects ATAC-seq experiments (SRX) from ENA for a given species list and a start date, and attaches PubMed paper info. Defaults:
- Start date: 2022-01-01 (inclusive)
- Include scATAC: true
- Only keep studies with PubMed IDs: true
- Strict `library_strategy="ATAC-seq"`

Data sources:
- ENA portal API (read_experiment + study)
- PubMed E-utilities for paper titles

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ATAC_START_DATE=2022-01-01
export INCLUDE_SCATAC=true
export ONLY_PUBLISHED=true
export SPECIES_FILE=data/species_list.txt
export OUTPUT_CSV=out/atac_srx_with_pubmed.csv
# Optional (recommended for higher rate limits)
# export NCBI_API_KEY=your_api_key
# export NCBI_EMAIL=you@example.com

python scripts/fetch_atac_srx_from_ena.py
```

Output CSV columns:
- species, SRX, SRP, first_public, library_strategy, library_source, library_selection, instrument_platform, instrument_model, experiment_title, sample_accession, pubmed_ids, pubmed_titles, study_title

## Run via GitHub Actions

1. Add the repository secrets (recommended):
   - `NCBI_API_KEY`, `NCBI_EMAIL`
2. Go to Actions -> "Fetch recent ATAC SRX" -> Run workflow, accept defaults or adjust inputs.
3. Download the artifact `atac_srx_with_pubmed` to get the CSV, or find it committed under `out/atac_srx_with_pubmed.csv`。

## Notes

- The query uses `tax_eq("Species name")` and strict `library_strategy="ATAC-seq"`. This maximizes accuracy but can miss mis-annotated entries.
- The time filter uses ENA `first_public >= start_date`.
- PubMed titles come from E-utilities `esummary`. If multiple PMIDs are attached to a study, they are all included.
