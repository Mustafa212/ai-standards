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

    def test_a_tool_id_override_beats_its_rule(self) -> None:
        priorities = load_priorities()
        self.assertEqual(priority("DART-3", priorities, "prefer_const_constructors"), "P4")  # style inside a P1 rule
        self.assertEqual(priority("DART-3", priorities, "use_build_context_synchronously"), "P1")
        no_print = {priority(load_tool_map(stack)[tool_id], priorities, tool_id)
                    for stack, tool_id in [("flutter", "avoid_print"), ("python", "T201"), ("typescript", "no-console")]}
        self.assertEqual(len(no_print), 1)

    def test_every_tool_id_override_is_mapped_and_valid(self) -> None:
        mapped = {tool_id for stack in STACKS for tool_id in load_tool_map(stack)}
        for tool_id, level in load_priorities()["tool_ids"].items():
            self.assertIn(tool_id, mapped)
            self.assertIn(level, ("P1", "P2", "P3", "P4"))

    def test_standards_audit_uses_the_rule_priority(self) -> None:
        import standards_audit
        self.assertEqual(standards_audit.category("FBT001", "python")[0], "P3")  # PY-6 (the old patterns said P4)
        self.assertEqual(standards_audit.category("E722", "python")[0], "P1")  # ERR-1
        self.assertEqual(standards_audit.category("S324", "python")[0], "P1")  # unmapped: old pattern still applies
        self.assertEqual(standards_audit.category("prefer_const_constructors", "flutter")[0], "P4")  # tool-ID override


import shutil
import subprocess
import tempfile


class ExceptionRuleTest(unittest.TestCase):
    def check(self, project_text: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "rules", root / "rules")
            shutil.copytree(ROOT / "orgs", root / "orgs")
            projects = root / "orgs" / "personal" / "projects"
            projects.mkdir(exist_ok=True)
            (projects / "x.md").write_text(project_text, encoding="utf-8")
            done = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_rules.py"), str(root)],
                                  capture_output=True, text=True, check=False)
            return done.returncode, done.stdout

    def test_valid_exception_passes(self) -> None:
        text = "## Project: x\n\n- **X-EX-1 [exception] → CS-5** Calls skip the token. Reason: a legacy API.\n"
        self.assertEqual(self.check(text), (0, ""))

    def test_exception_to_an_unknown_rule_fails(self) -> None:
        code, out = self.check("- **X-EX-1 [exception] → NOPE-1** Something. Reason: none.\n")
        self.assertEqual(code, 1)
        self.assertIn("points at unknown rule NOPE-1", out)

    def test_duplicate_exception_id_fails(self) -> None:
        text = ("- **X-EX-1 [exception] → CS-5** A. Reason: b.\n"
                "- **X-EX-1 [exception] → CS-4** C. Reason: d.\n")
        code, out = self.check(text)
        self.assertEqual(code, 1)
        self.assertIn("duplicate id X-EX-1", out)


if __name__ == "__main__":
    unittest.main()
