"""Audit an existing project against ai-standards, without changing the project.

  audit.py tools <project> --stack <stack> --org <org> --render <dir> --out <dir> [--solution <path>]

`tools` runs the stack's own analyzers with the standard configs inside a temporary git worktree of
the project's HEAD (the working tree, index and branches are never touched) and writes
<out>/tool-findings.json: {"status", "notes", "findings"}. Exit 0 whenever that file is written, even
when the tools were skipped or failed (the status says which); 2 on bad arguments; 3 when a dotnet
solution must be chosen (the candidates are printed; run again with --solution).

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rule_data import load_tool_map  # noqa: E402

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
    """A detached worktree of HEAD in a new temporary folder, outside the project."""
    parent = Path(tempfile.mkdtemp(prefix="ai-standards-audit-"))
    worktree = parent / "wt"
    proc = run(["git", "-C", str(project), "worktree", "add", "--detach", str(worktree), "HEAD"], project)
    if proc.returncode != 0:
        shutil.rmtree(parent, ignore_errors=True)
        raise RuntimeError(f"git worktree add failed: {first_error(proc)}")
    return worktree


def remove_worktree(project: Path, worktree: Path) -> None:
    """Remove the worktree this script created, and only that one, even after a failure."""
    run(["git", "-C", str(project), "worktree", "remove", "--force", str(worktree)], project)
    run(["git", "-C", str(project), "worktree", "prune"], project)
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
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return f"failed ({first_error(proc)})", [], []
    version = run([uvx, "ruff", "--version"], worktree).stdout.strip()
    return f"ran ({version})", parse_ruff(data), []


SARIF_DIR = ".ai-standards-audit"
# Written in the worktree only. The project's own root props are imported first, so its settings
# stay; ours come after them. The command line turns warnings-as-errors off for every project.
AUDIT_PROPS = """<Project>
  <!-- ai-standards audit: temporary worktree only. -->
  <Import Project="$(MSBuildThisFileDirectory)Directory.Build.project.props"
          Condition="Exists('$(MSBuildThisFileDirectory)Directory.Build.project.props')" />
  <PropertyGroup>
    <AnalysisLevel>latest-Recommended</AnalysisLevel>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
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
ANALYZERS = re.compile(r'PackageReference Include="(SonarAnalyzer\.CSharp|Microsoft\.CodeAnalysis\.BannedApiAnalyzers)"')


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


def analyzer_packages(render: Path, central: bool) -> str:
    """The standard's analyzer PackageReferences, VersionOverride under central package management."""
    lines = [line.strip() for line in (render / "Directory.Build.props").read_text(encoding="utf-8").splitlines()
             if ANALYZERS.search(line)]
    if central:
        lines = [line.replace(' Version="', ' VersionOverride="') for line in lines]
    return "\n".join(f"    {line}" for line in lines)


def cs_section(text: str) -> str:
    """The [*.cs] section of an .editorconfig."""
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("["):
            inside = line.strip() == "[*.cs]"
        if inside:
            lines.append(line)
    return "\n".join(lines)


def overlay_dotnet(worktree: Path, render: Path) -> None:
    props = worktree / "Directory.Build.props"
    if props.exists():
        props.rename(worktree / "Directory.Build.project.props")
    packages_file = worktree / "Directory.Packages.props"
    central = packages_file.exists() and "<ManagePackageVersionsCentrally>true" in packages_file.read_text(
        encoding="utf-8", errors="replace")
    props.write_text(AUDIT_PROPS.format(sarif_dir=SARIF_DIR, packages=analyzer_packages(render, central)),
                     encoding="utf-8")
    (worktree / SARIF_DIR).mkdir(exist_ok=True)  # the compiler won't create the ErrorLog's folder
    (worktree / ".ai-standards").mkdir(exist_ok=True)
    for name in ("SonarLint.xml", "BannedSymbols.txt"):
        shutil.copy(render / ".ai-standards" / name, worktree / ".ai-standards" / name)
    # Appended last, so the standard severities win over the project's own [*.cs] settings.
    editorconfig = worktree / ".editorconfig"
    existing = editorconfig.read_text(encoding="utf-8") if editorconfig.exists() else "root = true\n"
    standard = cs_section((render / ".editorconfig").read_text(encoding="utf-8"))
    editorconfig.write_text(f"{existing.rstrip()}\n\n# ai-standards audit (temporary worktree only)\n{standard}\n",
                            encoding="utf-8")


def run_dotnet(worktree: Path, render: Path, solution: str | None) -> tuple[str, list[Finding], list[str]]:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return "skipped (dotnet not found)", [], []
    target = worktree / solution if solution else pick_solution(worktree)
    if target is None:
        return "failed (no solution or project found)", [], []
    overlay_dotnet(worktree, render)
    notes = [f"{path.relative_to(worktree).as_posix()} doesn't import the root props: its projects may be missed"
             for path in worktree.rglob("Directory.Build.props")
             if path.parent != worktree and not SKIP.search(path.relative_to(worktree).as_posix())
             and "GetPathOfFileAbove" not in path.read_text(encoding="utf-8", errors="replace")]
    proc = run([dotnet, "build", str(target), "--nologo",
                "-p:TreatWarningsAsErrors=false", "-p:CodeAnalysisTreatWarningsAsErrors=false"], worktree)
    found = [finding for sarif in sorted((worktree / SARIF_DIR).glob("*.sarif"))
             for finding in parse_sarif(sarif.read_text(encoding="utf-8"))]
    version = run([dotnet, "--version"], worktree).stdout.strip()
    status = f"ran (dotnet {version})" if proc.returncode == 0 else f"failed ({first_error(proc)})"
    return status, found, notes


RUNNERS: dict[str, Runner] = {"python": run_ruff, "dotnet": run_dotnet}


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
    args = parser.parse_args(argv)
    return tools(args)


if __name__ == "__main__":
    sys.exit(main())
