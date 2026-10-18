"""Pay standards debt in rounds, with proof a script computes instead of the agent's word.

  fix_debt.py items <out> --org <org> [--max 10] [--baseline <json> --stack typescript|python]
  fix_debt.py start <project> <batch-dir> --item <id> --items <items.json> [--allow <path>]...
                    [--formatter-only]
  fix_debt.py test <project> --command <cmd> --format trx|junit|jest|flutter|summary --out <json>
                   [--timeout <seconds>]
  fix_debt.py canary <project> --file <path> --line <n> --replace <text> --command <cmd>
                     --format <f> --clean <json> --out <json> [--timeout <seconds>]
  fix_debt.py verify <project> --item-dir <dir> --stack <s> --org <o> --render <dir>
                     --before <tool-findings.json> [--solution <sln>]
  fix_debt.py verify-review <project> --item-dir <dir> --review <auditor json>
  fix_debt.py baseline <project> --stack typescript|python --out <json>
  fix_debt.py verify-adopted <project> --item-dir <dir> --stack typescript|python --before <json>
                             --check <cmd>
  fix_debt.py verdict <project> --item-dir <dir>
  fix_debt.py done <out> --item <id>...

Evidence lives in the item's folder (<out>/fix-debt/<batch>/<item>/), never in the project.
In --command, {result} becomes the quoted result file and {dir} its quoted folder, new for each run.
Exit codes: 0 done, 1 STOPPED (verdict), 2 an error, 3 several solutions (verify).
Standard library only; Windows and Linux.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402
import standards_audit  # noqa: E402
from audit import area  # noqa: E402
from rule_data import load_priorities, load_tool_map, priority  # noqa: E402
from run_results import Unreadable, merge  # noqa: E402
from run_results import read as read_result  # noqa: E402

SPLIT_AT = 30
ITEMS, DONE, SKIPPED = "items.json", "done.json", "skipped.json"
TIMEOUT = 3600.0  # seconds a test run may take; after that it counts as a run with no result


def in_area(file: str, where: str) -> bool:
    """Whether a project-relative file belongs to an item's folder; "(root)" is the top level."""
    if where == "(root)":
        return "/" not in file
    return file == where or file.startswith(where.rstrip("/") + "/")


def in_item(file: str, item: dict) -> bool:
    """Whether a file is the item's. The rest of a split folder ("direct") has only the files right in it."""
    if not in_area(file, item["area"]):
        return False
    return not item.get("direct") or item["area"] == "(root)" or "/" not in file[len(item["area"]) + 1:]


def safe_name(item_id: str) -> str:
    """A folder name for an item id: RDB-1@src/billing#P4 → RDB-1@src_billing_P4."""
    return re.sub(r"[^A-Za-z0-9@._-]", "_", item_id)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path, default: object = None) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def load(path: Path) -> object:
    """A JSON file that must be there: a missing or broken one is an error (exit 2)."""
    return json.loads(path.read_text(encoding="utf-8"))


