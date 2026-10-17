"""Audit an existing project against ai-standards, without changing the project.

  audit.py tools <project> --stack <stack> --org <org> --render <dir> --out <dir> [--solution <path>]

`tools` runs the stack's own analyzers with the standard configs inside a temporary git worktree of
the project's HEAD (the working tree, index and branches are never touched) and writes
<out>/tool-findings.json: {"status", "notes", "findings"}. Exit 0 whenever that file is written, even
when the tools were skipped or failed (the status says which); 2 on bad arguments; 3 when a dotnet
solution must be chosen (the candidates are printed; run again with --solution).

  audit.py report <out> --project-name <n> --org <o> --stack <s> --sha <sha> [--review <file>]
                  [--exceptions <project rules .md>] [--agents <n>] [--model <m>]

`report` merges the tool and review findings, applies the project's exceptions and the rule
priorities, and writes STANDARDS-DEBT.md, findings.json and previous.json (the last run) in <out>.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rule_data import PRIORITY_TITLES, load_priorities, load_tool_map, priority  # noqa: E402

STACKS = ("typescript", "angular", "python", "dotnet", "flutter")
TOOL_FINDINGS = "tool-findings.json"
# Build output, dependencies, migrations and generated code are never findings.
SKIP = re.compile(
    r"(^|/)(bin|obj|node_modules|\.dart_tool|build|dist|\.ai-standards-audit|\.ai-session|[Mm]igrations)/"
    r"|\.g\.dart$|\.freezed\.dart$|\.[Dd]esigner\.cs$"
)

Finding = dict[str, object]
Runner = Callable[[Path, Path, "str | None"], "tuple[str, list[Finding], list[str]]"]


class Ambiguous(Exception):
    """Several dotnet solutions qualify; the caller picks one with --solution."""


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # fixed argument lists, no shell
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )


def first_error(proc: subprocess.CompletedProcess[str]) -> str:
    """The first line that mentions an error, else the last line: why a run failed."""
    lines = [line.strip() for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    for line in lines:
        if "error" in line.lower():
            return line[:200]
    return lines[-1][:200] if lines else f"exit {proc.returncode}"


def make_worktree(project: Path) -> Path:
    """A detached worktree of HEAD in a new temporary folder, outside the project.

    The project's hooks don't run (an empty hooks folder), and Git LFS doesn't download anything.
    """
    parent = Path(tempfile.mkdtemp(prefix="ai-standards-audit-"))
    worktree, no_hooks = parent / "wt", parent / "no-hooks"
    no_hooks.mkdir()
    proc = subprocess.run(  # noqa: S603  # fixed argument list, no shell
        ["git", "-c", f"core.hooksPath={no_hooks}", "-C", str(project), "worktree", "add", "--detach",
         str(worktree), "HEAD"],
        cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})
    if proc.returncode != 0:
        shutil.rmtree(parent, ignore_errors=True)
        raise RuntimeError(f"git worktree add failed: {first_error(proc)}")
    return worktree


def remove_worktree(project: Path, worktree: Path) -> None:
    """Remove the worktree this script created, and only that one, even after a failure.

    Never `git worktree prune`: it would also drop the metadata of the user's other worktrees whose
    folders are missing for now.
    """
    admin = run(["git", "-C", str(worktree), "rev-parse", "--absolute-git-dir"], worktree).stdout.strip()
    removed = run(["git", "-C", str(project), "worktree", "remove", "--force", str(worktree)], project)
    if removed.returncode != 0 and admin and Path(admin).parent.name == "worktrees":
        shutil.rmtree(admin, ignore_errors=True)  # this worktree's own metadata, nothing else
    shutil.rmtree(worktree.parent, ignore_errors=True)


def uri_to_path(uri: str) -> str:
    if not uri.startswith("file:"):
        return unquote(uri)
    parsed = urlparse(uri)
    path = unquote(parsed.path)
    return url2pathname(f"//{parsed.netloc}{path}" if parsed.netloc else path)


def parse_sarif(text: str) -> list[Finding]:
    found: list[Finding] = []
    for sarif_run in json.loads(text).get("runs", []):
        for result in sarif_run.get("results", []):
            locations = result.get("locations") or []
            if result.get("suppressions") or not locations:
                continue  # suppressed in source, or not tied to a file
            physical = locations[0].get("physicalLocation", {})
            uri = physical.get("artifactLocation", {}).get("uri", "")
            if uri:
                found.append({"tool_id": result.get("ruleId", ""), "file": uri_to_path(uri),
                              "line": physical.get("region", {}).get("startLine"),
                              "message": result.get("message", {}).get("text", "")})
    return found


def parse_eslint(data: list[dict]) -> list[Finding]:
    return [{"tool_id": message["ruleId"], "file": file.get("filePath", ""), "line": message.get("line"),
             "message": message.get("message", "")}
            for file in data for message in file.get("messages", []) if message.get("ruleId")]


def parse_ruff(data: list[dict]) -> list[Finding]:
    return [{"tool_id": item["code"], "file": item.get("filename", ""),
             "line": (item.get("location") or {}).get("row"), "message": item.get("message", "")}
            for item in data if item.get("code")]


def parse_dart_machine(text: str) -> list[Finding]:
    """`dart analyze --format=machine`: SEVERITY|TYPE|CODE|FILE|LINE|COLUMN|LENGTH|MESSAGE."""
    found: list[Finding] = []
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) >= 8 and parts[0] in ("INFO", "WARNING", "ERROR"):
            found.append({"tool_id": parts[2].lower(), "file": parts[3],
                          "line": int(parts[4]) if parts[4].isdigit() else None,
                          "message": "|".join(parts[7:])})
    return found


def normalize(raw: list[Finding], base: Path, tool_map: dict[str, str]) -> list[Finding]:
    """Project-relative paths, rule IDs, no duplicates (multi-targeting), no generated code."""
    root = base.resolve()
    seen: set[tuple[object, str, object]] = set()
    out: list[Finding] = []
    for item in raw:
        path = Path(str(item["file"]))
        if path.is_absolute():
            try:
                relative = path.resolve().relative_to(root).as_posix()
            except ValueError:
                continue  # outside the project, such as a package's source file
        else:
            relative = path.as_posix()
        key = (item["tool_id"], relative, item["line"])
        if SKIP.search(relative) or key in seen:
            continue
        seen.add(key)
        out.append({"rule": tool_map.get(str(item["tool_id"]), "unmapped"), "tool_id": item["tool_id"],
                    "file": relative, "line": item["line"], "message": str(item["message"]).strip(),
                    "source": "tool"})
    return out


def run_ruff(worktree: Path, render: Path, _solution: str | None) -> tuple[str, list[Finding], list[str]]:
    uvx = shutil.which("uvx")
    if not uvx:
        return "skipped (uv not found)", [], []
    # The standard config at the root wins over the project's pyproject.toml settings.
    (worktree / ".ruff.toml").unlink(missing_ok=True)
    shutil.copy(render / "ruff.toml", worktree / "ruff.toml")
    proc = run([uvx, "ruff", "check", ".", "--output-format", "json", "--exit-zero", "--no-cache"], worktree)
    if proc.returncode != 0:  # --exit-zero: only an error (bad config, no download) lands here
        return f"failed ({first_error(proc)})", [], []
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return f"failed ({first_error(proc)})", [], []
    version = run([uvx, "ruff", "--version"], worktree).stdout.strip()
    return f"ran ({version})", parse_ruff(data), []


SARIF_DIR = ".ai-standards-audit"
# Written in the worktree only. The project's own root props are imported first, so its settings
# stay; ours come after them. Analyzer packages are added both ways, and MSBuild keeps the one that
# matches central package management, wherever the project turns it on. Test projects get the same
# exemptions as in the template (no banned-API checks, no doc comments).
AUDIT_PROPS = """<Project>
  <!-- ai-standards audit: temporary worktree only. -->
  <Import Project="$(MSBuildThisFileDirectory)Directory.Build.project.props"
          Condition="Exists('$(MSBuildThisFileDirectory)Directory.Build.project.props')" />
  <PropertyGroup>
    <_AiStandardsPropsAbove>$([MSBuild]::GetPathOfFileAbove('Directory.Build.props', '$(MSBuildThisFileDirectory)../'))</_AiStandardsPropsAbove>
  </PropertyGroup>
  <Import Project="$(_AiStandardsPropsAbove)"
          Condition="!Exists('$(MSBuildThisFileDirectory)Directory.Build.project.props') And '$(_AiStandardsPropsAbove)' != ''" />
  <PropertyGroup>
    <AnalysisLevel>latest-Recommended</AnalysisLevel>
    <GenerateDocumentationFile>true</GenerateDocumentationFile>
    <Nullable>enable</Nullable>
    <ErrorLog>$(MSBuildThisFileDirectory){sarif_dir}/$(MSBuildProjectName)-$(TargetFramework).sarif,version=2.1</ErrorLog>
  </PropertyGroup>
  <ItemGroup>
{packages}
    <AdditionalFiles Include="$(MSBuildThisFileDirectory).ai-standards/SonarLint.xml" />
    <AdditionalFiles Include="$(MSBuildThisFileDirectory).ai-standards/BannedSymbols.txt" />
  </ItemGroup>
