"""Tests for fix_debt.py. Run: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import json
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

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

    def test_the_rest_of_a_split_folder_covers_only_its_own_files(self) -> None:
        findings = {"rules": [{"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 35,
                               "sources": ["tool"], "areas": {"src": 35}}]}
        tools = [tool("RDB-1", f"src/billing/f{n}.py") for n in range(25)]
        tools += [tool("RDB-1", f"src/f{n}.py") for n in range(10)]
        rest = next(item for item in fix_debt.build_items(findings, tools, PRIORITIES, done=set())["items"]
                    if item["id"] == "RDB-1@src")
        self.assertTrue(rest["direct"])
        self.assertEqual(fix_debt.compare_findings(rest, [], [tool("RDB-1", "src/billing/f0.py")], [])["remaining"], 0)

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

    def test_items_from_an_adopted_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            baseline = out / "fix-debt" / "baseline.json"
            fix_debt.write_json(baseline, {"max-params": {"src/a.ts": 2, "lib/b.ts": 1}, "no-console": {"src/a.ts": 3}})
            self.assertEqual(fix_debt.main(["items", str(out), "--org", "personal", "--baseline", str(baseline),
                                            "--stack", "typescript"]), 0)
            data = json.loads((out / "fix-debt" / "items.json").read_text(encoding="utf-8"))
            self.assertEqual({item["id"]: (item["tool_ids"], item["count"]) for item in data["items"] + data["p1"]},
                             {"RDB-1@src": (["max-params"], 2), "RDB-1@lib": (["max-params"], 1),
                              "RDB-7@src": (["no-console"], 3)})

    def test_done_records_the_items_of_a_finished_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(fix_debt.main(["done", str(out), "--item", "B@src", "--item", "A@src"]), 0)
            self.assertEqual(fix_debt.main(["done", str(out), "--item", "C@lib"]), 0)
            done = json.loads((out / "fix-debt" / "done.json").read_text(encoding="utf-8"))
            self.assertEqual(done, ["A@src", "B@src", "C@lib"])

    def test_a_skipped_false_positive_stays_out_until_its_count_grows(self) -> None:
        findings = {"rules": [{"rule": "DES-1", "priority": "P3", "kind": "violation", "count": 2,
                               "sources": ["review"], "areas": {"src": 2}}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
            items = ["items", str(out), "--org", "personal"]
            self.assertEqual(fix_debt.main(items), 0)
            self.assertEqual(fix_debt.main(["skip", str(out), "--item", "NOPE@src", "--reason", "x"]), 2)
            self.assertEqual(fix_debt.main(["skip", str(out), "--item", "DES-1@src", "--reason", "a DTO, not an entity"]), 0)
            self.assertEqual(fix_debt.main(items), 0)
            listed = json.loads((out / "fix-debt" / "items.json").read_text(encoding="utf-8"))
            self.assertEqual(listed["items"] + listed["p1"], [])
            findings["rules"][0]["areas"]["src"] = 3  # a new finding in the same place
            (out / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
            self.assertEqual(fix_debt.main(items), 0)
            listed = json.loads((out / "fix-debt" / "items.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in listed["items"]], ["DES-1@src"])


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
    git_q("config", "gc.auto", "0", cwd=repo)  # no background gc writing objects/pack while tearDown deletes it
    git_q("add", ".", cwd=repo)
    git_q("commit", "-qm", "init", cwd=repo)
    return repo


def head_of(repo: Path) -> str:
    return git_q("rev-parse", "HEAD", cwd=repo).strip()


# A stand-in test runner, kept in a file so no shell quoting touches it. It reads src/calc.py:
# "a + b" passes the test, "SYNTAX" hides it (as a module that no longer loads does), and "EXTRA"
# adds a failing test.
FAKE_RUNNER = """import pathlib, sys
code = pathlib.Path("src/calc.py").read_text()
cases = ""
if "SYNTAX" not in code:
    cases = '<testcase classname="t" name="adds">' + ("" if "a + b" in code else "<failure/>") + "</testcase>"
