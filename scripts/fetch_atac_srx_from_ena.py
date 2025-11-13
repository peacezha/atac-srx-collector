name: Fetch recent ATAC SRX

on:
  workflow_dispatch:
    inputs:
      start_date:
        description: "Start date (YYYY-MM-DD)"
        required: true
        default: "2022-01-01"
      include_scatac:
        description: "Include single-cell ATAC"
        required: true
        default: "true"
      only_published:
        description: "Only keep entries with PubMed IDs"
        required: true
        default: "true"
      species_file:
        description: "Path to species list file"
        required: true
        default: "data/species_list.txt"
  push:
    branches:
      - main
    paths:
      - "scripts/**"
      - "data/**"
      - "requirements.txt"
      - ".github/workflows/fetch-atac.yml"
      - "README.md"

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Syntax check
        run: |
          python -m py_compile scripts/fetch_atac_srx_from_ena.py

      - name: Run fetcher
        env:
          ATAC_START_DATE: ${{ github.event.inputs.start_date || '2022-01-01' }}
          INCLUDE_SCATAC: ${{ github.event.inputs.include_scatac || 'true' }}
          ONLY_PUBLISHED: ${{ github.event.inputs.only_published || 'true' }}
          SPECIES_FILE: ${{ github.event。inputs.species_file || 'data/species_list.txt' }}
          OUTPUT_CSV: out/atac_srx_with_pubmed.csv
          NCBI_API_KEY: ${{ secrets.NCBI_API_KEY }}
          NCBI_EMAIL: ${{ secrets.NCBI_EMAIL }}
        run: |
          mkdir -p out
          python scripts/fetch_atac_srx_from_ena.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: atac_srx_with_pubmed
          path: out/atac_srx_with_pubmed.csv

      - name: Commit CSV back to repo (optional)
        if: ${{ github.ref == 'refs/heads/main' || github.ref == 'refs/heads/master' }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -f out/atac_srx_with_pubmed.csv || true
          git commit -m "Update ATAC SRX table (auto)" || echo "Nothing to commit"
          git push || true
