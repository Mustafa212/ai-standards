"""Tests for audit.py. Run: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402

AUDIT = Path(__file__).resolve().parent / "audit.py"


def remove_tree(path: Path) -> None:
    """rmtree that also removes read-only files (git's objects on Windows)."""
    def make_writable(function, target, _exc):  # noqa: ANN001
        os.chmod(target, 0o700)
        function(target)

    shutil.rmtree(path, onerror=make_writable)


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)


class ParserTest(unittest.TestCase):
    def test_sarif_keeps_located_unsuppressed_results(self) -> None:
        sarif = {"runs": [{"results": [
            {"ruleId": "S107", "message": {"text": "Too many parameters"},
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "file:///w/src/A.cs"},
                                                 "region": {"startLine": 3}}}]},
            {"ruleId": "CA1031", "suppressions": [{"kind": "inSource"}], "message": {"text": "x"},
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "file:///w/src/B.cs"},
                                                 "region": {"startLine": 9}}}]},
            {"ruleId": "CS8618", "message": {"text": "no location"}},
        ]}]}
        found = audit.parse_sarif(json.dumps(sarif))
        self.assertEqual([(item["tool_id"], item["line"]) for item in found], [("S107", 3)])
        self.assertTrue(str(found[0]["file"]).replace("\\", "/").endswith("w/src/A.cs"))

    def test_eslint_ruff_and_dart(self) -> None:
        eslint = [{"filePath": "/w/src/a.ts", "messages": [{"ruleId": "max-params", "line": 2, "message": "m"},
                                                           {"ruleId": None, "line": 1, "message": "parse"}]}]
        self.assertEqual([item["tool_id"] for item in audit.parse_eslint(eslint)], ["max-params"])
        ruff = [{"code": "E722", "filename": "/w/a.py", "location": {"row": 4}, "message": "bare except"}]
        self.assertEqual(audit.parse_ruff(ruff)[0]["line"], 4)
        dart = "INFO|LINT|AVOID_PRINT|/w/lib/a.dart|7|3|5|Don't invoke 'print'.\nAnalyzing w...\n"
        self.assertEqual([(i["tool_id"], i["line"]) for i in audit.parse_dart_machine(dart)], [("avoid_print", 7)])

    def test_normalize_maps_dedupes_and_skips_generated(self) -> None:
        base = Path(tempfile.gettempdir()) / "wt"
        raw = [
            {"tool_id": "S107", "file": str(base / "src" / "A.cs"), "line": 3, "message": "m"},
            {"tool_id": "S107", "file": str(base / "src" / "A.cs"), "line": 3, "message": "m"},
            {"tool_id": "S107", "file": str(base / "obj" / "G.cs"), "line": 1, "message": "m"},
            {"tool_id": "XYZ1", "file": "src/B.cs", "line": 2, "message": "m"},
        ]
        found = audit.normalize(raw, base, {"S107": "RDB-1"})
        self.assertEqual([(item["rule"], item["file"]) for item in found],
                         [("RDB-1", "src/A.cs"), ("unmapped", "src/B.cs")])


class WorktreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.project = base / "my project"  # a space, as real paths have
        self.project.mkdir()
        git("init", "-q", cwd=self.project)
        (self.project / "app.py").write_text("print('hi')\n", encoding="utf-8")
        git("add", ".", cwd=self.project)
        git("commit", "-qm", "init", cwd=self.project)
        (self.project / "app.py").write_text("print('dirty')\n", encoding="utf-8")  # uncommitted
        self.out = base / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def args(self) -> list[str]:
        return ["tools", str(self.project), "--stack", "python", "--org", "personal",
                "--render", str(self.project), "--out", str(self.out)]

    def assert_untouched(self) -> None:
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), "print('dirty')\n")
        listing = subprocess.run(["git", "worktree", "list"], cwd=self.project, capture_output=True,
                                 text=True, check=True).stdout.strip().splitlines()
        self.assertEqual(len(listing), 1, listing)

    def test_missing_sdk_is_skipped_and_project_untouched(self) -> None:
        only_git = str(Path(shutil.which("git") or "git").parent)
        done = subprocess.run([sys.executable, str(AUDIT), *self.args()], capture_output=True, text=True,
                              env={**os.environ, "PATH": only_git}, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads((self.out / "tool-findings.json").read_text(encoding="utf-8"))
        self.assertEqual((data["status"], data["findings"]), ("skipped (uv not found)", []))
        self.assert_untouched()

    def test_a_crashing_runner_still_removes_the_worktree(self) -> None:
        original = audit.RUNNERS["python"]

        def crash(worktree: Path, render: Path, solution: str | None) -> tuple[str, list, list]:
            raise OSError("boom")

        audit.RUNNERS["python"] = crash
        try:
            self.assertEqual(audit.main(self.args()), 0)
        finally:
            audit.RUNNERS["python"] = original
        data = json.loads((self.out / "tool-findings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "failed (boom)")
        self.assert_untouched()

    def test_not_a_git_repository_is_a_bad_argument(self) -> None:
        remove_tree(self.project / ".git")
        self.assertEqual(audit.main(self.args()), 2)


class DotnetTest(unittest.TestCase):
    def test_pick_solution_prefers_the_one_with_most_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A.sln").write_text('Project("{x}") = "One", "One\\One.csproj"\n', encoding="utf-8")
            (root / "B.slnx").write_text('<Project Path="src/One/One.csproj" /><Project Path="src/Two/Two.csproj" />',
                                         encoding="utf-8")
            self.assertEqual(audit.pick_solution(root).name, "B.slnx")
            (root / "C.sln").write_text("src/X/X.csproj src/Y/Y.csproj", encoding="utf-8")
            with self.assertRaises(audit.Ambiguous):
                audit.pick_solution(root)

    def test_pick_solution_nested_and_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(audit.pick_solution(root))
            (root / "backend").mkdir()
            (root / "backend" / "App.sln").write_text("", encoding="utf-8")
            self.assertEqual(audit.pick_solution(root), root / "backend" / "App.sln")

    def test_overlay_keeps_project_settings_and_adds_the_standard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
            (render / ".ai-standards").mkdir(parents=True)
            worktree.mkdir()
            (render / "Directory.Build.props").write_text(
                '<Project>\n'
                '    <PackageReference Include="SonarAnalyzer.CSharp" Version="10.35.0.4138" PrivateAssets="all" />\n'
                '    <PackageReference Include="Microsoft.CodeAnalysis.BannedApiAnalyzers" Version="5.6.0" PrivateAssets="all" />\n'
                '    <PackageReference Include="xunit.v3" Version="4.0.2" />\n</Project>\n', encoding="utf-8")
            (render / ".editorconfig").write_text(
                "root = true\n\n[*]\nindent_style = space\n\n[*.cs]\ndotnet_diagnostic.IDE0161.severity = warning\n\n"
                "[*.md]\ntrim_trailing_whitespace = false\n", encoding="utf-8")
            for name in ("SonarLint.xml", "BannedSymbols.txt"):
                (render / ".ai-standards" / name).write_text("x", encoding="utf-8")
            (worktree / "Directory.Build.props").write_text(
                "<Project><PropertyGroup><LangVersion>12</LangVersion></PropertyGroup></Project>", encoding="utf-8")
            (worktree / "Directory.Packages.props").write_text(
                "<Project><PropertyGroup><ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>"
                "</PropertyGroup></Project>", encoding="utf-8")
            (worktree / ".editorconfig").write_text("root = true\n[*.cs]\ndotnet_diagnostic.IDE0161.severity = none\n",
                                                    encoding="utf-8")
            audit.overlay_dotnet(worktree, render)
            props = (worktree / "Directory.Build.props").read_text(encoding="utf-8")
            self.assertIn("Directory.Build.project.props", props)
            self.assertTrue((worktree / "Directory.Build.project.props").exists())
            self.assertIn('Include="SonarAnalyzer.CSharp" VersionOverride="10.35.0.4138"', props)
            self.assertNotIn("xunit", props)
            editorconfig = (worktree / ".editorconfig").read_text(encoding="utf-8")
            self.assertLess(editorconfig.index("severity = none"), editorconfig.index("IDE0161.severity = warning"))
            self.assertNotIn("[*.md]", editorconfig)
            self.assertTrue((worktree / ".ai-standards" / "SonarLint.xml").exists())
            self.assertTrue((worktree / audit.SARIF_DIR).is_dir())  # the compiler writes the SARIF there


if __name__ == "__main__":
    unittest.main()