if "EXTRA" in code:
    cases += '<testcase classname="t" name="extra"><failure/></testcase>'
pathlib.Path(sys.argv[1]).write_text("<testsuite>" + cases + "</testsuite>")
"""
# Writes one TRX file per test project into the folder it's given, as dotnet test does.
TRX_RUNNER = """import pathlib, sys
for name in ("Shop.Tests", "Api.Tests"):
    pathlib.Path(sys.argv[1], name + ".trx").write_text(
        '<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010"><TestDefinitions>'
        '<UnitTest name="Adds" id="a"><TestMethod className="' + name + '.Calc" name="Adds"/></UnitTest>'
        '</TestDefinitions><Results><UnitTestResult testId="a" testName="Adds" outcome="Passed"/></Results></TestRun>')
"""


def runner_command(script: str, name: str, placeholder: str = "{result}") -> str:
    path = Path(tempfile.gettempdir()) / name
    path.write_text(script, encoding="utf-8")
    return f'"{sys.executable}" "{path}" {placeholder}'


def fake_command() -> str:
    return runner_command(FAKE_RUNNER, "fix-debt-test-runner.py")


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
        self.assertEqual(item["start"], head_of(self.repo))
        self.assertEqual(item["allow"], ["tests"])
        self.assertFalse(item["p1"])

    def test_start_refuses_a_dirty_tree(self) -> None:
        (self.repo / "src" / "calc.py").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            fix_debt.start_item(self.repo, self.batch, "RDB-1@src", self.items_file, [], False)

    def test_start_refuses_an_evidence_folder_inside_the_project(self) -> None:
        with self.assertRaises(SystemExit):
            fix_debt.start_item(self.repo, self.repo / "fix-debt" / "b", "RDB-1@src", self.items_file, [], False)

    def test_run_tests_parses_the_runner_file(self) -> None:
        result = fix_debt.run_tests(self.repo, fake_command(), "junit", self.batch / "x" / "clean.json")
        self.assertEqual((result["executed"], result["passed"], result["source"]), (1, 1, "file"))
        saved = json.loads((self.batch / "x" / "clean.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["tests"], {"t::adds": "passed"})

    def test_run_tests_records_the_commit_and_a_dirty_tree(self) -> None:
        result = fix_debt.run_tests(self.repo, fake_command(), "junit", self.batch / "x" / "clean.json")
        self.assertEqual((result["head"], result["dirty"]), (head_of(self.repo), False))
        (self.repo / "src" / "helper.py").write_text("x = 1\n", encoding="utf-8")
        self.assertTrue(fix_debt.run_tests(self.repo, fake_command(), "junit", self.batch / "x" / "after.json")["dirty"])

    def test_the_test_and_canary_commands_run_from_the_cli(self) -> None:
        clean = self.batch / "x" / "clean.json"
        self.assertEqual(fix_debt.main(["test", str(self.repo), "--command", fake_command(), "--format", "junit",
                                        "--out", str(clean)]), 0)
        self.assertEqual(json.loads(clean.read_text(encoding="utf-8"))["executed"], 1)
        self.assertEqual(fix_debt.main(["canary", str(self.repo), "--file", "src/calc.py", "--line", "2",
                                        "--replace", "    return a - b", "--command", fake_command(),
                                        "--format", "junit", "--clean", str(clean),
                                        "--out", str(self.batch / "x" / "canary.json")]), 0)

    def test_a_stale_result_file_never_counts(self) -> None:
        out = self.batch / "x" / "after.json"
        fix_debt.run_tests(self.repo, fake_command(), "junit", out)
        result = fix_debt.run_tests(self.repo, f'"{sys.executable}" -c "pass"', "junit", out)
        self.assertEqual((result["executed"], result["source"]), (0, "missing"))

    def test_a_run_that_times_out_has_no_result(self) -> None:
        began = time.monotonic()
        result = fix_debt.run_tests(self.repo, f'"{sys.executable}" -c "import time; time.sleep(60)"', "junit",
                                    self.batch / "x" / "after.json", timeout=1)
        self.assertLess(time.monotonic() - began, 30)
        self.assertEqual(result["source"], "missing")
        self.assertIn("timed out", result["error"])

    def test_every_trx_file_of_the_run_counts(self) -> None:
        command = runner_command(TRX_RUNNER, "fix-debt-trx-runner.py", "{dir}")
        result = fix_debt.run_tests(self.repo, command, "trx", self.batch / "x" / "clean.json")
        self.assertEqual(sorted(result["tests"]), ["Api.Tests.Calc::Adds", "Shop.Tests.Calc::Adds"])


class CanaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)
        self.dir = self.root / "evidence"
        fix_debt.run_tests(self.repo, fake_command(), "junit", self.dir / "clean.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def canary(self, line: int, text: str) -> dict:
        return fix_debt.canary(self.repo, "src/calc.py", line, text, fake_command(), "junit",
                               self.dir / "clean.json", self.dir / "canary.json")

    def test_a_break_the_tests_see_counts_and_the_file_is_restored(self) -> None:
        result = self.canary(2, "    return a - b")
        self.assertEqual(result["new_failures"], ["t::adds"])
        self.assertTrue(result["restored"])
        self.assertEqual((self.repo / "src" / "calc.py").read_text(encoding="utf-8"),
                         "def add(a, b):\n    return a + b\n")

    def test_a_break_nothing_sees_has_no_new_failures(self) -> None:
        result = self.canary(1, "def add(a, b):  # same")
        self.assertEqual((result["new_failures"], result["failed_delta"]), ([], 0))

    def test_a_break_that_hides_tests_is_reported_not_counted(self) -> None:
        result = self.canary(2, "    SYNTAX")
        self.assertEqual((result["new_failures"], result["vanished"]), ([], ["t::adds"]))

    def test_only_tests_that_passed_before_count_as_new_failures(self) -> None:
        self.assertEqual(self.canary(2, "    return a + b  # EXTRA")["new_failures"], [])

    def test_crlf_files_are_restored_byte_for_byte(self) -> None:
        path = self.repo / "src" / "calc.py"
        path.write_bytes(b"def add(a, b):\r\n    return a + b\r\n")
        git_q("commit", "-qam", "crlf", "--allow-empty", cwd=self.repo)  # already CRLF on Windows
        before = path.read_bytes()
        self.canary(2, "    return a - b")
        self.assertEqual(path.read_bytes(), before)

    def test_a_dirty_file_is_refused(self) -> None:
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return b + a\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.canary(2, "x")

    def test_a_terminated_canary_still_restores_the_file(self) -> None:
        def killed(*_args: object, **_kwargs: object) -> dict:
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)  # what a kill delivers to the script
            return {}
        before = (self.repo / "src" / "calc.py").read_bytes()
        with mock.patch.object(fix_debt, "run_tests", killed), self.assertRaises(SystemExit):
            self.canary(2, "    return a - b")
        self.assertEqual((self.repo / "src" / "calc.py").read_bytes(), before)
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)


class VerifyTest(unittest.TestCase):
    ITEM = {"id": "RDB-1@src", "rule": "RDB-1", "area": "src", "tool_ids": ["PLR0913"]}

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)
        self.folder = self.root / "evidence"
        fix_debt.write_json(self.folder / "item.json", {**self.ITEM, "start": head_of(self.repo)})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def verify(self, code: int) -> int:
        """fd verify with the audit's tools run replaced: it exits with code, and finds nothing."""
        def fake_audit(argv: list[str]) -> int:
            if code == 0:
                fix_debt.write_json(Path(argv[argv.index("--out") + 1]) / "tool-findings.json",
                                    {"status": "ran", "findings": []})
            return code
        before = self.root / "before.json"
        fix_debt.write_json(before, {"findings": []})
        with mock.patch.object(fix_debt.audit, "main", fake_audit):
            return fix_debt.main(["verify", str(self.repo), "--item-dir", str(self.folder), "--stack", "dotnet",
                                  "--org", "personal", "--render", str(self.root), "--before", str(before)])

    def saved(self) -> dict:
        return json.loads((self.folder / "verify.json").read_text(encoding="utf-8"))

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

    def test_findings_match_the_item_by_tool_id(self) -> None:
        after = [tool("RDB-2", "src/a.py", "PLR0913")]  # the same tool id, mapped to another rule now
        self.assertEqual(fix_debt.compare_findings(self.ITEM, [], after, [])["remaining"], 1)

    def test_adopted_baseline_must_lose_the_item_in_its_folder(self) -> None:
        item = {"id": "RDB-1@src", "rule": "RDB-1", "area": "src", "tool_ids": ["max-params"]}
        before = {"max-params": {"src/a.ts": 2, "lib/b.ts": 1}}
        self.assertEqual(fix_debt.compare_baseline(item, before, {"max-params": {"lib/b.ts": 1}}, ["src/a.ts"])
                         ["remaining"], 0)
        self.assertEqual(fix_debt.compare_baseline(item, before, {"max-params": {"src/a.ts": 1}}, ["src/a.ts"])
                         ["remaining"], 1)
        grown = {"max-params": {"lib/b.ts": 1}, "no-console": {"src/a.ts": 1}}
        self.assertEqual(fix_debt.compare_baseline(item, before, grown, ["src/a.ts"])["new"],
                         [{"file": "src/a.ts", "tool_id": "no-console", "count": 1}])

    def test_verify_records_the_commit_it_checked(self) -> None:
        self.assertEqual(self.verify(0), 0)
        self.assertEqual((self.saved()["remaining"], self.saved()["head"]), (0, head_of(self.repo)))

    def test_several_solutions_ask_for_one(self) -> None:
        self.assertEqual(self.verify(3), 3)
        self.assertIn("--solution", self.saved()["status"])

    def test_verify_review_reads_the_auditor_count(self) -> None:
        review = self.root / "auditor.json"
        fix_debt.write_json(review, {"rules": [{"rule": "RDB-1", "count": 0}]})
        self.assertEqual(fix_debt.main(["verify-review", str(self.repo), "--item-dir", str(self.folder),
                                        "--review", str(review)]), 0)
        verify = self.saved()
        self.assertEqual((verify["status"], verify["remaining"], verify["evidence"], verify["head"]),
                         ("review", 0, "rule auditor", head_of(self.repo)))

    def test_verify_review_without_a_readable_review_exits_2(self) -> None:
        broken = self.root / "broken.json"
        broken.write_text("not json", encoding="utf-8")
        for review in (self.root / "missing.json", broken):
            with self.subTest(review=review.name):
                self.assertEqual(fix_debt.main(["verify-review", str(self.repo), "--item-dir", str(self.folder),
                                                "--review", str(review)]), 2)
        self.assertFalse((self.folder / "verify.json").exists())