</Project>
"""
# Imported after each project file, so a project can't switch the analyzers off, turn warnings into
# errors, or hide a standard rule with NoWarn.
AUDIT_TARGETS = """<Project>
  <!-- ai-standards audit: temporary worktree only. -->
  <Import Project="$(MSBuildThisFileDirectory)Directory.Build.project.targets"
          Condition="Exists('$(MSBuildThisFileDirectory)Directory.Build.project.targets')" />
  <PropertyGroup>
    <_AiStandardsTargetsAbove>$([MSBuild]::GetPathOfFileAbove('Directory.Build.targets', '$(MSBuildThisFileDirectory)../'))</_AiStandardsTargetsAbove>
  </PropertyGroup>
  <Import Project="$(_AiStandardsTargetsAbove)"
          Condition="!Exists('$(MSBuildThisFileDirectory)Directory.Build.project.targets') And '$(_AiStandardsTargetsAbove)' != ''" />
  <PropertyGroup>
    <RunAnalyzers>true</RunAnalyzers>
    <RunAnalyzersDuringBuild>true</RunAnalyzersDuringBuild>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>
    <CodeAnalysisTreatWarningsAsErrors>false</CodeAnalysisTreatWarningsAsErrors>
    <WarningsAsErrors></WarningsAsErrors>
  </PropertyGroup>
  <Target Name="AiStandardsAuditKeepStandardWarnings" BeforeTargets="CoreCompile">
    <ItemGroup>
      <_AiStandardsNoWarn Include="$(NoWarn)" Exclude="{standard_ids}" />
      <_AiStandardsNoWarn Include="CS1591;CA1707" Condition="$(MSBuildProjectName.EndsWith('Tests'))" />
    </ItemGroup>
    <PropertyGroup>
      <NoWarn>@(_AiStandardsNoWarn)</NoWarn>
    </PropertyGroup>
  </Target>