def git(project: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603  # fixed argument list, no shell
        ["git", "-C", str(project), *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=True).stdout


def _head(project: Path) -> str:
    return git(project, "rev-parse", "HEAD").strip()


def _changed(project: Path, older: str, newer: str = "HEAD") -> list[str]:
    return [line for line in git(project, "diff", "--name-only", older, newer).splitlines() if line]


def _is_ancestor(project: Path, older: str, newer: str) -> bool:
    return subprocess.run(["git", "-C", str(project), "merge-base", "--is-ancestor", older, newer],  # noqa: S603
                          capture_output=True, check=False).returncode == 0


def _sub_area(file: str, top: str) -> str:
    parts = file.split("/")
    return "/".join(parts[:2]) if top != "(root)" and len(parts) > 2 else top


def build_items(findings: dict, tool_findings: list[dict], priorities: dict, done: set[str],
                skipped: dict | None = None) -> dict:
    """Debt items, one per rule, priority and folder (split by the next folder past SPLIT_AT).
    A skipped false positive stays out until its count grows past the count it was skipped at."""
    skipped = skipped or {}
    repeated = {rule["rule"] for rule in findings["rules"]
                if sum(r["rule"] == rule["rule"] for r in findings["rules"]) > 1}
    items: list[dict] = []
    for rule in findings["rules"]:
        if rule["kind"] != "violation":
            continue  # inconsistencies are settled in onboarding before they become debt
        mine = [f for f in tool_findings if f["rule"] == rule["rule"]
                and priority(f["rule"], priorities, f["tool_id"]) == rule["priority"]]
        suffix = f"#{rule['priority']}" if rule["rule"] in repeated else ""
        for top, count in rule["areas"].items():
            in_top = [f for f in mine if area(f["file"]) == top]
            groups: dict[str, list[dict]] = {top: in_top}
            split = len(in_top) > SPLIT_AT
            if split:
                groups = {}
                for finding in in_top:
                    groups.setdefault(_sub_area(finding["file"], top), []).append(finding)
            for where, group in groups.items():
                item_id = f"{rule['rule']}@{where}{suffix}"
                count_now = len(group) if group else int(count)
                if item_id in done or count_now <= skipped.get(item_id, {}).get("count", -1):
                    continue
                items.append({
                    "id": item_id, "rule": rule["rule"], "area": where, "priority": rule["priority"],
                    "count": count_now,
                    "kind": "tool" if group else "review",
                    "tool_ids": sorted({str(f["tool_id"]) for f in group}),
                    "files": sorted({str(f["file"]) for f in group}),
                    "behavior": "changes" if rule["priority"] == "P1" else "preserves",
                    "direct": split and where == top,
                })
    items.sort(key=lambda item: (item["priority"], -item["count"], item["id"]))
    return {"items": [i for i in items if i["behavior"] == "preserves"],
            "p1": [i for i in items if i["behavior"] == "changes"]}


def baseline_findings(baseline: dict, tool_map: dict, priorities: dict) -> tuple[dict, list[dict]]:
    """An adopted project's baseline ({tool_id: {file: count}}) as audit findings, to split into items alike."""
    tool = [{"rule": tool_map.get(tool_id, "unmapped"), "tool_id": tool_id, "file": file}
            for tool_id, files in baseline.items() for file, n in files.items() for _ in range(n)]
    areas: dict[tuple[str, str], Counter] = {}
    for finding in tool:
        key = (finding["rule"], priority(finding["rule"], priorities, finding["tool_id"]))
        areas.setdefault(key, Counter())[area(finding["file"])] += 1
    return {"rules": [{"rule": rule, "priority": level, "kind": "violation", "areas": dict(counts)}
                      for (rule, level), counts in areas.items()]}, tool


def cmd_items(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    priorities = load_priorities(args.org)
    if args.baseline:
        if not args.stack:
            sys.stderr.write("--baseline needs --stack\n")
            return 2
        findings, tool = baseline_findings(load(args.baseline.resolve()), load_tool_map(args.stack, args.org),
                                           priorities)
    else:
        findings = read_json(out / "findings.json")
        if findings is None:
            sys.stderr.write(f"no findings.json in {out}: run /ai-standards:audit first\n")
            return 2
        tool = read_json(out / "tool-findings.json", {"findings": []})["findings"]
    done = set(read_json(out / "fix-debt" / DONE, []))
    result = build_items(findings, tool, priorities, done, read_json(out / "fix-debt" / SKIPPED, {}))
    write_json(out / "fix-debt" / ITEMS, result)
    for item in result["items"][: args.max]:
        print(f"{item['id']}  {item['priority']}  {item['count']}  {item['kind']}")
    for item in result["p1"]:
        print(f"{item['id']}  P1 (changes behavior)  {item['count']}  {item['kind']}")
    return 0


RESULT_SUFFIX = {"trx": ".trx", "junit": ".xml", "jest": ".jest.json", "flutter": ".jsonl", "summary": ".log"}


def start_item(project: Path, batch: Path, item_id: str, items_file: Path, allow: list[str],
               formatter_only: bool) -> Path:
    data = read_json(items_file, {"items": [], "p1": []})
    item = next((i for i in data["items"] + data["p1"] if i["id"] == item_id), None)
    if item is None:
        sys.stderr.write(f"no item {item_id} in {items_file}\n")
        raise SystemExit(2)
    if batch.resolve().is_relative_to(project.resolve()):
        sys.stderr.write(f"{batch} is inside the project: evidence goes in <out>/fix-debt/<batch>\n")
        raise SystemExit(2)
    if git(project, "status", "--porcelain").strip():
        sys.stderr.write("the working tree has uncommitted changes: commit or stash them first\n")
        raise SystemExit(2)
    folder = batch / safe_name(item_id)
    write_json(folder / "item.json", {**item, "start": _head(project), "allow": allow,
                                      "formatter_only": formatter_only, "p1": item["behavior"] == "changes"})
    return folder


def _shell(command: str, cwd: Path, timeout: float | None) -> tuple[int | None, str]:
    """Run a shell command with its output in a file (a child left running can't hold a pipe open).
    On timeout, kill its whole process tree; the exit code is then None."""
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(command, shell=True, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,  # noqa: S602
                                start_new_session=os.name != "nt")
        try:
            code: int | None = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],  # noqa: S603, S607
                               capture_output=True, check=False)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            code = None
        log.seek(0)
        return code, log.read().decode("utf-8", "replace")


