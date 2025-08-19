# pubmed_utils.py
# Utilities for building PubMed queries, fetching records, and formatting output.
# Dependencies: biopython (Entrez/Medline)
#   pip install biopython

from __future__ import annotations

from typing import Iterable, List, Dict, Any, Tuple, Pattern
from dataclasses import dataclass  # (import ok even if unused)
import re
from Bio import Entrez, Medline

# ---------------------------------------------
# Public constants (importable by the Flask UI)
# ---------------------------------------------
TOP_20_PHARMA: List[str] = [
    "Pfizer",
    "Novartis",
    "Roche",
    "Merck",
    "GSK",
    "Sanofi",
    "AstraZeneca",
    "Johnson & Johnson",
    "AbbVie",
    "Amgen",
    "Bristol Myers Squibb",
    "Eli Lilly",
    "Takeda",
    "Bayer",
    "Boehringer Ingelheim",
    "Novo Nordisk",
    "Gilead",
    "Moderna",
    "Regeneron",
    "Vertex",
]

# A small default set; extend as you wish.
RARE_METABOLIC_DEFAULT_TERMS: List[str] = [
    "Niemann-Pick type C",
    "Gaucher disease",
    "Fabry disease",
    "Pompe disease",
    "MPS I",
]

# ---------------------------------------------
# Stricter pharma affiliation detection
# ---------------------------------------------
COMPANY_INDICATORS = re.compile(
    r"\b(inc|inc\.|incorporated|ltd|limited|llc|ag|gmbh|s\.?a\.?|sas|plc|company|"
    r"pharma\w*|pharmaceutical\w*|diagnostics|biotech|research|holding|group)\b",
    re.I,
)

PHARMA_REGEX: List[Tuple[Pattern[str], str]] = [
    # Canonical matches
    (re.compile(r"\bpfizer\b|\bpfizer\s+inc\b", re.I), "Pfizer"),
    (re.compile(r"\bnovartis\b", re.I), "Novartis"),
    (re.compile(r"\bmerck\b|\bmsd\b|merck\s+sharp\s*&\s*doh\w*|\bmerck\s+kga?a?\b", re.I), "Merck"),
    (re.compile(r"glaxo\w*smith\w*|\bgsk\b", re.I), "GSK"),
    (re.compile(r"\bsanofi\b", re.I), "Sanofi"),
    (re.compile(r"astra\s*zeneca", re.I), "AstraZeneca"),
    (re.compile(r"johnson\s*&\s*johnson|\bj&j\b|\bjanssen\b", re.I), "J&J"),

    # Roche: require company context; avoid French place names (handled separately)
    (re.compile(r"f\.?\s*hoffmann[-\s]*la[-\s]*roche", re.I), "Roche"),
    (re.compile(r"\broche\s+diagnostics\b", re.I), "Roche"),
    (re.compile(r"\broche\s+(pharma\w*|holding|group)\b", re.I), "Roche"),
    (re.compile(r"\broche\s+(ag|gmbh|s\.?a\.?|sas|plc|ltd\.?|inc\.)\b", re.I), "Roche"),
    (re.compile(r"\bgenentech\b", re.I), "Roche"),

    # Other large companies
    (re.compile(r"\babbvie\b", re.I), "AbbVie"),
    (re.compile(r"\bamgen\b", re.I), "Amgen"),
    (re.compile(r"bristol\s+myers\s+squibb|\bbms\b", re.I), "Bristol Myers Squibb"),
    (re.compile(r"eli\s+lilly|\blilly\b", re.I), "Eli Lilly"),
    (re.compile(r"\btakeda\b", re.I), "Takeda"),
    (re.compile(r"\bbayer\b", re.I), "Bayer"),
    (re.compile(r"boehringer\s+ingelheim", re.I), "Boehringer Ingelheim"),
    (re.compile(r"novo\s+nordisk", re.I), "Novo Nordisk"),
    (re.compile(r"\bgilead\b", re.I), "Gilead"),
    (re.compile(r"\bmoderna\b", re.I), "Moderna"),
    (re.compile(r"\bregeneron\b", re.I), "Regeneron"),
    (re.compile(r"\bvertex\b", re.I), "Vertex"),
]

def normalize_affiliation(affil: str | None) -> str | None:
    """
    Return canonical short pharma name if affiliation looks like a company; else None.
    Avoids false positives like French toponyms (e.g., "La Roche-Guyon Hospital").
    """
    if not affil:
        return None
    clean = affil.strip()

    # If it's a La Roche toponym and *no* company indicator, do not match
    if re.search(r"\bla\s+roche\b", clean, flags=re.I) and not COMPANY_INDICATORS.search(clean):
        return None

    for rx, short in PHARMA_REGEX:
        if rx.search(clean):
            return short
    return None