</Project>
"""
PACKAGE = re.compile(
    r'<PackageReference Include="(SonarAnalyzer\.CSharp|Microsoft\.CodeAnalysis\.BannedApiAnalyzers)" Version="([^"]+)"')


def project_count(solution: Path) -> int:
    text = solution.read_text(encoding="utf-8", errors="replace")
    return len(set(re.findall(r"[\w./\\-]+\.csproj", text)))


def pick_solution(root: Path) -> Path | None:
    """The root's solution (or the one two levels down at most) with the most projects; else a lone csproj."""
    candidates: list[Path] = []
    for depth in range(3):
        pattern = "/".join(["*"] * depth + ["*.sln*"])
        candidates = sorted(path for path in root.glob(pattern)
                            if path.suffix in (".sln", ".slnx")
                            and not SKIP.search(path.relative_to(root).as_posix()))
        if candidates:
            break
    if not candidates:
        projects = sorted(root.glob("*.csproj"))
        if len(projects) > 1:
            raise Ambiguous([path.name for path in projects])
        return projects[0] if projects else None
    if len(candidates) == 1:
        return candidates[0]
    counts = {path: project_count(path) for path in candidates}
    best = [path for path, count in counts.items() if count == max(counts.values())]
    if len(best) > 1:
        raise Ambiguous([path.relative_to(root).as_posix() for path in best])
    return best[0]


