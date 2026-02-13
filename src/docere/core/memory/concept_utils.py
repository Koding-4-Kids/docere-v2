"""Concept name normalization utilities."""

import re

_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_ACTION_PREFIX_RE = re.compile(
    r"^(understanding|solving|taking|computing|calculating|finding|using|applying|learning|studying)\s+",
    re.IGNORECASE,
)


def normalize_concept(name: str) -> str:
    """Canonicalize a concept name: strip articles/action prefixes, depluralize, lowercase."""
    name = name.strip().lower()
    name = _ARTICLE_RE.sub("", name)
    name = _ACTION_PREFIX_RE.sub("", name)
    name = name.strip()
    # Simple depluralization: trailing 's' for words > 4 chars (avoids "gas" → "ga")
    if len(name) > 4 and name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)
    return name
