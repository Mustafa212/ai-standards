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


class CanaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)
        self.dir = self.root / "evidence"
        fix_debt.run_tests(self.repo, fake_command(), "junit", self.dir / "clean.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_break_the_tests_see_counts_and_the_file_is_restored(self) -> None:
        result = fix_debt.canary(self.repo, "src/calc.py", 2, "    return a - b", fake_command(), "junit",
                                 self.dir / "clean.json", self.dir / "canary.json")
        self.assertEqual(result["new_failures"], ["t::adds"])
        self.assertTrue(result["restored"])
        self.assertEqual((self.repo / "src" / "calc.py").read_text(encoding="utf-8"),
                         "def add(a, b):\n    return a + b\n")

    def test_a_break_nothing_sees_has_no_new_failures(self) -> None:
        result = fix_debt.canary(self.repo, "src/calc.py", 1, "def add(a, b):  # same", fake_command(), "junit",
                                 self.dir / "clean.json", self.dir / "canary.json")
        self.assertEqual((result["new_failures"], result["failed_delta"]), ([], 0))

    def test_crlf_files_are_restored_byte_for_byte(self) -> None:
        path = self.repo / "src" / "calc.py"
        path.write_bytes(b"def add(a, b):\r\n    return a + b\r\n")
        git_q("commit", "-qam", "crlf", "--allow-empty", cwd=self.repo)  # already CRLF on Windows
        before = path.read_bytes()
        fix_debt.canary(self.repo, "src/calc.py", 2, "    return a - b", fake_command(), "junit",
                        self.dir / "clean.json", self.dir / "canary.json")
        self.assertEqual(path.read_bytes(), before)

    def test_a_dirty_file_is_refused(self) -> None:
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return b + a\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            fix_debt.canary(self.repo, "src/calc.py", 2, "x", fake_command(), "junit",
                            self.dir / "clean.json", self.dir / "canary.json")


class VerifyTest(unittest.TestCase):
    ITEM = {"id": "RDB-1@src", "rule": "RDB-1", "area": "src", "tool_ids": ["PLR0913"]}

    def test_item_gone_and_no_new_findings_in_touched_files(self) -> None:
        before = [tool("RDB-1", "src/a.py", "PLR0913"), tool("RDB-4", "src/a.py", "PLR2004")]
        after = [tool("RDB-4", "src/a.py", "PLR2004")]
        result = fix_debt.compare_findings(self.ITEM, before, after, ["src/a.py"])
        self.assertEqual((result["remaining"], result["new"]), (0, []))

    def test_remaining_findings_and_new_ones_are_reported(self) -> None:
        before = [tool("RDB-1", "src/a.py", "PLR0913")]
        after = [tool("RDB-1", "src/a.py", "PLR0913"), tool("RDB-4", "src/a.py", "PLR2004"),
                 tool("RDB-4", "lib/untouched.py", "PLR2004")]
        result = fix_debt.compare_findings(self.ITEM, before, after, ["src/a.py"])
        self.assertEqual(result["remaining"], 1)
        self.assertEqual(result["new"], [{"file": "src/a.py", "tool_id": "PLR2004", "count": 1}])

    def test_adopted_baseline_must_lose_the_item_in_its_folder(self) -> None:
        item = {"id": "max-params@src", "rule": "max-params", "area": "src", "tool_ids": ["max-params"]}
        before = {"max-params": {"src/a.ts": 2, "lib/b.ts": 1}}
        after = {"max-params": {"lib/b.ts": 1}}
        self.assertEqual(fix_debt.compare_baseline(item, before, after, ["src/a.ts"])["remaining"], 0)
        grown = {"max-params": {"lib/b.ts": 1}, "no-console": {"src/a.ts": 1}}
        self.assertEqual(fix_debt.compare_baseline(item, before, grown, ["src/a.ts"])["new"],
                         [{"file": "src/a.ts", "tool_id": "no-console", "count": 1}])

    def test_verify_review_reads_the_auditor_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fix_debt.write_json(folder / "item.json", {**self.ITEM, "start": "x"})
            review = folder / "auditor.json"
            fix_debt.write_json(review, {"rules": [{"rule": "RDB-1", "count": 0}]})
            self.assertEqual(fix_debt.main(["verify-review", "--item-dir", str(folder), "--review", str(review)]), 0)
            verify = json.loads((folder / "verify.json").read_text(encoding="utf-8"))
            self.assertEqual((verify["status"], verify["remaining"], verify["evidence"]), ("review", 0, "rule auditor"))


class VerdictTest(unittest.TestCase):
    """Each test builds one item: a start commit, then evidence files and commits, then a verdict."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_calc.py").write_text("def test_adds():\n    assert True\n", encoding="utf-8")
        git_q("add", ".", cwd=self.repo)
        git_q("commit", "-qm", "tests", cwd=self.repo)
        self.batch = self.root / "out" / "fix-debt" / "2026-10-16-1"
        self.folder = self.batch / "RDB-1@src"
        start = git_q("rev-parse", "HEAD", cwd=self.repo).strip()
        fix_debt.write_json(self.folder / "item.json", {
            "id": "RDB-1@src", "rule": "RDB-1", "area": "src", "kind": "tool", "tool_ids": ["PLR0913"],
            "start": start, "allow": ["src"], "formatter_only": False, "p1": False})
        self.passing = {"executed": 2, "passed": 2, "failed": 0, "skipped": 0, "source": "file",
                        "tests": {"t::a": "passed", "t::b": "passed"}, "finished_at": 0}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fix(self, text: str = "def add(a, b):\n    return b + a\n", path: str = "src/calc.py") -> None:
        (self.repo / path).write_text(text, encoding="utf-8")
        git_q("add", "-A", cwd=self.repo)
        git_q("commit", "-qm", "refactor: pay RDB-1 debt in src", cwd=self.repo)

    def evidence(self, **overrides: dict) -> None:
        files = {"clean": self.passing, "after": {**self.passing, "finished_at": time.time() + 5},
                 "canary": {"new_failures": ["t::a"], "failed_delta": 1, "restored": True, "source": "file"},
                 "verify": {"status": "ran (ruff 0.13)", "remaining": 0, "new": [], "evidence": "analyzer"}}
        files.update(overrides)
        for name, data in files.items():
            if data is not None:
                fix_debt.write_json(self.folder / f"{name}.json", data)

    def verdict(self) -> dict:
        return fix_debt.compute_verdict(self.repo, self.folder)

    def test_done_when_every_check_passes(self) -> None:
        self.fix()
        self.evidence()
        result = self.verdict()
        self.assertEqual(result["verdict"], "DONE", result["reasons"])
        self.assertTrue(result["does_not_prove"])

    def test_zero_tests_executed_stops(self) -> None:
        self.fix()
        self.evidence(after={**self.passing, "executed": 0, "passed": 0, "tests": {}, "finished_at": time.time() + 5})
        self.assertIn("tests ran", self.verdict()["checks"])
        self.assertFalse(self.verdict()["checks"]["tests ran"]["ok"])

    def test_an_after_run_older_than_the_last_commit_stops(self) -> None:
        self.fix()
        self.evidence(after={**self.passing, "finished_at": time.time() - 3600})
        self.assertEqual(self.verdict()["verdict"], "STOPPED")

    def test_a_lost_or_flaky_test_stops_and_is_named(self) -> None:
        self.fix()
        self.evidence(after={**self.passing, "tests": {"t::a": "passed", "t::b": "failed"},
                             "passed": 1, "failed": 1, "finished_at": time.time() + 5})
        result = self.verdict()
        self.assertEqual(result["verdict"], "STOPPED")
        self.assertIn("t::b", result["checks"]["nothing lost"]["reason"])

    def test_a_canary_with_no_new_failures_stops(self) -> None:
        self.fix()
        self.evidence(canary={"new_failures": [], "failed_delta": 0, "restored": True, "source": "file"})
        self.assertFalse(self.verdict()["checks"]["canary"]["ok"])

    def test_formatter_only_skips_the_canary(self) -> None:
        item = json.loads((self.folder / "item.json").read_text(encoding="utf-8"))
        fix_debt.write_json(self.folder / "item.json", {**item, "formatter_only": True})
        self.fix()
        self.evidence(canary=None)
        result = self.verdict()
        self.assertEqual(result["verdict"], "DONE", result["reasons"])
        self.assertIsNone(result["checks"]["canary"]["ok"])

    def test_remaining_findings_stop(self) -> None:
        self.fix()
        self.evidence(verify={"status": "ran", "remaining": 2, "new": [], "evidence": "analyzer"})
        self.assertFalse(self.verdict()["checks"]["item gone"]["ok"])

    def test_an_analyzer_that_did_not_run_stops(self) -> None:
        self.fix()
        self.evidence(verify={"status": "skipped (uv not found)", "remaining": None, "new": [], "evidence": "analyzer"})
        self.assertFalse(self.verdict()["checks"]["item gone"]["ok"])

    def test_a_file_outside_the_item_stops(self) -> None:
        self.fix(path="README.md", text="changed\n")
        self.evidence()
        self.assertFalse(self.verdict()["checks"]["scope"]["ok"])

    def test_an_added_suppression_stops(self) -> None:
        self.fix(text="def add(a, b):  # noqa: PLR0913\n    return a + b\n")
        self.evidence()
        self.assertIn("suppression", self.verdict()["checks"]["scope"]["reason"])

    def test_pinned_tests_must_pass_on_the_unfixed_code_and_stay_untouched(self) -> None:
        (self.repo / "tests" / "test_pin.py").write_text("def test_pin():\n    assert True\n", encoding="utf-8")
        git_q("add", ".", cwd=self.repo)
        git_q("commit", "-qm", "test: pin src before RDB-1", cwd=self.repo)
        item = json.loads((self.folder / "item.json").read_text(encoding="utf-8"))
        fix_debt.write_json(self.folder / "item.json", {**item, "allow": ["src", "tests"]})
        self.fix()
        self.evidence(pinned={**self.passing})
        self.assertTrue(self.verdict()["checks"]["pinned tests"]["ok"])
        (self.repo / "tests" / "test_pin.py").write_text("def test_pin():\n    pass\n", encoding="utf-8")
        git_q("commit", "-qam", "refactor: tweak", cwd=self.repo)
        self.assertFalse(self.verdict()["checks"]["pinned tests"]["ok"])

    def test_p1_needs_a_test_seen_failing_first(self) -> None:
        item = json.loads((self.folder / "item.json").read_text(encoding="utf-8"))
        fix_debt.write_json(self.folder / "item.json", {**item, "p1": True})
        self.fix()
        self.evidence(red={**self.passing})
        self.assertFalse(self.verdict()["checks"]["red first"]["ok"])

    def test_cli_writes_the_verdict_and_records_done(self) -> None:
        self.fix()
        self.evidence()
        self.assertEqual(fix_debt.main(["verdict", str(self.repo), "--item-dir", str(self.folder)]), 0)
        self.assertTrue((self.folder / "verdict.md").read_text(encoding="utf-8").startswith("## RDB-1@src — DONE"))
        done = json.loads((self.root / "out" / "fix-debt" / "done.json").read_text(encoding="utf-8"))
        self.assertEqual(done, ["RDB-1@src"])


if __name__ == "__main__":
    unittest.main()
