"""Tests for rule_data.py, the tool-map and priority files, and check_rules.py exceptions.

Run: python3 -m unittest discover -s scripts -p 'test_*.py'
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rule_data import ROOT, load_priorities, load_tool_map, priority  # noqa: E402

EXPECT = re.compile(r"^(?://|#)\s*expect:\s*(.+)$")
RULE_ID = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-\d+) ", re.MULTILINE)
STACKS = ("typescript", "angular", "python", "dotnet", "flutter")


def expected_ids(folder: Path) -> set[str]:
    """The tool IDs a folder's violation files say must fire (their `expect:` first line)."""
    ids: set[str] = set()
    for file in folder.glob("*.*"):
        match = EXPECT.match(file.read_text(encoding="utf-8").splitlines()[0])
        if match:
            ids |= {item.strip() for item in match.group(1).split(",")}
    return ids


def rule_ids(org: str | None) -> set[str]:
    """Every rule ID a project in this org can see."""
    files = [ROOT / "rules" / "base.md", *(ROOT / "rules" / "stacks").glob("*.md"),
             *(ROOT / "rules" / "architectures").glob("*.md")]
    if org:
        files.append(ROOT / "orgs" / org / "rules.md")
    return {rule for file in files for rule in RULE_ID.findall(file.read_text(encoding="utf-8"))}


class ToolMapTest(unittest.TestCase):
    def test_every_expected_tool_id_has_a_rule(self) -> None:
        for stack_dir in sorted(path for path in (ROOT / "tests" / "violations").iterdir() if path.is_dir()):
            stack = stack_dir.name
            missing = expected_ids(stack_dir) - load_tool_map(stack).keys()
            self.assertFalse(missing, f"{stack}: no rule for {sorted(missing)}")
            for org_dir in (path for path in stack_dir.iterdir() if path.is_dir()):
                org_missing = expected_ids(org_dir) - load_tool_map(stack, org_dir.name).keys()
                self.assertFalse(org_missing, f"{stack}/{org_dir.name}: no rule for {sorted(org_missing)}")

    def test_every_mapped_rule_exists(self) -> None:
        orgs = [None, *(path.name for path in (ROOT / "orgs").iterdir() if path.is_dir())]
        for org in orgs:
            known = rule_ids(org)
            for stack in STACKS:
                unknown = set(load_tool_map(stack, org).values()) - known
                self.assertFalse(unknown, f"{stack} ({org or 'base'}): unknown rules {sorted(unknown)}")

    def test_angular_includes_the_typescript_rules(self) -> None:
        self.assertEqual(load_tool_map("angular")["max-params"], "RDB-1")


class PriorityTest(unittest.TestCase):
    def test_priority_comes_from_the_rule(self) -> None:
        priorities = load_priorities()
        self.assertEqual(priority(load_tool_map("dotnet")["S107"], priorities), "P3")  # Sonar IDs aren't security
        self.assertEqual(priority("ERR-1", priorities), "P1")
        self.assertEqual(priority("RDB-6", priorities), "P4")
        self.assertEqual(priority("unmapped", priorities), "P4")
        self.assertEqual(priority("ZZZ-9", priorities), "P3")  # org and project rules default to P3


if __name__ == "__main__":
    unittest.main()
