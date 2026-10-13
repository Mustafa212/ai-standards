"""Reject rules written twice within one org: the same ID, or the same text in two places.

A project sees base + stack + architecture + its org + its own project rules, so within that scope every rule ID
and every rule text must appear once. A rule that two projects share belongs in the org file: the
onboard skill moves it there, and this check is the safety net for exact matches.

Usage: python3 scripts/check_rules.py [repo root]   (prints each problem; exit 1 if there are any)
Standard library only.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

# A rule bullet: - **ID [level]** text. Headings, prose and comments are not rules.
RULE = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-\d+) \[(?:tool|review|ai)\]\*\* (.+)$")


def rules_in(path: Path) -> list[tuple[str, str]]:
    """Return (ID, text) for every rule bullet in a file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [(match.group(1), match.group(2)) for line in lines if (match := RULE.match(line))]


def normalized(text: str) -> str:
    """Rule text without case, punctuation or markdown, so a trivial rewording still matches."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def org_scope(root: Path, org_dir: Path) -> list[Path]:
    """Every rule file that a project in this org sees."""
    return [
        root / "rules" / "base.md",
        *sorted((root / "rules" / "stacks").glob("*.md")),
        *sorted((root / "rules" / "architectures").glob("*.md")),
        org_dir / "rules.md",
        *sorted((org_dir / "projects").glob("*.md")),
    ]


def duplicates(root: Path, files: list[Path]) -> set[str]:
    """Describe each ID or text that appears more than once across these files."""
    places_by_id: dict[str, list[str]] = defaultdict(list)
    places_by_text: dict[str, list[str]] = defaultdict(list)
    for file in files:
        if not file.exists():
            continue
        name = file.relative_to(root).as_posix()
        for rule_id, text in rules_in(file):
            places_by_id[rule_id].append(name)
            places_by_text[normalized(text)].append(f"{name} {rule_id}")

    problems = {
        f"duplicate id {rule_id}: {', '.join(places)}"
        for rule_id, places in places_by_id.items()
        if len(places) > 1
    }
    problems |= {
        f"duplicate text: {', '.join(places)}" for places in places_by_text.values() if len(places) > 1
    }
    return problems


def main() -> int:
    """Check every org's scope and report the problems once each."""
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    # A set, because a duplicate in base or stack rules shows up in every org's scope.
    problems: set[str] = set()
    for org_dir in sorted(path for path in (root / "orgs").iterdir() if path.is_dir()):
        problems |= duplicates(root, org_scope(root, org_dir))
    for problem in sorted(problems):
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
