"""Audit a project against ai-standards and write a prioritized debt plan for humans and AI.

Usage: python standards_audit.py <project-dir> [--output docs/STANDARDS-DEBT.md] [--stdout]

Reads the stack and adoption answers from .copier-answers.yml, measures the debt that is
baselined or deferred, and writes docs/STANDARDS-DEBT.md: a checklist ordered by risk
(correctness and security first, cosmetics last), with the exact commands to pay each item and
to ratchet the standards up once an area is clean. Standard library only.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ANSWERS_FILE = ".copier-answers.yml"
DEFAULT_OUTPUT = "docs/STANDARDS-DEBT.md"
TOP_FILES = 5

# (priority, title, rule-id patterns). First match wins; unmatched rules fall into the last bucket.
CATEGORIES: list[tuple[str, str, tuple[str, ...]]] = [
    ("P1", "Correctness and security", (
        r"no-floating-promises", r"no-misused-promises", r"eqeqeq", r"no-empty", r"switch-exhaustiveness",
        r"no-unsafe-", r"restrict-", r"no-unnecessary-condition", r"no-restricted-imports",
        r"^E722$", r"^BLE", r"^S\d", r"^B\d", r"^TRY", r"^PLW", r"^TID", r"^A\d",
    )),
    ("P2", "Types", (
        r"no-explicit-any", r"explicit-module-boundary-types", r"no-non-null-assertion",
        r"consistent-type-imports", r"^ANN", r"^typecheck$",
    )),
    ("P3", "Readability and size", (
        r"complexity", r"^max-", r"no-magic-numbers", r"naming-convention", r"no-nested-ternary",
        r"no-else-return", r"^C90", r"^PLR", r"^N\d", r"^SIM", r"^RET", r"^ERA", r"^C4",
    )),
    ("P4", "Style and hygiene", (r".",)),
]

HINTS = {
    "P1": "Real bugs or security risks. Fix first; each fix needs a test that fails without it.",
    "P2": "Replace `any`/missing types with precise ones. Type the boundaries first (APIs, DTOs).",
    "P3": "Refactor one function or module at a time, behavior unchanged, existing tests green.",
    "P4": "Mostly mechanical. Batch per rule; auto-fix where the tool can.",
}


@dataclass
class Debt:
    by_rule: Counter[str] = field(default_factory=Counter)
    files_by_rule: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    notes: list[str] = field(default_factory=list)

    def add(self, rule: str, file: str, count: int = 1) -> None:
        self.by_rule[rule] += count
        self.files_by_rule[rule][file] += count


def read_answers(project: Path) -> dict[str, str]:
    answers: dict[str, str] = {}
    path = project / ANSWERS_FILE
    if not path.exists():
        return answers
    key = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if match := re.match(r"^([A-Za-z_]\w*):\s*(.*)$", line):
            key, value = match.groups()
            answers[key] = value.strip("'\"")
        elif key and (item := re.match(r"^\s*-\s*(.+)$", line)):
            answers[key] = f"{answers[key]} {item.group(1)}".strip()
    return answers


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # fixed argument lists, no shell
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False
    )


def node_tool(project: Path, *segments: str) -> list[str] | None:
    script = project.joinpath("node_modules", *segments)
    node = shutil.which("node")
    return [node, str(script)] if node and script.exists() else None


def python_tool(project: Path, module: str) -> list[str]:
    if shutil.which("uv"):
        return ["uv", "run", "--quiet", "python", "-m", module]
    return [sys.executable, "-m", module]


def typescript_debt(project: Path, deferred: str) -> Debt:
    debt = Debt()
    suppressions = project / "eslint-suppressions.json"
    if suppressions.exists():
        for file, rules in json.loads(suppressions.read_text(encoding="utf-8")).items():
            for rule, info in rules.items():
                debt.add(rule, file, int(info.get("count", 1)))
    if "typecheck" in deferred:
        tsc = node_tool(project, "typescript", "bin", "tsc")
        if tsc:
            output = run([*tsc, "--noEmit", "--pretty", "false"], project).stdout
            for match in re.finditer(r"^(.+?)\(\d+,\d+\): error TS\d+", output, re.MULTILINE):
                debt.add("typecheck", match.group(1).replace("\\", "/"))
        else:
            debt.notes.append("typecheck is deferred but TypeScript is not installed (run npm install).")
    return debt


MANAGED_DIRS = (".claude/", ".ai-standards/", ".ai-session/")
# `# noqa: CODE  # reason`: a deliberate suppression with a reason (SUP-1), not baselined debt.
JUSTIFIED_NOQA = re.compile(r"#\s*noqa:\s*[A-Z0-9, ]+#\s*\S")


def is_justified(path: Path, item: dict[str, Any]) -> bool:
    try:
        line = path.read_text(encoding="utf-8").splitlines()[item["location"]["row"] - 1]
    except (OSError, IndexError):
        return False
    return bool(JUSTIFIED_NOQA.search(line)) and item["code"] in line


def python_debt(project: Path, deferred: str) -> Debt:
    debt = Debt()
    ruff = python_tool(project, "ruff")
    result = run([*ruff, "check", ".", "--ignore-noqa", "--output-format", "json", "--exit-zero"], project)
    try:
        findings = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        findings = []
        debt.notes.append(f"ruff did not run: {result.stderr.strip()[:200]}")
    for item in findings:
        file = Path(item["filename"]).resolve().relative_to(project.resolve()).as_posix()
        if file.startswith(MANAGED_DIRS) or is_justified(project / file, item):
            continue
        debt.add(item["code"] or "syntax", file)
    if "typecheck" in deferred:
        output = run([*python_tool(project, "mypy")], project).stdout
        for match in re.finditer(r"^(.+?):\d+: error:", output, re.MULTILINE):
            debt.add("typecheck", match.group(1).replace("\\", "/"))
    return debt


def category(rule: str) -> tuple[str, str]:
    for priority, title, patterns in CATEGORIES:
        if any(re.search(pattern, rule) for pattern in patterns):
            return priority, title
    return CATEGORIES[-1][0], CATEGORIES[-1][1]


EMPTY_BASELINE = ".ai-session/no-baseline.json"


def show_command(stack: str, rule: str, file: str) -> str:
    """Command that shows the baselined findings, which normal lint runs hide."""
    if rule == "typecheck":
        return "npm run check:deferred" if stack == "typescript" else "make check-deferred"
    if stack == "typescript":
        return f"npx eslint {file} --suppressions-location {EMPTY_BASELINE}"
    return f"uv run ruff check {file} --ignore-noqa --select {rule}"


def render_backlog(debt: Debt, stack: str) -> list[str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for rule, count in debt.by_rule.most_common():
        priority, _ = category(rule)
        files = debt.files_by_rule[rule]
        top = ", ".join(f"`{file}` ({n})" for file, n in files.most_common(TOP_FILES))
        more = f" and {len(files) - TOP_FILES} more files" if len(files) > TOP_FILES else ""
        first_file = files.most_common(1)[0][0]
        grouped[priority].append(
            f"- [ ] **{rule}**: {count} in {len(files)} file(s): {top}{more}\n"
            f"      see them: `{show_command(stack, rule, first_file)}`"
        )
    lines: list[str] = []
    for priority, title, _ in CATEGORIES:
        if grouped[priority]:
            lines += [f"### {priority}. {title}", "", f"_{HINTS[priority]}_", "", *grouped[priority], ""]
    return lines or ["No baselined lint or type debt. 🎉", ""]


def render_ratchet(answers: dict[str, str], debt: Debt) -> list[str]:
    deferred = answers.get("deferred_checks", "")
    floor = answers.get("coverage_floor", "0")
    items: list[str] = []
    if "typecheck" in deferred:
        left = debt.by_rule["typecheck"]
        state = "ready to enable" if left == 0 else f"{left} error{'s' if left != 1 else ''} left"
        items.append(f"- [ ] **Enable type checking** ({state}): fix the `typecheck` items, then "
                     "remove it from `deferred_checks`.")
    if "coverage" in deferred:
        items.append("- [ ] **Enforce coverage**: add tests for the riskiest untested code, measure, set "
                     "`coverage_floor` to the measured value and remove `coverage` from `deferred_checks`.")
    elif floor not in ("", "0"):
        items.append(f"- [ ] **Raise coverage floor** (now {floor}%): after adding tests, set "
                     "`coverage_floor` to the new measured value, until it reaches the org target.")
    if not items:
        return []
    return [
        "## Ratchet: raise the bar as debt is paid",
        "",
        *items,
        "",
        "Change these answers with `copier update`, never by editing managed files:",
        "",
        "```bash",
        "uvx copier update --trust --defaults --data coverage_floor=<new %> --data 'deferred_checks=[]'",
        "```",
        "",
    ]


def render(project: Path, answers: dict[str, str], debt: Debt) -> str:
    stack = answers.get("stack", "?")
    total = sum(debt.by_rule.values())
    files = len({file for counter in debt.files_by_rule.values() for file in counter})
    header = [
        "# Standards debt",
        "",
        "<!-- Generated by ai-standards (scripts/standards_audit.py). Regenerate instead of editing:",
        "     the fix-debt skill does this after every item. Project-owned, safe to commit. -->",
        "",
        f"Project: `{project.name}` · stack: `{stack}` · org: `{answers.get('org', '?')}` · "
        f"**{total} baselined finding{'s' if total != 1 else ''} in {files} file{'s' if files != 1 else ''}**",
        "",
        "## How to pay this down",
        "",
        "1. Take the **first unchecked item**, highest priority first. One rule (or one area of a big rule) per change.",
        "2. Fix the code. Never add new baseline entries, suppressions or `noqa` to get green.",
        "3. Prune the baseline: "
        + ("`npx eslint . --prune-suppressions`" if stack == "typescript" else "`uv run ruff check . --fix`"),
        "4. Run the full check, commit on its own (`refactor: pay <rule> debt in <area>`), regenerate this file.",
        "5. Never mix debt fixes into feature or bug-fix changes (rule ADOPT-2).",
        "",
        "In Claude Code: `/ai-standards:fix-debt` does exactly this, one item at a time.",
        *(
            [
                "",
                f"Normal lint runs hide baselined findings. The \"see them\" commands need an empty baseline "
                f"first: `mkdir -p .ai-session && echo {{}} > {EMPTY_BASELINE}`",
            ]
            if stack == "typescript"
            else []
        ),
        "",
        "## Backlog",
        "",
    ]
    notes = [f"> Note: {note}" for note in debt.notes]
    return "\n".join([*header, *render_backlog(debt, stack), *render_ratchet(answers, debt), *notes]).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--stdout", action="store_true", help="print instead of writing the file")
    args = parser.parse_args()

    project = args.project.resolve()
    answers = read_answers(project)
    stack = answers.get("stack")
    if stack not in ("typescript", "python"):
        sys.stderr.write(f"{ANSWERS_FILE} with a known stack not found in {project}. Adopt the project first.\n")
        return 1
    deferred = answers.get("deferred_checks", "")
    debt = typescript_debt(project, deferred) if stack == "typescript" else python_debt(project, deferred)
    report = render(project, answers, debt)
    if args.stdout:
        sys.stdout.write(report)
    else:
        output = project / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        print(f"[ai-standards] wrote {args.output}: {sum(debt.by_rule.values())} findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
