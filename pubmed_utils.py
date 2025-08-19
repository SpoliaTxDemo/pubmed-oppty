"""Utility functions for searching PubMed via Entrez and processing results.

This module provides helper functions to build search queries, perform
ESearch and EFetch calls to the NCBI Entrez API, and format the results
into plain text suitable for export or further analysis. The default
disease terms include several categories of rare metabolic disorders.
"""

from __future__ import annotations

import os
import datetime
from typing import List, Dict
from Bio import Entrez, Medline

__all__ = [
    "RARE_METABOLIC_DEFAULT_TERMS",
    "build_query",
    "esearch_pmids",
    "efetch_medline",
    "to_txt",
]


RARE_METABOLIC_DEFAULT_TERMS: List[str] = [
    "inborn errors of metabolism",
    "lysosomal storage disease",
    "mitochondrial disorder",
    "peroxisomal disorder",
    "rare metabolic disorder",
]


def _entrez_init() -> None:
    Entrez.email = os.getenv("NCBI_EMAIL", "you@example.com")
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        Entrez.api_key = api_key


def build_query(affiliations: List[str], disease_terms: List[str], custom_terms: str = "") -> str:
    aff_q_parts: List[str] = []
    for a in affiliations:
        a = a.strip()
        if a:
            aff_q_parts.append(f'"{a}"[ad]')

    terms: List[str] = [t.strip() for t in disease_terms if t.strip()]
    if custom_terms.strip():
        terms.append(custom_terms.strip())

    query_parts: List[str] = []
    if aff_q_parts:
        query_parts.append("(" + " OR ".join(aff_q_parts) + ")")
    if terms:
        quoted_terms = [f'"{t}"' for t in terms]
        query_parts.append("(" + " OR ".join(quoted_terms) + ")")

    return " AND ".join(query_parts)


def esearch_pmids(query: str, retmax: int = 100, min_year: int = 2005) -> List[str]:
    if not query:
        return []
    _entrez_init()
    today = datetime.date.today().strftime("%Y/%m/%d")
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=retmax,
        datetype="pdat",
        mindate=f"{min_year}/01/01",
        maxdate=today,
    )
    record = Entrez.read(handle)
    return record.get("IdList", [])


def efetch_medline(pmids: List[str]) -> List[Dict]:
    if not pmids:
        return []
    _entrez_init()
    handle = Entrez.efetch(
        db="pubmed",
        id=",".join(pmids),
        rettype="medline",
        retmode="text",
    )
    records = list(Medline.parse(handle))
    result: List[Dict] = []
    for rec in records:
        authors = rec.get("AU", [])
        affiliations = rec.get("AD", [])
        if isinstance(affiliations, str):
            affiliations = [affiliations]

        author_info = []
        for i, name in enumerate(authors):
            affil = affiliations[i] if i < len(affiliations) else ""
            author_info.append((name, affil))

        result.append(
            {
                "pmid": rec.get("PMID", ""),
                "title": rec.get("TI", ""),
                "journal": rec.get("JT", ""),
                "pubdate": rec.get("DP", ""),
                "authors": author_info,
                "abstract": rec.get("AB", ""),
                "doi": next(
                    (
                        aid.split()[0]
                        for aid in rec.get("AID", [])
                        if "doi" in aid.lower()
                    ),
                    "",
                ),
            }
        )
    return result


def to_txt(records: List[Dict]) -> str:
    LARGE_PHARMA = ["Novartis", "Roche"]
    lines: List[str] = []

    for idx, rec in enumerate(records, 1):
        lines.append(f"## {idx}. {rec['title']}")
        lines.append(
            f"Journal: {rec['journal']} | PubDate: {rec['pubdate']} | PMID: {rec['pmid']} | DOI: {rec['doi']}"
        )

        author_strs = []
        for name, affil in rec["authors"]:
            match = next((pharma for pharma in LARGE_PHARMA if pharma.lower() in affil.lower()), None)
            if match:
                formatted = f"**{name}** ({affil})"
            else:
                formatted = name
            author_strs.append(formatted)

        if author_strs:
            lines.append("Authors: " + "; ".join(author_strs))
        lines.append("Abstract:")
        lines.append(rec["abstract"] or "(no abstract)")
        lines.append("")

    return "\n".join(lines)