# ---------------------------------------------
# Query building
# ---------------------------------------------
def build_query(affiliations: List[str], disease_terms: List[str], custom_terms: str = "") -> str:
    """
    Build a PubMed query.
    - affiliations: list of company names → searched in Affiliation field [AD]
    - disease_terms: list of disease terms → searched in Title/Abstract
    - custom_terms: comma-separated extra Title/Abstract terms
    """
    parts: List[str] = []

    aff_parts = [f'"{a}"[AD]' for a in affiliations if a and a.strip()]
    if aff_parts:
        parts.append("(" + " OR ".join(aff_parts) + ")")

    dt_parts = [f'({t})[Title/Abstract]' for t in disease_terms if t and t.strip()]
    if dt_parts:
        parts.append("(" + " OR ".join(dt_parts) + ")")

    if custom_terms:
        extras = [s.strip() for s in custom_terms.split(",") if s.strip()]
        if extras:
            parts.append("(" + " OR ".join(f'({e})[Title/Abstract]' for e in extras) + ")")

    if not parts:
        parts.append("all[filter]")

    return " AND ".join(parts)

# ---------------------------------------------
# Entrez helpers
# ---------------------------------------------
def esearch_pmids(query: str, retmax: int = 100, min_year: int | None = None) -> List[str]:
    """Run Entrez.esearch and return a list of PMIDs (strings)."""
    params: Dict[str, Any] = {"db": "pubmed", "term": query, "retmax": retmax, "retmode": "xml"}
    if min_year:
        params.update({"mindate": str(min_year), "datetype": "pdat"})
    handle = Entrez.esearch(**params)
    data = Entrez.read(handle)
    handle.close()
    return list(data.get("IdList", []))

def efetch_medline(pmids: Iterable[str]) -> List[Dict[str, Any]]:
    """
    Fetch MEDLINE records and return a simplified list of dicts with normalized authors.
    We attempt to construct per-author (name, affiliation) tuples when possible.
    """
    ids = ",".join(pmids)
    if not ids:
        return []
    handle = Entrez.efetch(db="pubmed", id=ids, rettype="medline", retmode="text")
    records = list(Medline.parse(handle))
    handle.close()

    out: List[Dict[str, Any]] = []
    for rec in records:
        # Title / Journal / Date / PMID / DOI
        title = rec.get("TI") or rec.get("JT") or ""
        journal = rec.get("JT") or rec.get("TA") or ""
        date = rec.get("DP") or ""
        pmid = rec.get("PMID") or ""
        doi = None
        for aid in rec.get("AID", []) or []:
            if aid and "[doi]" in aid.lower():
                doi = aid.split(" ")[0]
                break

        # Authors & affiliations
        au = rec.get("AU", []) or []  # list of names
        fa = rec.get("FAU", []) or []  # full author names
        ad = rec.get("AD", []) or []   # affiliations (can be many, not reliably aligned)

        authors: List[Tuple[str, str | None]] = []
        names = fa or au
        ad_list = [ad] if isinstance(ad, str) else list(ad)

        if names and ad_list and len(names) == len(ad_list):
            authors = [(n, a) for n, a in zip(names, ad_list)]
        else:
            authors = [(n, None) for n in names]

        out.append(
            {
                "title": title,
                "journal": journal,
                "date": date,
                "pmid": pmid,
                "doi": doi,
                "authors": authors,
                "raw": rec,
            }
        )
    return out

# ---------------------------------------------
# Formatting helpers
# ---------------------------------------------
def _format_single_author(name: str, affil: str | None) -> str:
    name = (name or "").strip()
    company = normalize_affiliation(affil)
    if company:
        return f"**{name}** ({company})"
    return name

def to_txt(records: List[Dict[str, Any]]) -> str:
    """
    Convert fetched records into a readable text blob suitable for export/download.
    Authors with large-pharma affiliations are **bolded** and followed by (Company).
    Others are printed name-only (no affiliation).
    """
    lines: List[str] = []
    for r in records:
        title = r.get("title", "").strip()
        journal = r.get("journal", "").strip()
        date = r.get("date", "").strip()
        pmid = r.get("pmid", "").strip()
        doi = r.get("doi")

        lines.append(f"{title}")
        head_parts = [journal, date, f"PMID {pmid}"]
        if doi:
            head_parts.append(f"DOI {doi}")
        head = " | ".join([p for p in head_parts if p])
        if head:
            lines.append(head)

        author_strs: List[str] = []
        for item in r.get("authors", []) or []:
            if isinstance(item, (list, tuple)) and len(item) >= 1:
                nm = str(item[0])
                af = str(item[1]) if len(item) > 1 and item[1] is not None else None
                author_strs.append(_format_single_author(nm, af))
            else:
                nm = str(item)
                author_strs.append(_format_single_author(nm, None))
        if author_strs:
            lines.append("Authors: " + "; ".join(author_strs))

        ab = r.get("raw", {}).get("AB") if isinstance(r.get("raw"), dict) else None
        if ab:
            lines.append("Abstract")
            lines.append(ab.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"