def run_tests(project: Path, command: str, kind: str, out: Path, timeout: float | None = None) -> dict:
    """Run the test command into a new folder; the result comes only from what the runner writes
    there this time (for dotnet, every .trx in it: one per test project). Records the commit and
    whether anything was uncommitted, so a verdict can tell which code ran."""
    results = out.with_name(out.stem + "-results")
    shutil.rmtree(results, ignore_errors=True)
    results.mkdir(parents=True)
    result_file = results / (out.stem + RESULT_SUFFIX[kind])
    expanded = command.replace("{result}", f'"{result_file}"').replace("{dir}", f'"{results}"')
    head, dirty = _head(project), bool(git(project, "status", "--porcelain").strip())
    code, output = _shell(expanded, project, timeout)
    out.with_name(out.stem + ".output.log").write_text(output, encoding="utf-8")
    if kind == "summary":
        result_file.write_text(output, encoding="utf-8")
    try:
        if code is None:
            raise Unreadable(f"timed out after {timeout:g} s")
        if kind == "trx":
            files = sorted(results.glob("*.trx"))
            if not files:
                raise Unreadable(f"no .trx file in {results}")
            result = merge([read_result(file, kind) for file in files])
        else:
            result = read_result(result_file, kind)
        error = ""
    except Unreadable as problem:
        result = {"executed": 0, "passed": 0, "failed": 0, "skipped": 0, "tests": {}, "source": "missing"}
        error = str(problem)
    result.update(command=expanded, exit_code=code, head=head, dirty=dirty, result_file=str(result_file),
                  error=error)
    write_json(out, result)
    return result


def cmd_start(args: argparse.Namespace) -> int:
    print(start_item(args.project.resolve(), args.batch.resolve(), args.item, args.items.resolve(),
                     args.allow, args.formatter_only))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    result = run_tests(args.project.resolve(), args.command, args.format, args.out.resolve(), args.timeout)
    print(f"[fix-debt] tests: {result['executed']} executed, {result['failed']} failed, "
          f"{result['skipped']} skipped ({result['source']}){' — ' + result['error'] if result['error'] else ''}")
    return 0


def canary(project: Path, file: str, line: int, replace: str, command: str, kind: str, clean: Path,
           out: Path, timeout: float | None = None) -> dict:
    """Break one line on purpose, run the tests, restore the file. Tests that passed in the clean run
    and fail now mean the tests see that line; tests that vanish mean the break hid them (it may not
    compile), which proves nothing."""
    if git(project, "status", "--porcelain", "--", file).strip():
        sys.stderr.write(f"{file} has uncommitted changes: the canary needs a clean file\n")
        raise SystemExit(2)
    before = load(clean)
    target = project / file
    original = target.read_bytes()
    lines = original.decode("utf-8").splitlines(keepends=True)
    if not 1 <= line <= len(lines):
        sys.stderr.write(f"{file} has no line {line}\n")
        raise SystemExit(2)
    old = lines[line - 1]
    ending = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
    lines[line - 1] = replace + ending

    def stop(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)  # unwinds through the finally below, which restores the file

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        target.write_bytes("".join(lines).encode("utf-8"))
        result = run_tests(project, command, kind, out.with_name(out.stem + "-run.json"), timeout)
    finally:
        target.write_bytes(original)
        signal.signal(signal.SIGTERM, previous)
    restored = not git(project, "status", "--porcelain", "--", file).strip()
    if result["source"] == before["source"] == "file":
        new = sorted(t for t, outcome in before["tests"].items()
                     if outcome == "passed" and result["tests"].get(t) == "failed")
        vanished = sorted(t for t in before["tests"] if t not in result["tests"])
        delta = len(new)
    else:
        new, delta = [], result["failed"] - before["failed"]
        hidden = before["executed"] - result["executed"]
        vanished = [f"{hidden} tests by count"] if hidden > 0 else []
    data = {"file": file, "line": line, "replace": replace, "new_failures": new, "failed_delta": delta,
            "vanished": vanished, "restored": restored, "source": result["source"], "executed": result["executed"]}
    write_json(out, data)
    return data