def analyzer_packages(render: Path) -> str:
    """The standard's analyzer packages, once with Version and once with VersionOverride."""
    lines: list[str] = []
    text = (render / "Directory.Build.props").read_text(encoding="utf-8")
    for name, version in PACKAGE.findall(text):
        not_tests = " and !$(MSBuildProjectName.EndsWith('Tests'))" if "BannedApi" in name else ""
        for attribute, central in (("Version", "!="), ("VersionOverride", "==")):
            condition = f"'$(ManagePackageVersionsCentrally)' {central} 'true'{not_tests}"
            lines.append(f'    <PackageReference Include="{name}" {attribute}="{version}" PrivateAssets="all"'
                         f' Condition="{condition}" />')
    return "\n".join(lines)


def cs_sections(text: str) -> str:
    """Every C# section of an .editorconfig ([*.cs], [tests/**.cs], …)."""
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("["):
            inside = ".cs" in line
        if inside:
            lines.append(line)
    return "\n".join(lines)


def standard_ids() -> list[str]:
    """The diagnostic IDs the standard maps to rules, plus the bare number NoWarn also accepts for CS IDs."""
    ids = sorted(load_tool_map("dotnet"))
    return ids + [rule_id[2:] for rule_id in ids if rule_id.startswith("CS")]


def overlay_dotnet(worktree: Path, render: Path, base: Path | None = None) -> None:
    """The audit's props and targets go in `base`, the solution's folder: MSBuild stops at the nearest
    Directory.Build.props, so a copy at the repo root is never read when the solution has its own."""
    base = base or worktree
    for name, renamed in (("Directory.Build.props", "Directory.Build.project.props"),
                          ("Directory.Build.targets", "Directory.Build.project.targets")):
        if (base / name).exists():
            (base / name).rename(base / renamed)
    (base / "Directory.Build.props").write_text(
        AUDIT_PROPS.format(sarif_dir=SARIF_DIR, packages=analyzer_packages(render)), encoding="utf-8")
    (base / "Directory.Build.targets").write_text(
        AUDIT_TARGETS.format(standard_ids=";".join(standard_ids())), encoding="utf-8")
    (base / SARIF_DIR).mkdir(exist_ok=True)  # the compiler won't create the ErrorLog's folder
    (base / ".ai-standards").mkdir(exist_ok=True)
    for name in ("SonarLint.xml", "BannedSymbols.txt"):
        shutil.copy(render / ".ai-standards" / name, base / ".ai-standards" / name)
    # A rule silenced by ID beats an option's ":warning" suffix, so the standard's IDE rules are set by
    # ID too. The block goes last in every .editorconfig, nested ones included: later entries win.
    explicit = "\n".join(f"dotnet_diagnostic.{rule_id}.severity = warning"
                         for rule_id in sorted(load_tool_map("dotnet")) if rule_id.startswith("IDE"))
    block = (f"\n\n# ai-standards audit (temporary worktree only)\n"
             f"{cs_sections((render / '.editorconfig').read_text(encoding='utf-8'))}\n\n[*.cs]\n{explicit}\n")
    editorconfigs = [path for path in worktree.rglob(".editorconfig")
                     if not SKIP.search(path.relative_to(worktree).as_posix())]
    if worktree / ".editorconfig" not in editorconfigs:
        (worktree / ".editorconfig").write_text("root = true\n", encoding="utf-8")
        editorconfigs.append(worktree / ".editorconfig")
    for path in editorconfigs:
        path.write_text(path.read_text(encoding="utf-8").rstrip() + block, encoding="utf-8")


