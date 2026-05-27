"""PHI rule registry — loads data/deid-rules.json once and exposes lookups."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

Severity = Literal["high", "medium"]
TagName = str


def _rules_path() -> Path:
    import os

    override = os.environ.get("DEID_RULES_PATH")
    if override:
        return Path(override)

    # services/api-service/app/deid/rules.py
    # parents[0]=deid  [1]=app  [2]=api-service  [3]=services  [4]=<repo root>
    here = Path(__file__).resolve()
    repo_root = here.parents[4]
    candidate = repo_root / "data" / "deid-rules.json"
    if candidate.exists():
        return candidate

    return Path("/app/data/deid-rules.json")


@lru_cache(maxsize=1)
def load_rules() -> dict:
    """Read the JSON rule file. Cached for the process lifetime."""
    path = _rules_path()
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_index(items: list[dict]) -> dict[str, str]:
    return {entry["tag"]: entry["name"] for entry in items}


_rules = load_rules()
HIGH_SEVERITY_TAGS: dict[str, str] = _build_index(_rules["high_severity_tags"])
MEDIUM_SEVERITY_TAGS: dict[str, str] = _build_index(_rules["medium_severity_tags"])


def severity_for(tag: str) -> Severity | None:
    if tag in HIGH_SEVERITY_TAGS:
        return "high"
    if tag in MEDIUM_SEVERITY_TAGS:
        return "medium"
    return None


def tag_name_for(tag: str) -> TagName | None:
    if tag in HIGH_SEVERITY_TAGS:
        return HIGH_SEVERITY_TAGS[tag]
    if tag in MEDIUM_SEVERITY_TAGS:
        return MEDIUM_SEVERITY_TAGS[tag]
    return None