def cmd_canary(args: argparse.Namespace) -> int:
    data = canary(args.project.resolve(), args.file, args.line, args.replace, args.command, args.format,
                  args.clean.resolve(), args.out.resolve(), args.timeout)
    print(f"[fix-debt] canary: {data['failed_delta']} new failures, {len(data['vanished'])} vanished; "
          f"restored: {data['restored']}")
    return 0


def _new_in_touched(before: Counter, after: Counter) -> list[dict]:
    return [{"file": file, "tool_id": tool_id, "count": n - before[(file, tool_id)]}
            for (file, tool_id), n in sorted(after.items()) if n > before[(file, tool_id)]]


def compare_findings(item: dict, before: list[dict], after: list[dict], touched: list[str]) -> dict:
    """The item's findings left after the fix (by tool id when it has them), and findings the fix
    added to the files it touched."""
    def mine(finding: dict) -> bool:
        if not in_item(str(finding["file"]), item):
            return False
        return str(finding["tool_id"]) in item["tool_ids"] if item.get("tool_ids") else finding["rule"] == item["rule"]
    remaining = [f for f in after if mine(f)]
    counts_before = Counter((f["file"], f["tool_id"]) for f in before if f["file"] in touched)
    counts_after = Counter((f["file"], f["tool_id"]) for f in after if f["file"] in touched)
    return {"remaining": len(remaining), "remaining_examples": remaining[:5],
            "new": _new_in_touched(counts_before, counts_after)}


def compare_baseline(item: dict, before: dict, after: dict, touched: list[str]) -> dict:
    """The same comparison on an adopted project's baseline ({tool_id: {file: count}})."""
    remaining = sum(n for tool_id in item.get("tool_ids") or [item["rule"]]
                    for file, n in after.get(tool_id, {}).items() if in_item(file, item))
    def counts(baseline: dict) -> Counter:
        return Counter({(file, tool_id): n for tool_id, files in baseline.items()
                        for file, n in files.items() if file in touched})
    return {"remaining": remaining, "remaining_examples": [], "new": _new_in_touched(counts(before), counts(after))}


def cmd_verify(args: argparse.Namespace) -> int:
    project, folder = args.project.resolve(), args.item_dir.resolve()
    item = load(folder / "item.json")
    touched = _changed(project, item["start"])
    with tempfile.TemporaryDirectory() as tmp:
        argv = ["tools", str(project), "--stack", args.stack, "--org", args.org, "--render", str(args.render),
                "--out", tmp, *(["--solution", args.solution] if args.solution else [])]
        code = audit.main(argv)
        doc = read_json(Path(tmp) / audit.TOOL_FINDINGS, {"status": f"audit exit {code}", "findings": []})
    status = ("several solutions: run verify again with --solution and one printed above" if code == 3
              else doc["status"])
    data = {"status": status, "touched": touched, "head": _head(project), "evidence": "analyzer",
            "remaining": None, "remaining_examples": [], "new": []}
    if code == 0 and str(doc["status"]).startswith("ran"):
        before = load(args.before.resolve())["findings"]
        data.update(compare_findings(item, before, doc["findings"], touched))
    write_json(folder / "verify.json", data)
    print(f"[fix-debt] verify: {data['status']}; remaining {data['remaining']}; new {len(data['new'])}")
    return 3 if code == 3 else 0


def cmd_verify_review(args: argparse.Namespace) -> int:
    project, folder = args.project.resolve(), args.item_dir.resolve()
    item = load(folder / "item.json")
    review = load(args.review.resolve())
    remaining = sum(int(r.get("count", 0)) for r in review["rules"] if r.get("rule") == item["rule"])
    write_json(folder / "verify.json", {"status": "review", "touched": [], "head": _head(project),
                                        "evidence": "rule auditor", "remaining": remaining,
                                        "remaining_examples": [], "new": []})
    return 0


