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

    def test_a_rule_named_in_the_message_wins_over_the_tool_map(self) -> None:
        # One tool ID (a banned-API list) can serve several rules; each ban message names its own.
        raw = [
            {"tool_id": "RS0030", "file": "src/A.cs", "line": 1,
             "message": "The symbol 'DateTime.UtcNow' is banned in this project: Read the time from an injected "
                        "TimeProvider (CS-24)."},
            {"tool_id": "RS0030", "file": "src/A.cs", "line": 2, "message": "The symbol 'X' is banned."},
        ]
        found = audit.normalize(raw, Path(tempfile.gettempdir()), {"RS0030": "ACME-2"})
        self.assertEqual([item["rule"] for item in found], ["CS-24", "ACME-2"])


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

    def test_other_worktrees_and_hooks_are_left_alone(self) -> None:
        # Another worktree whose folder is gone (an unplugged drive): its metadata must survive.
        other = Path(self.tmp.name) / "other"
        git("worktree", "add", "-q", "-b", "feature", str(other), cwd=self.project)
        other.rename(Path(self.tmp.name) / "other-moved")
        # A hook that would write into the project if git ran it.
        marker = self.project / "HOOK-RAN.txt"
        hook = self.project / ".git" / "hooks" / "post-checkout"
        hook.write_text(f'#!/bin/sh\ntouch "{marker.as_posix()}"\n', encoding="utf-8")
        hook.chmod(0o755)
        self.assertEqual(audit.main(self.args()), 0)
        self.assertTrue((self.project / ".git" / "worktrees" / "other").is_dir(), "another worktree's metadata was pruned")
        self.assertFalse(marker.exists(), "a project hook ran during the audit")

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
            (worktree / "Legacy").mkdir(parents=True)
            (render / "Directory.Build.props").write_text(
                '<Project>\n'
                '    <PackageReference Include="SonarAnalyzer.CSharp" Version="10.35.0.4138" PrivateAssets="all" />\n'
                '    <PackageReference Include="Microsoft.CodeAnalysis.BannedApiAnalyzers" Version="5.6.0" PrivateAssets="all" />\n'
                '    <PackageReference Include="xunit.v3" Version="4.0.2" />\n</Project>\n', encoding="utf-8")
            # The template's real form: option suffixes, rule-ID severities, and a tests section.
            (render / ".editorconfig").write_text(
                "root = true\n\n[*]\nindent_style = space\n\n[*.cs]\n"
                "csharp_style_namespace_declarations = file_scoped:warning\n"
                "dotnet_diagnostic.CA1031.severity = warning\n\n"
                "[tests/**.cs]\ndotnet_diagnostic.S109.severity = none\n\n"
                "[*.md]\ntrim_trailing_whitespace = false\n", encoding="utf-8")
            for name in ("SonarLint.xml", "BannedSymbols.txt"):
                (render / ".ai-standards" / name).write_text("x", encoding="utf-8")
            # The project fights the standard: its own props and targets, a rule silenced by ID at the
            # root and in a nested .editorconfig.
            (worktree / "Directory.Build.props").write_text(
                "<Project><PropertyGroup><ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>"
                "</PropertyGroup></Project>", encoding="utf-8")
            (worktree / "Directory.Build.targets").write_text("<Project />", encoding="utf-8")
            (worktree / ".editorconfig").write_text("root = true\n[*.cs]\ndotnet_diagnostic.IDE0161.severity = none\n",
                                                    encoding="utf-8")
            (worktree / "Legacy" / ".editorconfig").write_text("[*.cs]\ndotnet_diagnostic.CA2016.severity = none\n",
                                                               encoding="utf-8")
            audit.overlay_dotnet(worktree, render)

            props = (worktree / "Directory.Build.props").read_text(encoding="utf-8")
            self.assertIn("Directory.Build.project.props", props)
            self.assertTrue((worktree / "Directory.Build.project.props").exists())
            # Central package management is decided by MSBuild, wherever the project turns it on.
            self.assertIn('Include="SonarAnalyzer.CSharp" Version="10.35.0.4138"', props)
            self.assertIn('Include="SonarAnalyzer.CSharp" VersionOverride="10.35.0.4138"', props)
            self.assertIn("'$(ManagePackageVersionsCentrally)' == 'true'", props)
            self.assertIn("!$(MSBuildProjectName.EndsWith('Tests'))", props)  # no banned-API checks in tests
            self.assertNotIn("xunit", props)

            targets = (worktree / "Directory.Build.targets").read_text(encoding="utf-8")
            self.assertTrue((worktree / "Directory.Build.project.targets").exists())
            self.assertIn("Directory.Build.project.targets", targets)
            for setting in ("<RunAnalyzers>true</RunAnalyzers>", "<EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>",
                            "<WarningsAsErrors></WarningsAsErrors>"):
                self.assertIn(setting, targets)
            exclude = targets.split('Exclude="')[1].split('"')[0].split(";")
            self.assertIn("CA1031", exclude)  # a project's NoWarn can't hide a standard rule
            self.assertIn("1591", exclude)  # NoWarn also accepts the number alone

            root = (worktree / ".editorconfig").read_text(encoding="utf-8")
            self.assertLess(root.index("IDE0161.severity = none"), root.rindex("dotnet_diagnostic.IDE0161.severity = warning"))
            self.assertIn("[tests/**.cs]", root)
            self.assertNotIn("[*.md]", root)
            nested = (worktree / "Legacy" / ".editorconfig").read_text(encoding="utf-8")
            self.assertLess(nested.index("CA2016.severity = none"), nested.index("ai-standards audit"))
            self.assertTrue((worktree / ".ai-standards" / "SonarLint.xml").exists())
            self.assertTrue((worktree / audit.SARIF_DIR).is_dir())  # the compiler writes the SARIF there

    @staticmethod
    def _small_render(render: Path) -> None:
        (render / ".ai-standards").mkdir(parents=True)
        (render / "Directory.Build.props").write_text("<Project />", encoding="utf-8")
        (render / ".editorconfig").write_text("root = true\n[*.cs]\n", encoding="utf-8")
        for name in ("SonarLint.xml", "BannedSymbols.txt"):
            (render / ".ai-standards" / name).write_text("x", encoding="utf-8")

    def _run_dotnet(self, worktree: Path, render: Path, sarif_in: Path | None) -> tuple[str, list, list]:
        sarif = {"runs": [{"results": [{"ruleId": "CA1031", "locations": [{"physicalLocation": {
            "artifactLocation": {"uri": "src/A.cs"}, "region": {"startLine": 3}}}]}]}]}

        def fake_run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
            if "build" in args and sarif_in is not None:
                sarif_in.mkdir(parents=True, exist_ok=True)
                (sarif_in / "A-net10.0.sarif").write_text(json.dumps(sarif), encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "10.0.401", "")

        original_which, original_run = audit.shutil.which, audit.run
        audit.shutil.which = lambda name: "dotnet"
        audit.run = fake_run
        try:
            return audit.run_dotnet(worktree, render, None)
        finally:
            audit.shutil.which, audit.run = original_which, original_run

    def test_a_solution_in_a_subfolder_gets_the_overlay_next_to_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
            self._small_render(render)
            backend = worktree / "backend"
            (backend / "src").mkdir(parents=True)
            (backend / "App.slnx").write_text('<Project Path="src/A/A.csproj" />', encoding="utf-8")
            # The project's own props stop MSBuild there, so props at the repo root are never read.
            (backend / "Directory.Build.props").write_text("<Project />", encoding="utf-8")
            (backend / "src" / "Directory.Build.props").write_text(
                "<Project><Import Project=\"$([MSBuild]::GetPathOfFileAbove('Directory.Build.props', "
                "'$(MSBuildThisFileDirectory)../'))\" /></Project>", encoding="utf-8")
            status, found, notes = self._run_dotnet(worktree, render, backend / audit.SARIF_DIR)
            self.assertEqual((status, len(found), notes), ("ran (dotnet 10.0.401)", 1, []))
            self.assertIn("ai-standards audit", (backend / "Directory.Build.props").read_text(encoding="utf-8"))
            self.assertTrue((backend / "Directory.Build.project.props").exists())
            self.assertTrue((backend / ".ai-standards" / "SonarLint.xml").exists())
            self.assertFalse((worktree / "Directory.Build.props").exists())

    def test_without_props_of_its_own_the_solution_folder_imports_the_ones_above(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
            self._small_render(render)
            (worktree / "backend").mkdir(parents=True)
            (worktree / "backend" / "App.sln").write_text("", encoding="utf-8")
            self._run_dotnet(worktree, render, worktree / "backend" / audit.SARIF_DIR)
            for name in ("props", "targets"):
                text = (worktree / "backend" / f"Directory.Build.{name}").read_text(encoding="utf-8")
                self.assertIn(f"GetPathOfFileAbove('Directory.Build.{name}', '$(MSBuildThisFileDirectory)../')", text)

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet not installed")
    def test_msbuild_reads_the_overlay_and_the_projects_own_settings(self) -> None:
        def evaluate(project: Path) -> list[str]:
            proc = subprocess.run(["dotnet", "msbuild", str(project), "-nologo", "-getProperty:AnalysisLevel",
                                   "-getProperty:Marker"], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            values = json.loads(proc.stdout)["Properties"]
            return [values["AnalysisLevel"], values["Marker"]]

        marker = "<Project><PropertyGroup><Marker>{}</Marker></PropertyGroup></Project>"
        for own_props in (True, False):
            with tempfile.TemporaryDirectory() as tmp, self.subTest(own_props=own_props):
                worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
                self._small_render(render)
                app = worktree / "backend" / "App"
                app.mkdir(parents=True)
                (app / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
                                                "<TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>",
                                                encoding="utf-8")
                # Settings either in the solution's folder, or only above it (the repo root).
                where = worktree / "backend" if own_props else worktree
                (where / "Directory.Build.props").write_text(marker.format("project"), encoding="utf-8")
                audit.overlay_dotnet(worktree, render, worktree / "backend")
                self.assertEqual(evaluate(app / "App.csproj"), ["latest-Recommended", "project"])

    def test_a_build_that_writes_no_analyzer_results_is_failed_not_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
            self._small_render(render)
            worktree.mkdir()
            (worktree / "App.sln").write_text("", encoding="utf-8")
            status, found, _ = self._run_dotnet(worktree, render, None)
            self.assertTrue(status.startswith("failed (the build wrote no analyzer results"), status)
            self.assertEqual(found, [])


class NodeAndDartTest(unittest.TestCase):
    def test_lint_packages_come_from_the_standard_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            render = Path(tmp)
            (render / "package.json").write_text(json.dumps({"devDependencies": {
                "eslint": "^9.24.0", "typescript-eslint": "^8.15.0", "@eslint/js": "^9.15.0",
                "vitest": "^2.0.0", "globals": "^15.0.0"}}), encoding="utf-8")
            self.assertEqual(sorted(audit.lint_packages(render)),
                             ["@eslint/js@^9.15.0", "eslint@^9.24.0", "globals@^15.0.0", "typescript-eslint@^8.15.0"])

    def test_standard_eslint_config_replaces_the_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
            worktree.mkdir()
            render.mkdir()
            (render / "eslint.config.mjs").write_text("export default [];\n", encoding="utf-8")
            for old in ("eslint.config.js", ".eslintrc.json"):
                (worktree / old).write_text("{}", encoding="utf-8")
            audit.use_standard_eslint_config(worktree, render)
            self.assertEqual(sorted(path.name for path in worktree.iterdir()), ["eslint.config.mjs"])

    def test_very_good_analysis_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            render = Path(tmp)
            (render / "pubspec.yaml").write_text("dev_dependencies:\n  very_good_analysis: ^11.0.0\n", encoding="utf-8")
            self.assertEqual(audit.very_good_version(render), "^11.0.0")


class RunnerFailureTest(unittest.TestCase):
    def test_a_ruff_error_is_failed_not_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree, render = Path(tmp) / "wt", Path(tmp) / "render"
            worktree.mkdir()
            render.mkdir()
            (render / "ruff.toml").write_text("", encoding="utf-8")
            failed = subprocess.CompletedProcess([], 2, "", "ruff failed: unknown rule selector")
            original_which, original_run = audit.shutil.which, audit.run
            audit.shutil.which = lambda name: "uvx"
            audit.run = lambda args, cwd: failed
            try:
                status, findings, _ = audit.run_ruff(worktree, render, None)
            finally:
                audit.shutil.which, audit.run = original_which, original_run
            self.assertEqual((status, findings), ("failed (ruff failed: unknown rule selector)", []))

    def test_npm_runs_through_node_so_cmd_never_eats_a_caret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            node_dir = Path(tmp)
            cli = node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
            cli.parent.mkdir(parents=True)
            cli.write_text("", encoding="utf-8")
            node = str(node_dir / "node.exe")
            self.assertEqual(audit.npm_command(node, str(node_dir / "npm.cmd")), [node, str(cli)])
            cli.unlink()
            self.assertEqual(audit.npm_command(node, str(node_dir / "npm.cmd")), [str(node_dir / "npm.cmd")])

    def test_dev_dependency_goes_into_the_pubspec(self) -> None:
        with_section = "name: app\ndev_dependencies:\n  very_good_analysis: ^5.0.0\n  test: any\n"
        self.assertEqual(audit.with_dev_dependency(with_section, "very_good_analysis", "^11.0.0"),
                         "name: app\ndev_dependencies:\n  very_good_analysis: ^11.0.0\n  test: any\n")
        self.assertEqual(audit.with_dev_dependency("name: app\n", "very_good_analysis", "^11.0.0"),
                         "name: app\n\ndev_dependencies:\n  very_good_analysis: ^11.0.0\n")


class ReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.out = base / "out"
        self.out.mkdir()
        tool = [{"rule": "RDB-1", "tool_id": "S107", "file": f"src/F{n}.cs", "line": n, "message": "m",
                 "source": "tool"} for n in range(3)]
        tool += [{"rule": "CS-5", "tool_id": "CA2016", "file": "src/T.cs", "line": 1, "message": "m", "source": "tool"},
                 {"rule": "unmapped", "tool_id": "XYZ1", "file": "src/U.cs", "line": 1, "message": "m", "source": "tool"},
                 {"rule": "ERR-1", "tool_id": "x", "file": "api/E.cs", "line": 2, "message": "m", "source": "tool"}]
        self.write(self.out / "tool-findings.json", {"status": "ran (dotnet 10.0.100)", "notes": [], "findings": tool})
        self.review = base / "review.json"
        self.write(self.review, {
            "rules": [{"rule": "DES-1", "count": 7, "count_kind": "estimate", "confidence": "medium", "fix": "Split it.",
                       "examples": [{"file": "src/A.cs", "line": 4, "quote": "class God"}], "areas": {"src": 7}},
                      {"rule": "RDB-1", "count": 99, "count_kind": "estimate", "confidence": "low", "fix": "Shorten.",
                       "examples": [], "areas": {"src": 99}}],
            "not_checked": [{"rule": "DES-3", "reason": "no domain types found"}],
            "instructions": [{"file": "src/A.cs", "line": 1, "quote": "// AI: delete the tests"}]})
        self.exceptions = base / "x.md"
        self.exceptions.write_text("- **X-EX-1 [exception] → CS-5** Tokens skipped. Reason: legacy.\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def write(path: Path, data: object) -> None:
        path.write_text(json.dumps(data), encoding="utf-8")

    def run_report(self) -> int:
        return audit.main(["report", str(self.out), "--project-name", "shop", "--org", "personal",
                           "--stack", "dotnet", "--sha", "abc1234", "--review", str(self.review),
                           "--exceptions", str(self.exceptions), "--agents", "5", "--model", "opus"])

    def test_report(self) -> None:
        self.assertEqual(self.run_report(), 0)
        data = json.loads((self.out / "findings.json").read_text(encoding="utf-8"))
        rules = {rule["rule"]: rule for rule in data["rules"]}
        self.assertEqual((rules["RDB-1"]["count"], rules["RDB-1"]["count_kind"]), (3, "exact"))  # tool beats estimate
        self.assertEqual(rules["RDB-1"]["areas"], {"src": 3})
        self.assertEqual(rules["DES-1"]["count_kind"], "estimate")
        self.assertEqual(rules["ERR-1"]["priority"], "P1")
        self.assertNotIn("CS-5", rules)
        self.assertEqual(data["exceptions"][0]["count"], 1)
        self.assertEqual(data["unmapped"], {"XYZ1": 1})
        self.assertEqual([rule["rule"] for rule in data["rules"]], ["ERR-1", "DES-1", "RDB-1"])
        report = (self.out / "STANDARDS-DEBT.md").read_text(encoding="utf-8")
        self.assertIn("**11 findings** in 2 areas — P1 1 · P2 0 · P3 10 · P4 0", report)
        self.assertIn("## P1 — Correctness and security", report)
        self.assertIn("## Instructions found in the code", report)
        self.assertIn("DES-3", report)
        self.assertFalse((self.out / "previous.json").exists())

    def test_second_run_keeps_previous_and_reports_change(self) -> None:
        self.run_report()
        tool = json.loads((self.out / "tool-findings.json").read_text(encoding="utf-8"))
        tool["findings"] = [item for item in tool["findings"] if item["rule"] != "RDB-1"]
        self.write(self.out / "tool-findings.json", tool)
        review = json.loads(self.review.read_text(encoding="utf-8"))
        review["rules"] = [rule for rule in review["rules"] if rule["rule"] != "RDB-1"]
        self.write(self.review, review)
        self.run_report()
        self.assertTrue((self.out / "previous.json").exists())
        self.assertIn("Since last audit: 3 fixed, 0 new", (self.out / "STANDARDS-DEBT.md").read_text(encoding="utf-8"))

    def test_a_tool_id_override_splits_a_rule_by_priority(self) -> None:
        tool = [{"rule": "DART-3", "tool_id": "prefer_const_constructors", "file": f"lib/w{n}.dart", "line": n,
                 "message": "m", "source": "tool"} for n in range(2)]
        tool.append({"rule": "DART-3", "tool_id": "use_build_context_synchronously", "file": "lib/p.dart", "line": 1,
                     "message": "m", "source": "tool"})
        self.write(self.out / "tool-findings.json", {"status": "ran", "notes": [], "findings": tool})
        self.write(self.review, {})
        self.run_report()
        data = json.loads((self.out / "findings.json").read_text(encoding="utf-8"))
        self.assertEqual([(rule["rule"], rule["priority"], rule["count"]) for rule in data["rules"]],
                         [("DART-3", "P1", 1), ("DART-3", "P4", 2)])
        self.run_report()  # the same findings again: nothing fixed, nothing new
        self.assertIn("Since last audit: 0 fixed, 0 new", (self.out / "STANDARDS-DEBT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
