"""Which rule a tool finding belongs to, and how urgent each rule is.

Shared by audit.py and standards_audit.py. Reads config/tool-map.json and config/rule-priority.json,
plus orgs/<org>/tool-map.json and orgs/<org>/rule-priority.json when an org adds its own entries.
Standard library only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIORITY_TITLES = {
    "P1": "Correctness and security",
    "P2": "Types",
    "P3": "Readability and size",
    "P4": "Style",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@lru_cache(maxsize=None)
def load_tool_map(stack: str, org: str | None = None, root: Path = ROOT) -> dict[str, str]:
    """Tool ID -> rule ID for one stack (angular runs the TypeScript rules too), org entries on top."""
    layers = [_read(root / "config" / "tool-map.json")]
    if org:
        layers.append(_read(root / "orgs" / org / "tool-map.json"))
    stacks = ["typescript", "angular"] if stack == "angular" else [stack]
    mapping: dict[str, str] = {}
    for layer in layers:
        for name in stacks:
            mapping.update(layer.get(name, {}))
    return mapping


@lru_cache(maxsize=None)
def load_priorities(org: str | None = None, root: Path = ROOT) -> dict:
    """The default, per-prefix and per-ID priorities, with the org's own entries on top."""
    data = _read(root / "config" / "rule-priority.json")
    merged = {
        "default": data.get("default", "P3"),
        "prefixes": dict(data.get("prefixes", {})),
        "ids": dict(data.get("ids", {})),
    }
    if org:
        extra = _read(root / "orgs" / org / "rule-priority.json")
        merged["prefixes"].update(extra.get("prefixes", {}))
        merged["ids"].update(extra.get("ids", {}))
    return merged


def priority(rule: str, priorities: dict) -> str:
    """P1-P4 for a rule ID. Findings that no rule claims are P4."""
    if rule == "unmapped":
        return "P4"
    if rule in priorities["ids"]:
        return priorities["ids"][rule]
    return priorities["prefixes"].get(rule.split("-")[0], priorities["default"])
