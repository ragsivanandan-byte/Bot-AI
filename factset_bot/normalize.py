"""Text normalization helpers for robust name/company comparison."""
from __future__ import annotations

import re
import unicodedata

_SUFFIXES = (
    " inc", " inc.", " llc", " llc.", " ltd", " ltd.", " limited",
    " corp", " corp.", " corporation", " co", " co.", " company",
    " sa", " s.a.", " s.a", " sas", " sarl", " gmbh", " ag", " plc",
    " s.p.a.", " spa", " nv", " bv", " oy", " ab", " kk",
    " group", " holdings", " holding",
)


def normalize_company(name: str | None) -> str:
    """Normalize a company name for equality comparison.

    Strips accents, punctuation, common legal suffixes, and case.
    Two names normalizing to the same string are treated as the same employer.
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"[.,]", "", text)
    text = re.sub(r"\s+", " ", text)
    for _ in range(2):
        for suffix in _SUFFIXES:
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
    return text


def split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.strip().split() if p]
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])
