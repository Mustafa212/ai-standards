"""Tests for fix_debt.py. Run: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix_debt  # noqa: E402

PRIORITIES = {"default": "P3", "prefixes": {"ERR": "P1"}, "ids": {"RDB-6": "P4"}, "tool_ids": {}}


def tool(rule: str, file: str, tool_id: str = "x", line: int = 1) -> dict:
    return {"rule": rule, "tool_id": tool_id, "file": file, "line": line, "message": "m", "source": "tool"}


class ItemsTest(unittest.TestCase):
    def test_items_per_rule_and_folder_p1_apart_review_items_kept_done_skipped(self) -> None:
        findings = {"rules": [
            {"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 3, "sources": ["tool"],
             "areas": {"src": 2, "lib": 1}},
            {"rule": "ERR-1", "priority": "P1", "kind": "violation", "count": 1, "sources": ["tool"],
             "areas": {"src": 1}},
            {"rule": "DES-1", "priority": "P3", "kind": "violation", "count": 4, "sources": ["review"],
             "areas": {"src": 4}},
            {"rule": "RDB-3", "priority": "P3", "kind": "inconsistency", "count": 2, "sources": ["review"],
             "areas": {"src": 2}},
        ]}
        tools = [tool("RDB-1", "src/a.py"), tool("RDB-1", "src/b.py"), tool("RDB-1", "lib/c.py"),
                 tool("ERR-1", "src/a.py")]
        result = fix_debt.build_items(findings, tools, PRIORITIES, done={"RDB-1@lib"})
        self.assertEqual([item["id"] for item in result["items"]], ["DES-1@src", "RDB-1@src"])
        self.assertEqual(result["items"][1]["files"], ["src/a.py", "src/b.py"])
        self.assertEqual(result["items"][0]["kind"], "review")
        self.assertEqual([item["id"] for item in result["p1"]], ["ERR-1@src"])
        self.assertEqual(result["p1"][0]["behavior"], "changes")

    def test_a_large_item_splits_by_the_next_folder(self) -> None:
        findings = {"rules": [{"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 40,
                               "sources": ["tool"], "areas": {"src": 40}}]}
        tools = [tool("RDB-1", f"src/billing/f{n}.py") for n in range(25)]
        tools += [tool("RDB-1", f"src/orders/f{n}.py") for n in range(15)]
        result = fix_debt.build_items(findings, tools, PRIORITIES, done=set())
        self.assertEqual({item["id"]: item["count"] for item in result["items"]},
                         {"RDB-1@src/billing": 25, "RDB-1@src/orders": 15})

    def test_a_rule_split_by_tool_priority_keeps_its_tool_ids_apart(self) -> None:
        priorities = {**PRIORITIES, "ids": {"DART-3": "P1"}, "tool_ids": {"prefer_const_constructors": "P4"}}
        findings = {"rules": [
            {"rule": "DART-3", "priority": "P1", "kind": "violation", "count": 1, "sources": ["tool"], "areas": {"lib": 1}},
            {"rule": "DART-3", "priority": "P4", "kind": "violation", "count": 2, "sources": ["tool"], "areas": {"lib": 2}},
        ]}
        tools = [tool("DART-3", "lib/a.dart", "use_build_context_synchronously"),
                 tool("DART-3", "lib/b.dart", "prefer_const_constructors"),
                 tool("DART-3", "lib/c.dart", "prefer_const_constructors")]
        result = fix_debt.build_items(findings, tools, priorities, done=set())
        self.assertEqual(result["items"][0]["id"], "DART-3@lib#P4")
        self.assertEqual(result["items"][0]["tool_ids"], ["prefer_const_constructors"])
        self.assertEqual(result["p1"][0]["files"], ["lib/a.dart"])

    def test_in_area_and_root(self) -> None:
        self.assertTrue(fix_debt.in_area("src/billing/a.py", "src/billing"))
        self.assertFalse(fix_debt.in_area("src/billing2/a.py", "src/billing"))
        self.assertTrue(fix_debt.in_area("setup.py", "(root)"))
        self.assertFalse(fix_debt.in_area("src/a.py", "(root)"))

    def test_items_cli_writes_items_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "findings.json").write_text(json.dumps({"rules": [
                {"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 1, "sources": ["tool"],
                 "areas": {"src": 1}}]}), encoding="utf-8")
            (out / "tool-findings.json").write_text(json.dumps({"status": "ran", "notes": [],
                                                                "findings": [tool("RDB-1", "src/a.py")]}), encoding="utf-8")
            self.assertEqual(fix_debt.main(["items", str(out), "--org", "personal"]), 0)
            data = json.loads((out / "fix-debt" / "items.json").read_text(encoding="utf-8"))
            self.assertEqual(data["items"][0]["id"], "RDB-1@src")


def git_q(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                           "-c", "core.autocrlf=false", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def make_repo(root: Path) -> Path:
    repo = root / "my project"  # a space, as real paths have
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    git_q("init", "-q", cwd=repo)
    git_q("config", "core.autocrlf", "false", cwd=repo)  # plain git calls then see the committed bytes
    git_q("add", ".", cwd=repo)
    git_q("commit", "-qm", "init", cwd=repo)
    return repo


# A stand-in test runner, kept in a file so no shell quoting touches it: writes a JUnit file whose
# test passes while src/calc.py still says "a + b".
FAKE_RUNNER = """import pathlib, sys
ok = "a + b" in pathlib.Path("src/calc.py").read_text()
pathlib.Path(sys.argv[1]).write_text(
    '<testsuite><testcase classname="t" name="adds">' + ("" if ok else "<failure/>") + "</testcase></testsuite>")