class VerdictTest(unittest.TestCase):
    """Each test builds one item: a start commit, then evidence files and commits, then a verdict."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)
        self.start = self.commit({"tests/test_calc.py": "def test_adds():\n    assert True\n"}, "tests")
        self.folder = self.root / "out" / "fix-debt" / "2026-10-16-1" / "RDB-1@src"
        fix_debt.write_json(self.folder / "item.json", {
            "id": "RDB-1@src", "rule": "RDB-1", "area": "src", "kind": "tool", "tool_ids": ["PLR0913"],
            "start": self.start, "allow": [], "formatter_only": False, "p1": False})
        self.passing = {"executed": 2, "passed": 2, "failed": 0, "skipped": 0, "source": "file",
                        "tests": {"t::a": "passed", "t::b": "passed"}, "dirty": False}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def commit(self, files: dict[str, str], subject: str) -> str:
        for path, text in files.items():
            (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / path).write_text(text, encoding="utf-8")
        git_q("add", "-A", cwd=self.repo)
        git_q("commit", "-qm", subject, cwd=self.repo)
        return head_of(self.repo)

    def fix(self, text: str = "def add(a, b):\n    return b + a\n", path: str = "src/calc.py") -> None:
        self.commit({path: text}, "refactor: pay RDB-1 debt in src")

    def pin(self, files: dict[str, str] | None = None, subject: str = "test: pin src before RDB-1") -> str:
        return self.commit(files or {"tests/test_pin.py": "def test_pin():\n    assert True\n"}, subject)

    def run_on(self, head: str | None = None, **changes: object) -> dict:
        """A test run's evidence: the passing run, on head (HEAD when not given), with changes."""
        return {**self.passing, "head": head or head_of(self.repo), **changes}

    def set_item(self, **changes: object) -> None:
        item = json.loads((self.folder / "item.json").read_text(encoding="utf-8"))
        fix_debt.write_json(self.folder / "item.json", {**item, **changes})

    def evidence(self, **overrides: object) -> None:
        files = {"clean": self.run_on(self.start), "after": self.run_on(),
                 "canary": {"file": "src/calc.py", "line": 2, "new_failures": ["t::a"], "failed_delta": 1,
                            "vanished": [], "restored": True, "source": "file"},
                 "verify": {"status": "ran (ruff 0.13)", "remaining": 0, "new": [], "evidence": "analyzer",
                            "head": head_of(self.repo)}}
        files.update(overrides)
        for name, data in files.items():
            if data is not None:
                fix_debt.write_json(self.folder / f"{name}.json", data)

    def verdict(self) -> dict:
        return fix_debt.compute_verdict(self.repo, self.folder)

    def check(self, name: str) -> dict:
        return self.verdict()["checks"][name]

    def test_done_when_every_check_passes(self) -> None:
        self.fix()
        self.evidence()
        result = self.verdict()
        self.assertEqual(result["verdict"], "DONE", result["reasons"])
        self.assertTrue(result["does_not_prove"])

    def test_zero_tests_executed_stops(self) -> None:
        self.fix()
        self.evidence(after=self.run_on(executed=0, passed=0, tests={}))
        self.assertFalse(self.check("tests ran")["ok"])

    def test_a_clean_run_with_no_result_stops(self) -> None:
        self.fix()
        self.evidence(clean=self.run_on(self.start, executed=0, passed=0, tests={}, source="missing"))
        self.assertEqual(self.verdict()["verdict"], "STOPPED")
        self.assertFalse(self.check("clean run")["ok"])

    def test_a_clean_run_not_on_the_start_commit_stops(self) -> None:
        self.fix()
        self.evidence(clean=self.run_on())
        self.assertFalse(self.check("clean run")["ok"])

    def test_failures_in_the_clean_run_stop(self) -> None:
        self.fix()
        self.evidence(clean=self.run_on(self.start, passed=1, failed=1, tests={"t::a": "passed", "t::b": "failed"}))
        self.assertFalse(self.check("clean run")["ok"])

    def test_an_after_run_on_another_commit_stops(self) -> None:
        self.fix()
        self.evidence(after=self.run_on(self.start))
        self.assertFalse(self.check("tests ran")["ok"])

    def test_an_after_run_with_uncommitted_changes_stops(self) -> None:
        self.fix()
        self.evidence(after=self.run_on(dirty=True))
        self.assertFalse(self.check("tests ran")["ok"])

    def test_an_uncommitted_file_when_the_verdict_runs_stops(self) -> None:
        self.fix()
        self.evidence()
        (self.repo / "src" / "helper.py").write_text("x = 1\n", encoding="utf-8")
        result = self.verdict()
        self.assertEqual(result["verdict"], "STOPPED")
        self.assertIn("src/helper.py", " ".join(result["reasons"]))

    def test_a_verify_run_on_another_commit_stops(self) -> None:
        self.fix()
        self.evidence(verify={"status": "ran", "remaining": 0, "new": [], "evidence": "analyzer", "head": self.start})
        self.assertFalse(self.check("item gone")["ok"])

    def test_a_lost_or_flaky_test_stops_and_is_named(self) -> None:
        self.fix()
        self.evidence(after=self.run_on(tests={"t::a": "passed", "t::b": "failed"}, passed=1, failed=1))
        result = self.verdict()
        self.assertEqual(result["verdict"], "STOPPED")
        self.assertIn("t::b", result["checks"]["nothing lost"]["reason"])

    def test_a_new_test_failing_after_the_fix_stops(self) -> None:
        self.fix()
        self.evidence(after=self.run_on(tests={"t::a": "passed", "t::b": "passed", "t::c": "failed"},
                                        executed=3, failed=1))
        self.assertIn("t::c", self.check("nothing lost")["reason"])
        self.assertFalse(self.check("nothing lost")["ok"])

    def test_a_pinned_test_that_fails_after_the_fix_stops(self) -> None:
        pin = self.pin()
        self.fix()
        self.evidence(pinned=self.run_on(pin, tests={"t::a": "passed", "t::b": "passed", "t::pin": "passed"},
                                         executed=3, passed=3))
        self.assertFalse(self.check("nothing lost")["ok"])
        self.assertIn("t::pin", self.check("nothing lost")["reason"])

    def test_p1_tests_seen_failing_must_pass_after_the_fix(self) -> None:
        self.set_item(p1=True)
        self.fix()
        self.evidence(red=self.run_on(self.start, tests={"t::new": "failed"}, executed=1, passed=0, failed=1,
                                      dirty=True))
        self.assertFalse(self.check("nothing lost")["ok"])
        self.assertIn("t::new", self.check("nothing lost")["reason"])

    def test_a_canary_with_no_new_failures_stops(self) -> None:
        self.fix()
        self.evidence(canary={"file": "src/calc.py", "line": 2, "new_failures": [], "failed_delta": 0,
                              "vanished": [], "restored": True, "source": "file"})
        self.assertFalse(self.check("canary")["ok"])

    def test_a_canary_that_hid_tests_stops(self) -> None:
        self.fix()
        self.evidence(canary={"file": "src/calc.py", "line": 2, "new_failures": ["t::a"], "failed_delta": 1,
                              "vanished": ["t::b"], "restored": True, "source": "file"})
        self.assertFalse(self.check("canary")["ok"])

    def test_a_canary_in_a_file_the_fix_left_alone_stops(self) -> None:
        self.fix()
        self.evidence(canary={"file": "src/other.py", "line": 2, "new_failures": ["t::a"], "failed_delta": 1,
                              "vanished": [], "restored": True, "source": "file"})
        self.assertFalse(self.check("canary")["ok"])

    def test_formatter_only_skips_the_canary(self) -> None:
        self.set_item(formatter_only=True)
        self.fix()
        self.evidence(canary=None)
        result = self.verdict()
        self.assertEqual(result["verdict"], "DONE", result["reasons"])
        self.assertIsNone(result["checks"]["canary"]["ok"])

    def test_remaining_findings_stop(self) -> None:
        self.fix()
        self.evidence(verify={"status": "ran", "remaining": 2, "new": [], "evidence": "analyzer",
                              "head": head_of(self.repo)})
        self.assertFalse(self.check("item gone")["ok"])

    def test_an_analyzer_that_did_not_run_stops(self) -> None:
        self.fix()
        self.evidence(verify={"status": "skipped (uv not found)", "remaining": None, "new": [], "evidence": "analyzer",
                              "head": head_of(self.repo)})
        self.assertFalse(self.check("item gone")["ok"])

    def test_a_file_outside_the_item_stops(self) -> None:
        self.fix(path="README.md", text="changed\n")
        self.evidence()
        self.assertFalse(self.check("scope")["ok"])

    def test_an_added_suppression_stops(self) -> None:
        self.fix(text="def add(a, b):  # noqa: PLR0913\n    return a + b\n")
        self.evidence()
        self.assertIn("suppression", self.check("scope")["reason"])

    def test_more_ways_to_silence_a_rule_stop(self) -> None:
        for line in ("# ruff: noqa: PLR0913", "# mypy: ignore-errors", "// @ts-ignore", "// @ts-expect-error",
                     "/* eslint max-params: off */", '[System.Diagnostics.CodeAnalysis.SuppressMessage("x", "y")]',
                     "dotnet_diagnostic.CA1822.severity = silent"):
            with self.subTest(line=line):
                git_q("reset", "-q", "--hard", self.start, cwd=self.repo)
                self.fix(text=f"def add(a, b):\n    return b + a\n{line}\n")
                self.evidence()
                self.assertIn("suppression", self.check("scope")["reason"])

    def test_a_lint_config_change_stops_unless_allowed(self) -> None:
        self.fix(path="src/ruff.toml", text="[lint]\nignore = ['PLR0913']\n")
        self.evidence()
        self.assertIn("src/ruff.toml", self.check("scope")["reason"])
        self.set_item(allow=["src/ruff.toml"])
        self.assertTrue(self.check("scope")["ok"])

    def test_pinned_tests_must_pass_on_the_unfixed_code_and_stay_untouched(self) -> None:
        pin = self.pin()
        self.fix()
        self.evidence(pinned=self.run_on(pin))
        self.assertTrue(self.check("pinned tests")["ok"])
        self.commit({"tests/test_pin.py": "def test_pin():\n    pass\n"}, "refactor: tweak")
        self.assertFalse(self.check("pinned tests")["ok"])

    def test_pin_files_come_from_the_pinned_run_not_the_commit_subject(self) -> None:
        pin = self.pin(subject="add tests")
        self.fix()
        self.evidence(pinned=self.run_on(pin))
        result = self.verdict()
        self.assertEqual(result["verdict"], "DONE", result["reasons"])

    def test_a_pinned_run_without_a_pin_commit_stops(self) -> None:
        self.fix()
        self.evidence(pinned=self.run_on(self.start))
        self.assertFalse(self.check("pinned tests")["ok"])

    def test_a_non_test_file_in_the_pin_commit_is_outside_the_item(self) -> None:
        pin = self.pin({"tests/test_pin.py": "def test_pin():\n    assert True\n", "README.md": "changed\n"})
        self.fix()
        self.evidence(pinned=self.run_on(pin))
        self.assertIn("README.md", self.check("scope")["reason"])

    def test_p1_needs_a_test_seen_failing_first(self) -> None:
        self.set_item(p1=True)
        self.fix()
        self.evidence(red=self.run_on(self.start))
        self.assertFalse(self.check("red first")["ok"])

    def test_cli_writes_the_verdict_and_leaves_done_to_the_end_of_the_round(self) -> None:
        self.fix()
        self.evidence()
        self.assertEqual(fix_debt.main(["verdict", str(self.repo), "--item-dir", str(self.folder)]), 0)
        self.assertTrue((self.folder / "verdict.md").read_text(encoding="utf-8").startswith("## RDB-1@src — DONE"))
        self.assertFalse((self.root / "out" / "fix-debt" / "done.json").exists())

    def test_a_crash_exits_2_not_1(self) -> None:
        # Exit 1 is STOPPED, after which the skill resets the item's commits: an error must not look like it.
        self.assertEqual(fix_debt.main(["verdict", str(self.repo), "--item-dir", str(self.root / "nowhere")]), 2)


if __name__ == "__main__":
    unittest.main()