def adopted_baseline(project: Path, stack: str) -> dict:
    deferred = standards_audit.read_answers(project).get("deferred_checks", "")
    debt = (standards_audit.typescript_debt(project, deferred) if stack == "typescript"
            else standards_audit.python_debt(project, deferred))
    return {rule: dict(files) for rule, files in debt.files_by_rule.items()}


def cmd_baseline(args: argparse.Namespace) -> int:
    write_json(args.out.resolve(), adopted_baseline(args.project.resolve(), args.stack))
    return 0


def cmd_verify_adopted(args: argparse.Namespace) -> int:
    project, folder = args.project.resolve(), args.item_dir.resolve()
    item = load(folder / "item.json")
    touched = _changed(project, item["start"])
    check = subprocess.run(args.check, shell=True, cwd=project, capture_output=True, text=True,  # noqa: S602
                           encoding="utf-8", errors="replace", check=False)
    data = {"status": "check passed" if check.returncode == 0 else "check failed", "touched": touched,
            "head": _head(project), "evidence": "baseline",
            **compare_baseline(item, load(args.before.resolve()), adopted_baseline(project, args.stack), touched)}
    write_json(folder / "verify.json", data)
    return 0


# Markers that silence a finding instead of fixing it (ADOPT-3), on lines a fix adds.
SUPPRESSION = re.compile(
    r"eslint-disable|eslint\s+[^*\n]*?:\s*[\"']?(?:off|0)\b|@ts-(?:ignore|expect-error|nocheck)|#\s*noqa"
    r"|ruff\s*:\s*noqa|#\s*type:\s*ignore|mypy\s*:\s*ignore-errors|#\s*pragma\s+warning\s+disable"
    r"|SuppressMessage|<NoWarn>|//\s*ignore(?:_for_file)?:|severity\s*=\s*(?:none|silent)", re.IGNORECASE)
# Analyzer and lint settings: a fix changes them only with the user's approval (--allow <file>).
LINT_CONFIG = re.compile(
    r"(?:^|/)(?:\.?ruff\.toml|pyproject\.toml|setup\.cfg|mypy\.ini|\.editorconfig|\.globalconfig"
    r"|GlobalSuppressions\.cs|analysis_options\.yaml|eslint\.config\.[cm]?[jt]s|\.eslintrc[^/]*"
    r"|Directory\.Build\.[^/]+|[^/]+\.csproj|tsconfig[^/]*\.json)$")
# Pinned tests may sit outside the item's folder, but only test files do.
TEST_PATH = re.compile(r"(?:^|/)(?:[Tt]ests?|__tests__|spec)/|\.Tests?/|(?:^|/)test_[^/]*\.py$|_test\.(?:py|dart)$"
                       r"|\.(?:test|spec)\.[jt]sx?$|Tests?\.cs$")
BASELINES = ("eslint-suppressions.json",)