"""
RUNNER = Path(tempfile.gettempdir()) / "fix-debt-test-runner.py"


def fake_command() -> str:
    RUNNER.write_text(FAKE_RUNNER, encoding="utf-8")
    return f'"{sys.executable}" "{RUNNER}" {{result}}'


class StartAndTestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)
        self.batch = self.root / "out" / "fix-debt" / "2026-10-16-1"
        items = {"items": [{"id": "RDB-1@src", "rule": "RDB-1", "area": "src", "priority": "P3", "count": 1,
                            "kind": "tool", "tool_ids": ["PLR0913"], "files": ["src/calc.py"],
                            "behavior": "preserves"}], "p1": []}
        self.items_file = self.root / "out" / "fix-debt" / "items.json"
        fix_debt.write_json(self.items_file, items)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_start_records_the_item_and_its_start_commit(self) -> None:
        folder = fix_debt.start_item(self.repo, self.batch, "RDB-1@src", self.items_file, ["tests"], False)
        item = json.loads((folder / "item.json").read_text(encoding="utf-8"))
        self.assertEqual(item["start"], git_q("rev-parse", "HEAD", cwd=self.repo).strip())
        self.assertEqual(item["allow"], ["src", "tests"])
        self.assertFalse(item["p1"])

    def test_start_refuses_a_dirty_tree(self) -> None:
        (self.repo / "src" / "calc.py").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            fix_debt.start_item(self.repo, self.batch, "RDB-1@src", self.items_file, [], False)

    def test_run_tests_parses_the_runner_file(self) -> None:
        result = fix_debt.run_tests(self.repo, fake_command(), "junit", self.batch / "x" / "clean.json")
        self.assertEqual((result["executed"], result["passed"], result["source"]), (1, 1, "file"))
        saved = json.loads((self.batch / "x" / "clean.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["tests"], {"t::adds": "passed"})

    def test_a_stale_result_file_never_counts(self) -> None:
        out = self.batch / "x" / "after.json"
        stale = out.with_suffix(".xml")
        stale.parent.mkdir(parents=True)
        stale.write_text('<testsuite><testcase classname="t" name="old"/></testsuite>', encoding="utf-8")
        result = fix_debt.run_tests(self.repo, f'"{sys.executable}" -c "pass"', "junit", out)
        self.assertEqual((result["executed"], result["source"]), (0, "missing"))


if __name__ == "__main__":
    unittest.main()
