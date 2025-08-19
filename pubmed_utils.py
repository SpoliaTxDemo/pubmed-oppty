# pubmed_utils.py
# Utilities for building PubMed queries, fetching records, and formatting output.
# Dependencies: biopython (Entrez/Medline)
#   pip install biopython

from __future__ import annotations

from typing import Iterable, List, Dict, Any, Tuple, Pattern
import re
from Bio import Entrez, Medline

# ---------------------------------------------
# Public constants (importable by the Flask UI)
# ---------------------------------------------
TOP_20_PHARMA: List[str] = [
    "Pfizer", "Novartis", "Roche", "Merck", "GSK", "Sanofi", "AstraZeneca", "Johnson & Johnson",
    "AbbVie", "Amgen", "Bristol Myers Squibb", "Eli Lilly", "Takeda", "Bayer",
    "Boehringer Ingelheim", "Novo Nordisk", "Gilead", "Moderna", "Regeneron", "Vertex",
]

# A small default set; extend as you wish.
RARE_METABOLIC_DEFAULT_TERMS: List[str] = [
    "Niemann-Pick type C", "Gaucher disease", "Fabry disease", "Pompe disease", "MPS I",
]

# ---------------------------------------------
# Stricter pharma affiliation detection (for exports)
# ---------------------------------------------
COMPANY_INDICATORS = re.compile(
    r"\b(inc|inc\.|incorporated|ltd|limited|llc|ag|gmbh|s\.?a\.?|sas|plc|company|"
    r"pharma\w*|pharmaceutical\w*|diagnostics|biotech|research|holding|group)\b",
    re.I,
)

PHARMA_REGEX: List[Tuple[Pattern[str], str]] = [
    (re.compile(r"\bpfizer\b|\bpfizer\s+inc\b", re.I), "Pfizer"),
    (re.compile(r"\bnovartis\b", re.I), "Novartis"),
    (re.compile(r"\bmerck\b|\bmsd\b|merck\s+sharp\s*&\s*doh\w*|\bmerck\s+kga?a?\b", re.I), "Merck"),
    (re.compile(r"glaxo\w*smith\w*|\bgsk\b", re.I), "GSK"),
    (re.compile(r"\bsanofi\b", re.I), "Sanofi"),
    (re.compile(r"astra\s*zeneca", re.I), "AstraZeneca"),
    (re.compile(r"johnson\s*&\s*johnson|\bj&j\b|\bjanssen\b", re.I), "J&J"),
    # Roche: require company context; avoid place names
    (re.compile(r"f\.?\s*hoffmann[-\s]*la[-\s]*roche", re.I), "Roche"),
    (re.compile(r"\broche\s+diagnostics\b", re.I), "Roche"),
    (re.compile(r"\broche\s+(pharma\w*|holding|group)\b", re.I), "Roche"),
    (re.compile(r"\broche\s+(ag|gmbh|s\.?a\.?|sas|plc|ltd\.?|inc\.)\b", re.I), "Roche"),
    (re.compile(r"\bgenentech\b", re.I), "Roche"),
    # Others
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
    """Return canonical short pharma name if affiliation looks like a company; else None.
    Avoids false positives like 'La Roche-Guyon Hospital' (no company indicators)."""
    if not affil:
        return None
    clean = affil.strip()
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
    """Build a PubMed query:
      - affiliations: company names searched in Affiliation field [AD]
      - disease_terms: in Title/Abstract
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
# Entrez helpers — BACKWARD-COMPATIBLE SHAPE
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
    """Fetch MEDLINE records and return a list of dicts with fields your templates expect:
       title, journal, date, pmid, doi, authors (list[str]), affiliations (list[str]),
       abstract (str), plus raw (full Medline dict).
       Also provide aliases AU (authors), AD (affiliations), AB (abstract) for compatibility.
    """
    ids = ",".join(pmids)
    if not ids:
        return []
    handle = Entrez.efetch(db="pubmed", id=ids, rettype="medline", retmode="text")
    records = list(Medline.parse(handle))
    handle.close()

    out: List[Dict[str, Any]] = []
    for rec in records:
        title = rec.get("TI") or ""
        journal = rec.get("JT") or rec.get("TA") or ""
        date = rec.get("DP") or ""
        pmid = rec.get("PMID") or ""

        # DOI
        doi = None
        for aid in rec.get("AID", []) or []:
            if isinstance(aid, str) and "[doi]" in aid.lower():
                doi = aid.split(" ")[0]
                break

        # Authors & affiliations (keep as simple lists, no per-author tuples)
        authors: List[str] = list(rec.get("FAU") or rec.get("AU") or [])
        affiliations_raw = rec.get("AD", [])
        if isinstance(affiliations_raw, str):
            affiliations = [affiliations_raw]
        else:
            affiliations = list(affiliations_raw or [])

        # Abstract: Medline gives a single string under "AB"
        abstract = rec.get("AB") or ""

        item: Dict[str, Any] = {
            "title": title,
            "journal": journal,
            "date": date,
            "pmid": pmid,
            "doi": doi,
            "authors": authors,          # <- list[str], template-friendly
            "affiliations": affiliations, # <- list[str]
            "abstract": abstract,        # <- string
            "raw": rec,                  # full record for any advanced use
            # Aliases for backward compatibility if templates reference Medline keys:
            "AU": authors,
            "AD": affiliations,
            "AB": abstract,
        }
        out.append(item)
    return out

# ---------------------------------------------
# Formatting for export (text file)
# ---------------------------------------------
def _format_single_author(name: str, affil: str | None) -> str:
    name = (name or "").strip()
    company = normalize_affiliation(affil)
    if company:
        return f"**{name}** ({company})"
    return name

def to_txt(records: List[Dict[str, Any]]) -> str:
    """Convert fetched records into a readable text blob for download.
    - Authors with large-pharma affiliations are **bolded** with (Company).
    - Others: name only. If we can’t align authors↔affiliations, we print names only (safe).
    """
    lines: List[str] = []
    for r in records:
        title = (r.get("title") or "").strip()
        journal = (r.get("journal") or "").strip()
        date = (r.get("date") or "").strip()
        pmid = (r.get("pmid") or "").strip()
        doi = r.get("doi") or None
        authors: List[str] = r.get("authors") or []
        affiliations: List[str] = r.get("affiliations") or []

        lines.append(title)
        head = " | ".join([p for p in [journal, date, f"PMID {pmid}", f"DOI {doi}" if doi else None] if p])
        if head:
            lines.append(head)

        # Try to align authors with affiliations if counts match; else fall back to name-only
        author_strs: List[str] = []
        if authors and affiliations and len(authors) == len(affiliations):
            for nm, af in zip(authors, affiliations):
                author_strs.append(_format_single_author(nm, af))
        else:
            # No reliable alignment → do not guess; show names only
            for nm in authors:
                author_strs.append(_format_single_author(nm, None))
        if author_strs:
            lines.append("Authors: " + "; ".join(author_strs))

        abstract = (r.get("abstract") or "").strip()
        if abstract:
            lines.append("Abstract")
            lines.append(abstract)

        lines.append("")  # spacer between records

    return "\n".join(lines).strip() + "\n"