def _baseline_total(project: Path, ref: str, path: str) -> int:
    proc = subprocess.run(["git", "-C", str(project), "show", f"{ref}:{path}"],  # noqa: S603
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        return 0
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return 0
    return sum(int(info.get("count", 1)) for rules in data.values() for info in rules.values())


def _lost(base: dict, after: dict) -> list[str]:
    """Tests that passed in base and don't pass after: by id when both runs have ids, else by count."""
    if base["source"] == after["source"] == "file":
        return sorted(t for t, outcome in base["tests"].items() if outcome == "passed" and after["tests"].get(t) != "passed")
    lost, skipped = base["passed"] - after["passed"], after["skipped"] - base["skipped"]
    return ([f"{lost} by count"] if lost > 0 else []) + ([f"{skipped} more skipped"] if skipped > 0 else [])


def compute_verdict(project: Path, folder: Path) -> dict:
    item = load(folder / "item.json")
    clean, after = read_json(folder / "clean.json"), read_json(folder / "after.json")
    canary_run, verify = read_json(folder / "canary.json"), read_json(folder / "verify.json")
    pinned, red = read_json(folder / "pinned.json"), read_json(folder / "red.json")
    head = _head(project)
    uncommitted = [line[3:] for line in git(project, "status", "--porcelain").splitlines() if line]
    # Pinned tests count only from a pin commit between the start and HEAD; the fix is what follows it.
    pin_ok = (bool(pinned) and pinned.get("head") not in (None, item["start"])
              and _is_ancestor(project, item["start"], pinned["head"]) and _is_ancestor(project, pinned["head"], head))
    pin_files = _changed(project, item["start"], pinned["head"]) if pin_ok else []
    fix_files = _changed(project, pinned["head"] if pin_ok else item["start"])
    checks: dict[str, dict] = {}

    def check(name: str, ok: bool | None, reason: str) -> None:
        checks[name] = {"ok": ok, "reason": reason}

    if clean is None or clean["source"] == "missing":
        check("clean run", False, "no readable result from the clean run"
              + (f": {clean['error']}" if clean and clean.get("error") else ""))
    elif clean["executed"] == 0:
        check("clean run", False, "no test executed in the clean run")
    elif clean.get("head") != item["start"] or clean.get("dirty"):
        check("clean run", False, "the clean run wasn't on the item's start commit with nothing uncommitted")
    elif clean["failed"]:
        check("clean run", False, f"{clean['failed']} tests already failing on the start commit")
    else:
        check("clean run", True, f"{clean['executed']} executed, all passing")

    if after is None or after["source"] == "missing":
        check("tests ran", False, "no readable result from the after run"
              + (f": {after['error']}" if after and after.get("error") else ""))
    elif after["executed"] == 0:
        check("tests ran", False, "no test executed in the after run")
    elif after.get("head") != head or after.get("dirty"):
        check("tests ran", False, "the after run wasn't on HEAD with everything committed")
    elif uncommitted:
        check("tests ran", False, f"uncommitted changes now: {', '.join(uncommitted[:5])}")
    else:
        check("tests ran", True, f"{after['executed']} executed, {after['failed']} failed")

    if clean is None or after is None or "missing" in (clean["source"], after["source"]):
        check("nothing lost", False, "needs results from the clean and the after runs")
    else:
        lost = _lost(clean, after)
        lost += [t for t in (_lost(pinned, after) if pinned else []) if t not in lost]
        if red and red["source"] == after["source"] == "file":
            lost += [t for t, outcome in sorted(red["tests"].items())
                     if outcome == "failed" and after["tests"].get(t) != "passed" and t not in lost]
        failing = [t for t, outcome in sorted(after["tests"].items()) if outcome == "failed" and t not in lost]
        if after["failed"] and not failing and not lost:
            failing = [f"{after['failed']} by count"]
        problems = ([f"no longer passing: {', '.join(lost)}"] if lost else []) + \
                   ([f"failing after the fix: {', '.join(failing)}"] if failing else [])
        check("nothing lost", not problems, "; ".join(problems) or "every test that passed still passes; none fails")

    if item["formatter_only"]:
        check("canary", None, "formatter only: no canary")
    elif canary_run is None:
        check("canary", False, "no canary was run")
    elif not canary_run["restored"]:
        check("canary", False, f"{canary_run['file']} wasn't restored after the canary")
    elif canary_run.get("vanished"):
        check("canary", False, "the break hid tests instead of failing them (does it compile?): "
              + ", ".join(canary_run["vanished"][:5]))
    elif canary_run["file"] not in fix_files:
        check("canary", False, f"the break was in {canary_run['file']}, which the fix doesn't change")
    else:
        saw = canary_run["failed_delta"] > 0
        check("canary", saw, f"{canary_run['failed_delta']} new failures from the break in "
              f"{canary_run['file']}:{canary_run.get('line')}" if saw else "the break caused no new failure")

    if pinned is None:
        check("pinned tests", None, "no pinned tests")
    elif not pin_files:
        check("pinned tests", False, "the pinned run isn't on a commit of pinned tests between the start and HEAD")
    elif pinned.get("dirty") or pinned["executed"] == 0 or pinned["failed"]:
        check("pinned tests", False, "the pinned tests didn't pass on the unfixed code")
    else:
        changed_later = sorted(set(pin_files) & set(fix_files))
        check("pinned tests", not changed_later, f"pinned tests changed after pinning: {', '.join(changed_later)}"
              if changed_later else "pinned tests passed on the unfixed code and stayed unchanged")

    if not item["p1"]:
        check("red first", None, "not a P1 item")
    else:
        ok = bool(red) and red["failed"] > 0
        check("red first", ok, f"{red['failed']} failing before the fix" if ok else "no test was seen failing before the fix")

    if verify is None or verify.get("remaining") is None:
        check("item gone", False, f"not verified: {verify['status'] if verify else 'no verify run'}")
    elif verify.get("head") != head:
        check("item gone", False, "verified on another commit than HEAD")
    elif verify["status"] == "check failed":
        check("item gone", False, "the project's check failed")
    else:
        ok = verify["remaining"] == 0 and not verify["new"]
        check("item gone", ok, f"{verify['remaining']} left, {len(verify['new'])} new in touched files ({verify['evidence']})")

    changed = _changed(project, item["start"])
    allow = item.get("allow", [])
    outside = [f for f in changed if not (in_item(f, item) or any(in_area(f, a) for a in allow)
                                          or (f in pin_files and TEST_PATH.search(f)))]
    settings = [f for f in changed if LINT_CONFIG.search(f) and f not in allow]
    added = [line[1:] for line in git(project, "diff", "-U0", f"{item['start']}..HEAD").splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    marks = [line.strip() for line in added if SUPPRESSION.search(line)]
    grown = [b for b in BASELINES if _baseline_total(project, "HEAD", b) > _baseline_total(project, item["start"], b)]
    problems = ([f"outside the item: {', '.join(outside)}"] if outside else []) + \
               ([f"analyzer settings changed: {', '.join(settings)}"] if settings else []) + \
               ([f"suppression added: {marks[0]}"] if marks else []) + ([f"baseline grew: {', '.join(grown)}"] if grown else [])
    check("scope", not problems, "; ".join(problems) or f"{len(changed)} files, all inside the item")

    failing_checks = [f"{name}: {c['reason']}" for name, c in checks.items() if c["ok"] is False]
    does_not_prove = ["the canary shows the tests see one spot, not every changed line"]
    if item.get("kind") == "review":
        does_not_prove.append("the item's absence rests on an AI rule auditor")
    if any(run and run.get("source") == "summary" for run in (clean, after)):
        does_not_prove.append("summary-line evidence has no per-test ids")
    return {"item": item["id"], "verdict": "STOPPED" if failing_checks else "DONE", "checks": checks,
            "reasons": failing_checks, "does_not_prove": does_not_prove}


def render_verdict(verdict: dict) -> str:
    rows = [f"| {name} | {'pass' if c['ok'] else 'n/a' if c['ok'] is None else 'FAIL'} | {c['reason']} |"
            for name, c in verdict["checks"].items()]
    return "\n".join([f"## {verdict['item']} — {verdict['verdict']}", "", "| Check | Result | Why |",
                      "|---|---|---|", *rows, "", "Does not prove:",
                      *[f"- {line}" for line in verdict["does_not_prove"]]]) + "\n"


def cmd_verdict(args: argparse.Namespace) -> int:
    folder = args.item_dir.resolve()
    verdict = compute_verdict(args.project.resolve(), folder)
    write_json(folder / "verdict.json", verdict)
    (folder / "verdict.md").write_text(render_verdict(verdict), encoding="utf-8")
    print(render_verdict(verdict))
    return 0 if verdict["verdict"] == "DONE" else 1


def cmd_done(args: argparse.Namespace) -> int:
    """Record the round's DONE items once its pull request is open, so the next round skips them."""
    path = args.out.resolve() / "fix-debt" / DONE
    write_json(path, sorted({*read_json(path, []), *args.item}))
    return 0


def cmd_skip(args: argparse.Namespace) -> int:
    """Record a false positive with its reason, so later rounds leave it out until it grows."""
    folder = args.out.resolve() / "fix-debt"
    listed = read_json(folder / ITEMS, {"items": [], "p1": []})
    item = next((i for i in listed["items"] + listed["p1"] if i["id"] == args.item), None)
    if item is None:
        sys.stderr.write(f"{args.item} isn't in {folder / ITEMS}: run fix_debt.py items first\n")
        return 2
    skipped = read_json(folder / SKIPPED, {})
    skipped[args.item] = {"reason": args.reason, "count": item["count"]}
    write_json(folder / SKIPPED, skipped)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    # "action", not "command": the test and canary commands have a --command option of their own.
    commands = parser.add_subparsers(dest="action", required=True)
    items = commands.add_parser("items", help="debt items for the next round")
    items.add_argument("out", type=Path)
    items.add_argument("--org", required=True)
    items.add_argument("--max", type=int, default=10)
    items.add_argument("--baseline", type=Path, help="an adopted project's baseline (fix_debt.py baseline)")
    items.add_argument("--stack", choices=("typescript", "python"))
    start = commands.add_parser("start", help="record an item's start commit and allowed paths")
    start.add_argument("project", type=Path)
    start.add_argument("batch", type=Path)
    start.add_argument("--item", required=True)
    start.add_argument("--items", required=True, type=Path)
    start.add_argument("--allow", action="append", default=[])
    start.add_argument("--formatter-only", action="store_true")
    test = commands.add_parser("test", help="run the tests and keep their result file")
    test.add_argument("project", type=Path)
    test.add_argument("--command", required=True)
    test.add_argument("--format", required=True, choices=sorted(RESULT_SUFFIX))
    test.add_argument("--out", required=True, type=Path)
    test.add_argument("--timeout", type=float, default=TIMEOUT)
    can = commands.add_parser("canary", help="break one line, run the tests, restore it")
    can.add_argument("project", type=Path)
    can.add_argument("--file", required=True)
    can.add_argument("--line", required=True, type=int)
    can.add_argument("--replace", required=True)
    can.add_argument("--command", required=True)
    can.add_argument("--format", required=True, choices=sorted(RESULT_SUFFIX))
    can.add_argument("--clean", required=True, type=Path)
    can.add_argument("--out", required=True, type=Path)
    can.add_argument("--timeout", type=float, default=TIMEOUT)
    ver = commands.add_parser("verify", help="re-run the analyzers on HEAD: the item must be gone")
    ver.add_argument("project", type=Path)
    ver.add_argument("--item-dir", required=True, type=Path)
    ver.add_argument("--stack", required=True)
    ver.add_argument("--org", required=True)
    ver.add_argument("--render", required=True, type=Path)
    ver.add_argument("--before", required=True, type=Path)
    ver.add_argument("--solution")
    rev = commands.add_parser("verify-review", help="record a rule auditor's recount of a review item")
    rev.add_argument("project", type=Path)
    rev.add_argument("--item-dir", required=True, type=Path)
    rev.add_argument("--review", required=True, type=Path)
    base = commands.add_parser("baseline", help="an adopted project's baselined findings per tool id and file")
    base.add_argument("project", type=Path)
    base.add_argument("--stack", required=True, choices=("typescript", "python"))
    base.add_argument("--out", required=True, type=Path)
    vad = commands.add_parser("verify-adopted", help="the check passes and the item left the baseline")
    vad.add_argument("project", type=Path)
    vad.add_argument("--item-dir", required=True, type=Path)
    vad.add_argument("--stack", required=True, choices=("typescript", "python"))
    vad.add_argument("--before", required=True, type=Path)
    vad.add_argument("--check", required=True)
    ver_d = commands.add_parser("verdict", help="compute the item's verdict from its evidence")
    ver_d.add_argument("project", type=Path)
    ver_d.add_argument("--item-dir", required=True, type=Path)
    done = commands.add_parser("done", help="record the round's DONE items")
    done.add_argument("out", type=Path)
    done.add_argument("--item", required=True, action="append")
    skip = commands.add_parser("skip", help="record a false positive, with its reason")
    skip.add_argument("out", type=Path)
    skip.add_argument("--item", required=True)
    skip.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    handlers = {"items": cmd_items, "start": cmd_start, "test": cmd_test, "canary": cmd_canary,
                "verify": cmd_verify, "verify-review": cmd_verify_review, "baseline": cmd_baseline,
                "verify-adopted": cmd_verify_adopted, "verdict": cmd_verdict, "done": cmd_done,
                "skip": cmd_skip}
    try:
        return handlers[args.action](args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        # Exit 1 is STOPPED, after which the skill resets the item's commits: an error is 2, never 1.
        sys.stderr.write(f"fix_debt.py {args.action}: {type(error).__name__}: {error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
