# pubmed_utils.py
# Utilities for building PubMed queries, fetching records, and formatting output.
# Dependencies: biopython (Entrez/Medline)
# pip install biopython
# Be sure to configure Entrez.email (and optionally Entrez.api_key) in your app init.


from __future__ import annotations


from typing import Iterable, List, Dict, Any, Tuple
from dataclasses import dataclass
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


PHARMA_REGEX: List[Tuple[re.Pattern[str], str]] = [
# Canonical matches
(re.compile(r"\bpfizer\b|\bpfizer\s+inc\b", re.I), "Pfizer"),
(re.compile(r"\bnovartis\b", re.I), "Novartis"),
(re.compile(r"\bmerck\b|\bmsd\b|merck\s+sharp\s*&\s*doh\w*|merck\s*kga?a?\b", re.I), "Merck"),
(re.compile(r"glaxo\w*smith\w*|\bgsk\b", re.I), "GSK"),
(re.compile(r"\bsanofi\b", re.I), "Sanofi"),
(re.compile(r"astra\s*zeneca", re.I), "AstraZeneca"),
(re.compile(r"johnson\s*&\s*johnson|\bj&j\b|\bjanssen\b", re.I), "J&J"),
# Roche: require company context; avoid French place names
(re.compile(r"f\.?\s*hoffmann[-\s]*la[-\s]*roche", re.I), "Roche"),
(re.compile(r"roche\s+diagnostics", re.I), "Roche"),
(re.compile(r"roche\s+(pharma\w*|holding|group)\b", re.I), "Roche"),
(re.compile(r"roche\s+(ag|gmbh|s\.?a\.?|sas|plc|ltd\.?|inc\.)\b", re.I), "Roche"),
(re.compile(r"\bgenentech\b", re.I), "Roche"),
# Common large caps (expand as needed)
(re.compile(r"\babbvie\b", re.I), "AbbVie"),
(re.compile(r"\bamgen\b", re.I), "Amgen"),
(re.compile(r"bristol\s+myers\s+squibb|\bbms\b", re.I), "Bristol Myers Squibb"),
(re.compile(r"eli\s+lilly|\blilly\b", re.I), "Eli Lilly"),
return "\n".join(lines).strip() + "\n"