def run_dotnet(worktree: Path, render: Path, solution: str | None) -> tuple[str, list[Finding], list[str]]:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return "skipped (dotnet not found)", [], []
    target = worktree / solution if solution else pick_solution(worktree)
    if target is None:
        return "failed (no solution or project found)", [], []
    base = target.parent
    overlay_dotnet(worktree, render, base)
    notes = [f"{path.relative_to(worktree).as_posix()} doesn't import the root props: its projects may be missed"
             for path in base.rglob("Directory.Build.props")
             if path.parent != base and not SKIP.search(path.relative_to(worktree).as_posix())
             and "GetPathOfFileAbove" not in path.read_text(encoding="utf-8", errors="replace")]
    proc = run([dotnet, "build", str(target), "--nologo",
                "-p:TreatWarningsAsErrors=false", "-p:CodeAnalysisTreatWarningsAsErrors=false"], worktree)
    sarifs = sorted((base / SARIF_DIR).glob("*.sarif"))
    found = [finding for sarif in sarifs for finding in parse_sarif(sarif.read_text(encoding="utf-8"))]
    version = run([dotnet, "--version"], worktree).stdout.strip()
    status = f"ran (dotnet {version})" if proc.returncode == 0 else f"failed ({first_error(proc)})"
    if proc.returncode == 0 and not sarifs:  # analyzers that never ran look exactly like clean code
        status = "failed (the build wrote no analyzer results: the audit's props weren't imported)"
    return status, found, notes


ESLINT_CONFIGS = ("eslint.config.js", "eslint.config.cjs", "eslint.config.ts", "eslint.config.mts",
                  "eslint.config.cts", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
                  ".eslintrc.yml", ".eslintrc.yaml")


def lint_packages(render: Path) -> list[str]:
    """The standard's lint packages, at its versions: every devDependency named *eslint*, plus globals."""
    dev = json.loads((render / "package.json").read_text(encoding="utf-8")).get("devDependencies", {})
    return [f"{name}@{version}" for name, version in dev.items() if "eslint" in name or name == "globals"]


def use_standard_eslint_config(worktree: Path, render: Path) -> None:
    """ESLint picks eslint.config.js before .mjs, so the project's configs go."""
    for name in ESLINT_CONFIGS:
        (worktree / name).unlink(missing_ok=True)
    shutil.copy(render / "eslint.config.mjs", worktree / "eslint.config.mjs")


def npm_command(node: str, npm: str) -> list[str]:
    """npm run by node directly: through npm.cmd, cmd.exe would eat the ^ in "eslint@^9.24.0"."""
    cli = Path(node).parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    return [node, str(cli)] if cli.exists() else [npm]


def run_eslint(worktree: Path, render: Path, _solution: str | None) -> tuple[str, list[Finding], list[str]]:
    node, npm = shutil.which("node"), shutil.which("npm")
    if not (node and npm):
        return "skipped (node not found)", [], []
    use_standard_eslint_config(worktree, render)
    notes = [f"installed with npm; the project uses {lock}" for lock in ("pnpm-lock.yaml", "yarn.lock")
             if (worktree / lock).exists()]
    flags = ["--ignore-scripts", "--no-audit", "--no-fund"]
    npm_cmd = npm_command(node, npm)
    install = run([*npm_cmd, "ci" if (worktree / "package-lock.json").exists() else "install", *flags], worktree)
    if install.returncode != 0:
        return f"failed ({first_error(install)})", [], notes
    added = run([*npm_cmd, "install", "--no-save", *flags, *lint_packages(render)], worktree)
    if added.returncode != 0:
        return f"failed ({first_error(added)})", [], notes
    eslint = str(worktree / "node_modules" / "eslint" / "bin" / "eslint.js")
    proc = run([node, eslint, ".", "-f", "json"], worktree)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return f"failed ({first_error(proc)})", [], notes
    version = run([node, eslint, "--version"], worktree).stdout.strip()
    return f"ran (eslint {version})", parse_eslint(data), notes


def very_good_version(render: Path) -> str:
    match = re.search(r"very_good_analysis:\s*(\S+)", (render / "pubspec.yaml").read_text(encoding="utf-8"))
    return match.group(1) if match else "any"


def with_dev_dependency(pubspec: str, name: str, version: str) -> str:
    """The pubspec with `name: version` under dev_dependencies (replacing any other version of it).

    Written into the file, because `flutter pub add` goes through flutter.bat, where cmd.exe eats ^.
    """
    lines = pubspec.splitlines()
    entry = f"  {name}: {version}"
    if "dev_dependencies:" not in lines:
        return pubspec.rstrip("\n") + f"\n\ndev_dependencies:\n{entry}\n"
    start = lines.index("dev_dependencies:")
    end = next((i for i in range(start + 1, len(lines)) if lines[i] and not lines[i].startswith(" ")), len(lines))
    section = [line for line in lines[start + 1:end] if not line.strip().startswith(f"{name}:")]
    return "\n".join([*lines[:start + 1], entry, *section, *lines[end:]]) + "\n"


