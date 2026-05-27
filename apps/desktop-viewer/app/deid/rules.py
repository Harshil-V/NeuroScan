"""PHI rule registry (desktop copy) — reads bundled rules.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

Severity = Literal["high", "medium"]
TagName = str


def _rules_path() -> Path:
    return Path(__file__).resolve().parent / "rules.json"


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with _rules_path().open("r", encoding="utf-8") as f:
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
