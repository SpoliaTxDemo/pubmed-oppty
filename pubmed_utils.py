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


# Predefined list of terms for rare metabolic diseases
RARE_METABOLIC_DEFAULT_TERMS: List[str] = [
    "inborn errors of metabolism",
    "lysosomal storage disease",
    "mitochondrial disorder",
    "peroxisomal disorder",
    "rare metabolic disorder",
]


def _entrez_init() -> None:
    """Initialize global settings for the Entrez API.

    Sets the email and optional API key from environment variables. The email is
    required by NCBI for API usage. Providing an API key will increase
    the rate limits for requests.
    """

    Entrez.email = os.getenv("NCBI_EMAIL", "you@example.com")
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        Entrez.api_key = api_key


def build_query(affiliations: List[str], disease_terms: List[str], custom_terms: str = "") -> str:
    """Construct a PubMed search query.

    Parameters
    ----------
    affiliations : List[str]
        List of organization names to search in the author affiliation field.
    disease_terms : List[str]
        List of disease-related phrases to search in titles/abstracts.
    custom_terms : str, optional
        Additional terms provided by the user, to include in the query.

    Returns
    -------
    str
        A PubMed query string combining affiliation and disease term filters.
    """

    # Build affiliation query using [ad] field tag
    aff_q_parts: List[str] = []
    for a in affiliations:
        a = a.strip()
        if a:
            aff_q_parts.append(f'"{a}"[ad]')

    # Consolidate disease terms and custom terms
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
    """Execute an ESearch query on PubMed and return a list of PMIDs.

    Parameters
    ----------
    query : str
        The search query string.
    retmax : int, default 100
        Maximum number of PMIDs to return.
    min_year : int, default 2005
        Minimum publication year for filtering results.

    Returns
    -------
    List[str]
        A list of PubMed IDs (PMIDs) matching the query.
    """

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
    """Retrieve MEDLINE records for the given PMIDs.

    Parameters
    ----------
    pmids : List[str]
        List of PubMed IDs to retrieve.

    Returns
    -------
    List[Dict]
        A list of dictionaries containing relevant fields from each record.
    """

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
        result.append(
            {
                "pmid": rec.get("PMID", ""),
                "title": rec.get("TI", ""),
                "journal": rec.get("JT", ""),
                "pubdate": rec.get("DP", ""),
                "authors": rec.get("AU", []),
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
    """Convert a list of record dictionaries into a plain text string.

    Each record is formatted with a simple header, citation details, and the
    abstract. The output is meant for easy display or file export.

    Parameters
    ----------
    records : List[Dict]
        List of record dictionaries from efetch_medline.

    Returns
    -------
    str
        The concatenated text of all records.
    """

    lines: List[str] = []
    for idx, rec in enumerate(records, 1):
        lines.append(f"## {idx}. {rec['title']}")
        lines.append(
            f"Journal: {rec['journal']} | PubDate: {rec['pubdate']} | PMID: {rec['pmid']} | DOI: {rec['doi']}"
        )
        if rec["authors"]:
            lines.append("Authors: " + "; ".join(rec["authors"]))
        lines.append("Abstract:")
        lines.append(rec["abstract"] or "(no abstract)")
        lines.append("")
    return "\n".join(lines)