def run_dart(worktree: Path, render: Path, _solution: str | None) -> tuple[str, list[Finding], list[str]]:
    flutter = shutil.which("flutter")
    if not flutter:
        return "skipped (flutter not found)", [], []
    dart = shutil.which("dart") or str(Path(flutter).parent / "dart")
    shutil.copy(render / "analysis_options.yaml", worktree / "analysis_options.yaml")
    pubspec = worktree / "pubspec.yaml"
    pubspec.write_text(with_dev_dependency(pubspec.read_text(encoding="utf-8"), "very_good_analysis",
                                           very_good_version(render)), encoding="utf-8")
    added = run([flutter, "pub", "get"], worktree)
    if added.returncode != 0:
        return f"failed ({first_error(added)})", [], []
    proc = run([dart, "analyze", "--format=machine", "."], worktree)
    version = run([dart, "--version"], worktree)
    return (f"ran ({(version.stdout or version.stderr).strip()})",
            parse_dart_machine(proc.stdout + "\n" + proc.stderr), [])


RUNNERS: dict[str, Runner] = {"python": run_ruff, "dotnet": run_dotnet, "typescript": run_eslint,
                              "angular": run_eslint, "flutter": run_dart}


def tools(args: argparse.Namespace) -> int:
    project, out = args.project.resolve(), args.out.resolve()
    if args.stack not in RUNNERS:
        sys.stderr.write(f"no tools for stack {args.stack!r}\n")
        return 2
    if run(["git", "-C", str(project), "rev-parse", "--verify", "HEAD"], project).returncode != 0:
        sys.stderr.write(f"{project} is not a git repository with a commit\n")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    worktree = make_worktree(project)
    try:
        status, raw, notes = RUNNERS[args.stack](worktree, args.render.resolve(), args.solution)
        findings = normalize(raw, worktree, load_tool_map(args.stack, args.org))
    except Ambiguous as choices:
        print("Several solutions qualify. Run again with --solution and one of:")
        print("\n".join(f"  {choice}" for choice in choices.args[0]))
        return 3
    except Exception as error:  # noqa: BLE001  # a crash is reported in the status, never fatal
        status, findings, notes = f"failed ({error})", [], []
    finally:
        remove_worktree(project, worktree)
    result = {"status": status, "notes": notes, "findings": findings}
    (out / TOOL_FINDINGS).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[ai-standards] tools: {status}; {len(findings)} findings in {out / TOOL_FINDINGS}")
    return 0


EXAMPLES = 5
ORDER = ("P1", "P2", "P3", "P4")
REPORT, FINDINGS, PREVIOUS = "STANDARDS-DEBT.md", "findings.json", "previous.json"
EXCEPTION = re.compile(r"^- \*\*([A-Z][A-Z0-9]*-EX-\d+) \[exception\] → ([A-Z][A-Z0-9]*-\d+)\*\* (.+)$")


def read_json(path: Path | None, default: object) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else default


