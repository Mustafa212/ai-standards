"""Reject rules written twice within one org: the same ID, or the same text in two places.

Also rejects an ID that a `<!-- removed: ID ... -->` or `<!-- moved to org: ID → ... -->` marker
retired (IDs are never reused), a break shape (rules/examples/*.md, orgs/<org>/examples.md) for a
rule that doesn't exist, a base, stack or architecture rule that isn't in exactly one of the
audit's auditor groups (config/rule-groups.json), and a project registration whose repo URL carries
a user or token (everyone who can read the private copy would see it).

A project sees base + stack + architecture + its org + its own project rules, so within that scope every rule ID
and every rule text must appear once. A rule that two projects share belongs in the org file: the
onboard skill moves it there, and this check is the safety net for exact matches.

Usage: python3 scripts/check_rules.py [repo root]   (prints each problem; exit 1 if there are any)
Standard library only.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# A rule bullet: - **ID [level]** text. Headings, prose and comments are not rules.
RULE = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-\d+) \[(?:tool|review|ai)\]\*\* (.+)$")
# A project exception: - **X-EX-1 [exception] → CS-5** text. Its target must be a rule the project sees.
EXCEPTION = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-EX-\d+) \[exception\] → ([A-Z][A-Z0-9]*-\d+)\*\* (.+)$")
# Any rule ID, including those whose level is computed by template syntax (RDB-1, RDB-4).
ANY_ID = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-\d+) ")
# A deleted rule or exception, or one moved up to the org, leaves a marker; its ID stays taken.
RETIRED = re.compile(r"<!-- (?:removed|moved to org): ([A-Z][A-Z0-9]*-(?:EX-)?\d+)")
# An [ai] rule is guidance: the audit doesn't check it, so it needs no auditor group.
AI_RULE = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-\d+) \[ai\]\*\*")
# A break shape for the auditors: a "## <ID>" heading in an examples file.
EXAMPLE = re.compile(r"^## ([A-Z][A-Z0-9]*-\d+)\s*$", re.MULTILINE)
# A registration's repo URL, and an http(s) one with something before @ (`user:token@`, or a token
# alone, as Azure DevOps remotes often carry). SSH's `git@host:` is a fixed name, not a secret.
REPO_URL = re.compile(r"repo: (\S+)")
CREDENTIALS = re.compile(r"^https?://[^/@\s]+@", re.IGNORECASE)


def rules_in(path: Path) -> list[tuple[str, str]]:
    """Return (ID, text) for every rule bullet in a file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [(match.group(1), match.group(2)) for line in lines if (match := RULE.match(line))]


def exceptions_in(path: Path) -> list[tuple[str, str, str]]:
    """Return (ID, target rule, text) for every exception bullet in a file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [(m.group(1), m.group(2), m.group(3)) for line in lines if (m := EXCEPTION.match(line))]


def known_ids(files: list[Path]) -> set[str]:
    """Every rule ID in these files."""
    return {m.group(1) for file in files if file.exists()
            for line in file.read_text(encoding="utf-8").splitlines() if (m := ANY_ID.match(line))}


def unknown_targets(root: Path, files: list[Path]) -> set[str]:
    """Describe each exception whose target isn't a rule in this scope."""
    existing = [file for file in files if file.exists()]
    known = known_ids(files)
    return {
        f"exception {ex_id} points at unknown rule {target}: {file.relative_to(root).as_posix()}"
        for file in existing
        for ex_id, target, _ in exceptions_in(file)
        if target not in known
    }


def reused_ids(root: Path, files: list[Path]) -> set[str]:
    """Describe each retired ID that a rule or exception uses again."""
    existing = [file for file in files if file.exists()]
    retired = {m.group(1): file.relative_to(root).as_posix()
               for file in existing for m in RETIRED.finditer(file.read_text(encoding="utf-8"))}
    return {
        f"reused id {item_id}: retired in {retired[item_id]}, used in {file.relative_to(root).as_posix()}"
        for file in existing
        for item_id in [rule_id for rule_id, _ in rules_in(file)] + [ex[0] for ex in exceptions_in(file)]
        if item_id in retired
    }


def unknown_examples(root: Path, org_dir: Path, files: list[Path]) -> set[str]:
    """Describe each break shape whose rule isn't in this scope."""
    known = known_ids(files)
    examples = [*sorted((root / "rules" / "examples").glob("*.md")), org_dir / "examples.md"]
    return {
        f"example for unknown rule {rule_id}: {file.relative_to(root).as_posix()}"
        for file in examples if file.exists()
        for rule_id in EXAMPLE.findall(file.read_text(encoding="utf-8"))
        if rule_id not in known
    }


def ungrouped(root: Path) -> set[str]:
    """Describe each audited base, stack or architecture rule in no auditor group, or in two."""
    path = root / "config" / "rule-groups.json"
    if not path.is_file():
        return {"missing config/rule-groups.json"}
    groups = json.loads(path.read_text(encoding="utf-8"))["groups"]
    files = [root / "rules" / "base.md", *sorted((root / "rules" / "stacks").glob("*.md")),
             *sorted((root / "rules" / "architectures").glob("*.md"))]
    lines = [line for file in files if file.exists() for line in file.read_text(encoding="utf-8").splitlines()]
    audited = {m.group(1) for line in lines if (m := ANY_ID.match(line)) and not AI_RULE.match(line)}
    problems = set()
    for rule_id in sorted(audited):
        by_id = [g["name"] for g in groups if rule_id in g["rules"]]
        names = by_id or [g["name"] for g in groups if rule_id.split("-")[0] in g["rules"]]
        if len(names) != 1:
            where = ", ".join(names) if names else "no group"
            problems.add(f"rule {rule_id} is in {where}: config/rule-groups.json")
    prefixes = {rule_id.split("-")[0] for rule_id in audited}
    for group in groups:
        for entry in group["rules"]:
            if entry not in audited and entry not in prefixes:
                problems.add(f"auditor group {group['name']} names unknown rule {entry}: config/rule-groups.json")
    return problems


def url_credentials(root: Path, org_dir: Path) -> set[str]:
    """Name each registration whose repo URL carries credentials, without printing the URL."""
    return {
        f"repo URL with a user or token (remove the part before @): {file.relative_to(root).as_posix()}"
        for file in sorted((org_dir / "projects").glob("*.md"))
        for url in REPO_URL.findall(file.read_text(encoding="utf-8"))
        if CREDENTIALS.match(url)
    }


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
        for ex_id, _, _ in exceptions_in(file):
            places_by_id[ex_id].append(name)

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
    problems: set[str] = ungrouped(root)
    for org_dir in sorted(path for path in (root / "orgs").iterdir() if path.is_dir()):
        scope = org_scope(root, org_dir)
        problems |= duplicates(root, scope) | unknown_targets(root, scope) | reused_ids(root, scope)
        problems |= unknown_examples(root, org_dir, scope) | url_credentials(root, org_dir)
    for problem in sorted(problems):
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
