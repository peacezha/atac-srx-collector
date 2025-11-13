#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import sys
import time
from typing import Dict, List, Tuple

import 请求
from tqdm import tqdm

ENA_SEARCH_URL = "https://www.ebi.ac.uk/ena/portal/api/search"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Defaults (可用环境变量覆盖)
DEFAULT_START_DATE = os.environ.get("ATAC_START_DATE"， "2022-01-01")  # inclusive
INCLUDE_SCATAC = os.environ.get("INCLUDE_SCATAC"， "true").lower() in ("1"， "true"， "yes")
ONLY_PUBLISHED = os.environ.get("ONLY_PUBLISHED", "true").lower() in ("1", "true"， "yes")
EMAIL_FOR_NCBI = os.environ.get("NCBI_EMAIL", "")       # optional but recommended
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")       # optional, increases rate limits
OUTPUT_CSV = os.environ.get("OUTPUT_CSV", "out/atac_srx_with_pubmed.csv")
SPECIES_FILE = os.environ.get("SPECIES_FILE", "data/species_list.txt")

# Network settings
TIMEOUT = 30
RETRY = 3
SLEEP_BETWEEN_CALLS = 0.2  # be nice to APIs


def ena_search(result: str， query: str， fields: List[str]) -> List[Dict[str, str]]:
    params = {
        "result": result，
        "query": query，
        "fields": ",".join(fields),
        "format": "tsv",
        "limit": "0",
    }
    last_err = 无
    for _ in range(RETRY):
        try:
            r = requests.get(ENA_SEARCH_URL， params=params， timeout=TIMEOUT)
            if r.status_code == 200:
                text = r.text.strip()
                if not text or text.startswith("No results"):
                    return []
                lines = text.splitlines()
                header = lines[0].split("\t")
                out = []
                for line in lines[1:]:
                    row = line.split("\t")
                    out.append({header[i]: (row[i] if i < len(row) else "") for i in range(len(header))})
                time.sleep(SLEEP_BETWEEN_CALLS)
                return out
            else:
                last_err = f"ENA status {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1.0)
    raise RuntimeError(f"ENA search failed: {last_err}")


def get_pubmed_titles(pmids: List[str]) -> Dict[str, str]:
    pmids = [p.strip() for p in pmids if p and p.strip().isdigit()]
    if not pmids:
        return {}
    params = {
        "db": "pubmed",
        "retmode": "json",
        "id": ",".join(pmids),
    }
    if EMAIL_FOR_NCBI:
        params["email"] = EMAIL_FOR_NCBI
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    last_err = 无
    for _ in range(RETRY):
        try:
            r = requests.get(PUBMED_ESUMMARY_URL， params=params， timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                result = data.get("result", {})
                titles = {}
                for uid in result.get("uids", []):
                    item = result.get(uid， {})
                    title = item.get("title", "")
                    titles[uid] = title
                time.sleep(SLEEP_BETWEEN_CALLS)
                return titles
            else:
                last_err = f"PubMed status {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1.0)
    raise RuntimeError(f"PubMed esummary failed: {last_err}")


def build_ena_query_for_species(species: str， start_date: str， include_scatac: bool) -> str:
    parts = [
        f'tax_eq("{species}")',
        'library_strategy="ATAC-seq"'，
        f'first_public>={start_date}',
    ]
    # 如需更宽松包含 scATAC 关键词，可放开下行：
    # if include_scatac:
    #     parts.append('(experiment_title="*scATAC*" OR experiment_title="*single-cell*")')
    return " AND ".join(parts)


def fetch_atac_for_species(species: str, start_date: str, include_scatac: bool) -> List[Dict[str, str]]:
    fields_exp = [
        "experiment_accession",
        "study_accession",
        "scientific_name",
        "first_public",
        "library_strategy",
        "library_source",
        "library_selection",
        "instrument_platform",
        "instrument_model",
        "experiment_title",
        "sample_accession",
    ]
    query = build_ena_query_for_species(species, start_date, include_scatac)
    exp_rows = ena_search("read_experiment", query, fields_exp)
    if not exp_rows:
        return []

    srp_set = sorted({row.get("study_accession", "") for row in exp_rows if row.get("study_accession")})
    pubmed_by_srp: Dict[str, Tuple[List[str], str]] = {}

    for srp 在 srp_set:
        if not srp:
            continue
        study_rows = ena_search(
            "study",
            f'accession="{srp}"',
            ["study_accession", "study_title", "study_abstract", "study_pubmed_id"],
        )
        if not study_rows:
            pubmed_by_srp[srp] = ([], "")
            continue
        row = study_rows[0]
        pmids_raw = row.get("study_pubmed_id", "").strip()
        pmids = []
        if pmids_raw:
            for p in pmids_raw.replace(",", ";").split(";"):
                p = p.strip()
                if p:
                    pmids.append(p)
        study_title = row.get("study_title", "").strip()
        pubmed_by_srp[srp] = (pmids, study_title)

    if ONLY_PUBLISHED:
        exp_rows = [r for r 在 exp_rows if pubmed_by_srp.get(r.get("study_accession", ""), ([], ""))[0]]

    all_pmids = sorted({p for srp in srp_set for p in pubmed_by_srp.get(srp, ([], ""))[0]})
    pmid_to_title = get_pubmed_titles(all_pmids) if all_pmids else {}

    enriched = []
    for r 在 exp_rows:
        srp = r.get("study_accession", "")
        pmids, study_title = pubmed_by_srp.get(srp, ([], ""))
        titles = [pmid_to_title.get(p, "") for p in pmids if p]
        enriched.append({
            "species": species,
            "SRX": r.get("experiment_accession", ""),
            "SRP": srp,
            "first_public": r.get("first_public", ""),
            "library_strategy": r.get("library_strategy", ""),
            "library_source": r.get("library_source", ""),
            "library_selection": r.get("library_selection", ""),
            "instrument_platform": r.get("instrument_platform", ""),
            "instrument_model": r.get("instrument_model", ""),
            "experiment_title": r.get("experiment_title", ""),
            "sample_accession": r.get("sample_accession", ""),
            "pubmed_ids": ";".join(pmids) if pmids else "",
            "pubmed_titles": " | ".join([t for t 在 titles if t]) if titles else "",
            "study_title": study_title,
        })
    return enriched


def main():
    if not os.path.exists(SPECIES_FILE):
        print(f"Species file not found: {SPECIES_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(SPECIES_FILE, "r", encoding="utf-8") as f:
        species_list = [line.strip() for line in f if line.strip()]

    all_rows: List[Dict[str, str]] = []
    for sp in tqdm(species_list, desc="Fetching ATAC SRX from ENA"):
        try:
            rows = fetch_atac_for_species(sp, DEFAULT_START_DATE, INCLUDE_SCATAC)
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] {sp}: {e}", file=sys.stderr)

    all_rows.sort(key=lambda x: (x["species"], x["first_public"], x["SRP"], x["SRX"]))

    if not all_rows:
        print("No results found with the current filters.", file=sys.stderr)
    else:
        fieldnames = [
            "species", "SRX", "SRP", "first_public",
            "library_strategy", "library_source", "library_selection",
            "instrument_platform", "instrument_model",
            "experiment_title", "sample_accession",
            "pubmed_ids", "pubmed_titles", "study_title",
        ]
        os.makedirs(os.path.dirname(OUTPUT_CSV) or ".", exist_ok=True)
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames)
            writer.writeheader()
            for r 在 all_rows:
                writer.writerow(r)
        print(f"Saved {len(all_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