def exceptions_in(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    return [{"id": m.group(1), "target": m.group(2), "text": m.group(3)}
            for line in path.read_text(encoding="utf-8").splitlines() if (m := EXCEPTION.match(line))]


def area(file: str) -> str:
    """The top-level folder: one item of work per rule and folder."""
    parts = file.split("/")
    return parts[0] if len(parts) > 1 else "(root)"


def aggregate(tool_findings: list[dict], review: dict, priorities: dict) -> dict[tuple[str, str], dict]:
    """Findings per rule and priority: a tool ID with its own priority splits its rule in two."""
    rules: dict[tuple[str, str], dict] = {}

    def entry(rule: str, level: str) -> dict:
        return rules.setdefault((rule, level), {"rule": rule, "priority": level, "kind": "violation", "count": 0,
                                                "count_kind": "exact", "sources": [], "confidence": "high",
                                                "fix": "", "examples": [], "areas": Counter()})

    for finding in tool_findings:
        if finding["rule"] == "unmapped":
            continue
        item = entry(finding["rule"], priority(finding["rule"], priorities, finding["tool_id"]))
        item["count"] += 1
        item["areas"][area(finding["file"])] += 1
        if "tool" not in item["sources"]:
            item["sources"].append("tool")
        if len(item["examples"]) < EXAMPLES:
            item["examples"].append({"file": finding["file"], "line": finding["line"], "quote": finding["message"]})
    for reported in review.get("rules", []):
        item = entry(reported["rule"], priority(reported["rule"], priorities))
        item["kind"] = reported.get("kind", item["kind"])
        if "review" not in item["sources"]:
            item["sources"].append("review")
        if "tool" not in item["sources"]:  # a tool's exact count beats an estimate
            item["count"] += int(reported.get("count", 0))
            item["count_kind"] = reported.get("count_kind", "estimate")
            item["confidence"] = reported.get("confidence", "medium")
            item["areas"].update({name: int(n) for name, n in (reported.get("areas") or {}).items()})
        item["fix"] = item["fix"] or reported.get("fix", "")
        seen = {(example["file"], example["line"]) for example in item["examples"]}
        for example in reported.get("examples", []):
            if len(item["examples"]) < EXAMPLES and (example.get("file"), example.get("line")) not in seen:
                item["examples"].append(example)
    return {key: item for key, item in rules.items() if item["count"] > 0}


def change(previous: dict, current: list[dict]) -> dict[str, int]:
    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    for rule in previous.get("rules", []):
        before[rule["rule"]] += rule["count"]
    for rule in current:
        after[rule["rule"]] += rule["count"]
    return {"fixed": sum((before - after).values()), "new": sum((after - before).values())}


def rule_lines(rule: dict) -> list[str]:
    examples = ", ".join(f"`{e['file']}:{e['line']}` {e.get('quote', '')}".rstrip() for e in rule["examples"])
    areas = " · ".join(f"{name} ({n})" for name, n in rule["areas"].items())
    return [f"### {rule['rule']} — {rule['count']} ({rule['count_kind']}) · {' + '.join(rule['sources'])}"
            f" · {rule['confidence']}", "",
            *([f"How to fix: {rule['fix']}", ""] if rule["fix"] else []),
            *([f"Examples: {examples}", ""] if examples else []),
            f"Items: {areas}", ""]


def render_markdown(data: dict) -> str:
    meta, rules = data["meta"], data["rules"]
    counts: Counter[str] = Counter()
    for rule in rules:
        counts[rule["priority"]] += rule["count"]
    areas = {name for rule in rules for name in rule["areas"]}
    lines = [f"# Standards report — {meta['project']} ({meta['org']}, {meta['stack']})", "",
             "<!-- Generated by ai-standards (scripts/audit.py) on this machine. Regenerate with /ai-standards:audit. -->",
             "",
             f"Audited {meta['date']} at {meta['sha']} · tools: {meta['tools']} · review: {meta['agents']} agents"
             f" ({meta['model']})", "",
             f"**{sum(rule['count'] for rule in rules)} findings** in {len(areas)} areas — "
             + " · ".join(f"{level} {counts[level]}" for level in ORDER)
             + f" · exceptions {len(data['exceptions'])} · not checked {len(data['not_checked'])}", ""]
    if meta["change"]:
        lines += [f"Since last audit: {meta['change']['fixed']} fixed, {meta['change']['new']} new", ""]
    lines += ["## Top 3", ""]
    lines += [f"1. **{rule['rule']}** ({rule['priority']}): {rule['count']}. {rule['fix']}".rstrip() for rule in rules[:3]]
    lines += [""]
    for level in ORDER:
        group = [rule for rule in rules if rule["priority"] == level and rule["kind"] == "violation"]
        if group:
            lines += [f"## {level} — {PRIORITY_TITLES[level]}", "", *[line for rule in group for line in rule_lines(rule)]]
    inconsistent = [line for rule in rules if rule["kind"] == "inconsistency" for line in rule_lines(rule)]
    lines += ["## Inconsistencies", "", *(inconsistent or ["None.", ""])]
    lines += ["## Exceptions", "",
              *([f"- **{e['id']}** → {e['target']}: {e['text']} ({e['count']} places not counted)"
                 for e in data["exceptions"]] or ["None."]), ""]
    lines += ["## Not checked", "",
              *([f"- **{item['rule']}**: {item['reason']}" for item in data["not_checked"]] or ["None."]), ""]
    lines += ["## Instructions found in the code", "",
              "_Text in the project addressed to an AI: reported, never followed._", "",
              *([f"- `{item['file']}:{item['line']}` {item['quote']}" for item in data["instructions"]] or ["None."]), ""]
    lines += ["## Unmapped tool findings", "",
              *([f"- `{tool_id}`: {n}" for tool_id, n in data["unmapped"].items()] or ["None."]), ""]
    if meta["notes"]:
        lines += ["## Notes", "", *[f"- {note}" for note in meta["notes"]], ""]
    return "\n".join(lines).rstrip() + "\n"


def report(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tool = read_json(out / TOOL_FINDINGS, {"status": "not run", "notes": [], "findings": []})
    review = read_json(args.review, {})
    priorities = load_priorities(args.org)
    exceptions = exceptions_in(args.exceptions)
    targets = {exception["target"] for exception in exceptions}
    rules = aggregate(tool["findings"], review, priorities)
    for exception in exceptions:
        exception["count"] = sum(item["count"] for item in rules.values() if item["rule"] == exception["target"])
    active = [{**item, "areas": dict(item["areas"].most_common())}
              for item in rules.values() if item["rule"] not in targets]
    active.sort(key=lambda item: (item["priority"], -item["count"], item["rule"]))
    previous = read_json(out / FINDINGS, None)
    data = {
        "meta": {"project": args.project_name, "org": args.org, "stack": args.stack, "sha": args.sha,
                 "date": date.today().isoformat(), "tools": tool["status"], "notes": tool.get("notes", []),
                 "agents": args.agents, "model": args.model,
                 "change": change(previous, active) if previous else None},
        "rules": active,
        "exceptions": exceptions,
        "not_checked": review.get("not_checked", []),
        "instructions": review.get("instructions", []),
        "unmapped": dict(Counter(f["tool_id"] for f in tool["findings"] if f["rule"] == "unmapped").most_common()),
    }
    if previous is not None:
        (out / PREVIOUS).write_text(json.dumps(previous, indent=2), encoding="utf-8")
    (out / FINDINGS).write_text(json.dumps(data, indent=2), encoding="utf-8")
    (out / REPORT).write_text(render_markdown(data), encoding="utf-8")
    counts: Counter[str] = Counter()
    for item in active:
        counts[item["priority"]] += item["count"]
    print(f"[ai-standards] report: {sum(item['count'] for item in active)} findings "
          f"({', '.join(f'{level} {counts[level]}' for level in ORDER)}) in {out / REPORT}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    tools_cmd = commands.add_parser("tools", help="run the stack's analyzers in a temporary worktree")
    tools_cmd.add_argument("project", type=Path)
    tools_cmd.add_argument("--stack", required=True, choices=STACKS)
    tools_cmd.add_argument("--org", required=True)
    tools_cmd.add_argument("--render", required=True, type=Path)
    tools_cmd.add_argument("--out", required=True, type=Path)
    tools_cmd.add_argument("--solution")
    report_cmd = commands.add_parser("report", help="merge tool and review findings into the report")
    report_cmd.add_argument("out", type=Path)
    report_cmd.add_argument("--project-name", required=True)
    report_cmd.add_argument("--org", required=True)
    report_cmd.add_argument("--stack", required=True, choices=STACKS)
    report_cmd.add_argument("--sha", required=True)
    report_cmd.add_argument("--review", type=Path)
    report_cmd.add_argument("--exceptions", type=Path)
    report_cmd.add_argument("--agents", type=int, default=0)
    report_cmd.add_argument("--model", default="none")
    args = parser.parse_args(argv)
    return tools(args) if args.command == "tools" else report(args)


if __name__ == "__main__":
    sys.exit(main())
