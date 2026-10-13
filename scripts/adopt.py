"""Merge a freshly rendered ai-standards project into an EXISTING project without overwriting it.

`copier copy` into a non-empty folder either stops at the first conflict or, with --overwrite,
replaces the user's files. This script is the safe path instead:

  1. render the template into an empty temp dir:  copier copy --trust ... <src> <tmp>
  2. merge it in:                                  python adopt.py <tmp> <project>

Rules, file by file:
  - missing in the project            -> copied
  - identical                         -> nothing to do
  - project-owned (README, notes)     -> kept as is
  - CLAUDE.md                         -> kept; only the `@AGENTS.md` import line is added
  - package.json, .claude/settings.json -> JSON-merged: only missing keys are added, existing values
                                           win, conflicts are reported
  - .gitignore                        -> missing lines appended
  - anything else that differs        -> new version written next to it as <file>.ai-standards
                                         for review; the original is untouched

Exit code 0 always; read the report. Nothing is ever deleted or overwritten.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from ensure_claude_import import ensure_import

PROJECT_OWNED = {"README.md", "docs/PROJECT.md", "docs/STANDARDS-DEBT.md"}
JSON_MERGED = {"package.json", ".claude/settings.json"}
LINE_MERGED = {".gitignore"}
# Keys that change how existing code runs. Never added automatically; reported for a decision.
# ("type": "module" breaks every require() in a CommonJS project.)
NEVER_AUTO_ADD = {"package.json.type"}
REVIEW_SUFFIX = ".ai-standards"
ANSWERS_FILE = ".copier-answers.yml"


class Report:
    def __init__(self) -> None:
        self.sections: dict[str, list[str]] = {}

    def add(self, section: str, line: str) -> None:
        self.sections.setdefault(section, []).append(line)

    def print(self) -> None:
        for section, lines in self.sections.items():
            print(f"\n## {section}")
            for line in lines:
                print(f"  - {line}")


def merge_json(existing: Any, incoming: Any, path: str, report: Report) -> Any:
    """Add keys from `incoming` that `existing` lacks. Existing values always win."""
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = dict(existing)
        for key, value in incoming.items():
            child = f"{path}.{key}" if path else key
            if key in existing:
                merged[key] = merge_json(existing[key], value, child, report)
            elif child in NEVER_AUTO_ADD:
                report.add("Not added, changes runtime behavior (decide manually)", f"{child} = {value!r}")
            else:
                merged[key] = value
                report.add("Added (JSON keys)", child)
        return merged
    if isinstance(existing, list) and isinstance(incoming, list):
        return existing + [item for item in incoming if item not in existing]
    if existing != incoming:
        report.add("Kept yours, differs from standard (decide manually)", f"{path}: yours={existing!r} standard={incoming!r}")
    return existing


def merge_lines(target: Path, source: Path, rel: str, report: Report) -> None:
    present = set(target.read_text(encoding="utf-8").splitlines())
    missing = [line for line in source.read_text(encoding="utf-8").splitlines() if line and line not in present]
    if missing:
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\n# Added by ai-standards\n" + "\n".join(missing) + "\n")
        report.add("Merged", f"{rel}: appended {len(missing)} line(s)")


def adopt_file(source: Path, target: Path, rel: str, report: Report) -> None:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report.add("Added", rel)
    elif source.read_bytes() == target.read_bytes():
        return
    elif rel == "CLAUDE.md":
        report.add("Kept yours", f"CLAUDE.md ({ensure_import(target.parent)})")
    elif rel in PROJECT_OWNED:
        report.add("Kept yours", rel)
    elif rel in JSON_MERGED:
        merged = merge_json(json.loads(target.read_text(encoding="utf-8")), json.loads(source.read_text(encoding="utf-8")), rel, report)
        target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    elif rel in LINE_MERGED:
        merge_lines(target, source, rel, report)
    else:
        review = target.with_name(target.name + REVIEW_SUFFIX)
        shutil.copy2(source, review)
        report.add("Needs review (standard version saved next to yours)", f"{rel} -> {rel}{REVIEW_SUFFIX}")


def adopt(rendered: Path, project: Path) -> Report:
    report = Report()
    if (project / ANSWERS_FILE).exists():
        report.add("Stopped", f"{ANSWERS_FILE} already exists: project is already on ai-standards; use copier update")
        return report
    for source in sorted(p for p in rendered.rglob("*") if p.is_file()):
        rel = source.relative_to(rendered).as_posix()
        adopt_file(source, project / rel, rel, report)
    return report


if __name__ == "__main__":
    adopt(Path(sys.argv[1]), Path(sys.argv[2])).print()
