"""Pay standards debt in rounds, with proof a script computes instead of the agent's word.

  fix_debt.py items <out> --org <org> [--max 10]
  fix_debt.py start <project> <batch-dir> --item <id> --items <items.json> [--allow <path>]...
                    [--formatter-only]
  fix_debt.py test <project> --command <cmd> --format trx|junit|jest|flutter|summary --out <json>
  fix_debt.py canary <project> --file <path> --line <n> --replace <text> --command <cmd>
                     --format <f> --clean <json> --out <json>
  fix_debt.py verify <project> --item-dir <dir> --stack <s> --org <o> --render <dir>
                     --before <tool-findings.json> [--solution <sln>]
  fix_debt.py verify-review --item-dir <dir> --review <auditor json>
  fix_debt.py baseline <project> --stack typescript|python --out <json>
  fix_debt.py verify-adopted <project> --item-dir <dir> --stack typescript|python --before <json>
                             --check <cmd>
  fix_debt.py verdict <project> --item-dir <dir>

Evidence lives in the item's folder (<out>/fix-debt/<batch>/<item>/), never in the project.
In --command, {result} and {dir} become quoted paths and {name} the result file's bare name.
Standard library only; Windows and Linux.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402
import standards_audit  # noqa: E402
from audit import area  # noqa: E402
from rule_data import load_priorities, priority  # noqa: E402
from run_results import Unreadable  # noqa: E402
from run_results import read as read_result  # noqa: E402

SPLIT_AT = 30
ITEMS, DONE = "items.json", "done.json"


def in_area(file: str, where: str) -> bool:
    """Whether a project-relative file belongs to an item's folder; "(root)" is the top level."""
    if where == "(root)":
        return "/" not in file
    return file == where or file.startswith(where.rstrip("/") + "/")


def safe_name(item_id: str) -> str:
    """A folder name for an item id: RDB-1@src/billing#P4 → RDB-1@src_billing_P4."""
    return re.sub(r"[^A-Za-z0-9@._-]", "_", item_id)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path, default: object = None) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def git(project: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603  # fixed argument list, no shell
        ["git", "-C", str(project), *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=True).stdout


def _sub_area(file: str, top: str) -> str:
    parts = file.split("/")
    return "/".join(parts[:2]) if top != "(root)" and len(parts) > 2 else top


def build_items(findings: dict, tool_findings: list[dict], priorities: dict, done: set[str]) -> dict:
    """Debt items, one per rule, priority and folder (split by the next folder past SPLIT_AT)."""
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
            if len(in_top) > SPLIT_AT:
                groups = {}
                for finding in in_top:
                    groups.setdefault(_sub_area(finding["file"], top), []).append(finding)
            for where, group in groups.items():
                item_id = f"{rule['rule']}@{where}{suffix}"
                if item_id in done:
                    continue
                items.append({
                    "id": item_id, "rule": rule["rule"], "area": where, "priority": rule["priority"],
                    "count": len(group) if group else int(count),
                    "kind": "tool" if group else "review",
                    "tool_ids": sorted({str(f["tool_id"]) for f in group}),
                    "files": sorted({str(f["file"]) for f in group}),
                    "behavior": "changes" if rule["priority"] == "P1" else "preserves",
                })
    items.sort(key=lambda item: (item["priority"], -item["count"], item["id"]))
    return {"items": [i for i in items if i["behavior"] == "preserves"],
            "p1": [i for i in items if i["behavior"] == "changes"]}


def cmd_items(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    findings = read_json(out / "findings.json")
    tool = read_json(out / "tool-findings.json", {"findings": []})
    if findings is None:
        sys.stderr.write(f"no findings.json in {out}: run /ai-standards:audit first\n")
        return 2
    done = set(read_json(out / "fix-debt" / DONE, []))
    result = build_items(findings, tool["findings"], load_priorities(args.org), done)
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
    if git(project, "status", "--porcelain").strip():
        sys.stderr.write("the working tree has uncommitted changes: commit or stash them first\n")
        raise SystemExit(2)
    folder = batch / safe_name(item_id)
    write_json(folder / "item.json", {**item, "start": git(project, "rev-parse", "HEAD").strip(),
                                      "allow": [item["area"], *allow], "formatter_only": formatter_only,
                                      "p1": item["behavior"] == "changes"})
    return folder


def run_tests(project: Path, command: str, kind: str, out: Path) -> dict:
    """Run the test command; the result comes only from the file the runner writes this time."""
    out.parent.mkdir(parents=True, exist_ok=True)
    result_file = out.with_name(out.stem + RESULT_SUFFIX[kind])
    result_file.unlink(missing_ok=True)  # a file from an earlier run never counts
    expanded = (command.replace("{result}", f'"{result_file}"').replace("{dir}", f'"{result_file.parent}"')
                .replace("{name}", result_file.name))
    proc = subprocess.run(expanded, shell=True, cwd=project, capture_output=True, text=True,  # noqa: S602
                          encoding="utf-8", errors="replace", check=False)
    output = proc.stdout + "\n" + proc.stderr
    out.with_name(out.stem + ".output.log").write_text(output, encoding="utf-8")
    if kind == "summary":
        result_file.write_text(output, encoding="utf-8")
    try:
        result = read_result(result_file, kind)
        error = ""
    except Unreadable as problem:
        result = {"executed": 0, "passed": 0, "failed": 0, "skipped": 0, "tests": {}, "source": "missing"}
        error = str(problem)
    result.update(command=expanded, exit_code=proc.returncode, finished_at=time.time(),
                  result_file=str(result_file), error=error)
    write_json(out, result)
    return result


def cmd_start(args: argparse.Namespace) -> int:
    print(start_item(args.project.resolve(), args.batch.resolve(), args.item, args.items.resolve(),
                     args.allow, args.formatter_only))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    result = run_tests(args.project.resolve(), args.command, args.format, args.out.resolve())
    print(f"[fix-debt] tests: {result['executed']} executed, {result['failed']} failed, "
          f"{result['skipped']} skipped ({result['source']}){' — ' + result['error'] if result['error'] else ''}")
    return 0


def canary(project: Path, file: str, line: int, replace: str, command: str, kind: str, clean: Path,
           out: Path) -> dict:
    """Break one line on purpose, run the tests, restore the file: new failures mean the tests see it."""
    if git(project, "status", "--porcelain", "--", file).strip():
        sys.stderr.write(f"{file} has uncommitted changes: the canary needs a clean file\n")
        raise SystemExit(2)
    target = project / file
    original = target.read_bytes()
    lines = original.decode("utf-8").splitlines(keepends=True)
    if not 1 <= line <= len(lines):
        sys.stderr.write(f"{file} has no line {line}\n")
        raise SystemExit(2)
    old = lines[line - 1]
    ending = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
    lines[line - 1] = replace + ending
    target.write_bytes("".join(lines).encode("utf-8"))
    try:
        result = run_tests(project, command, kind, out.with_name(out.stem + "-run.json"))
    finally:
        target.write_bytes(original)
    restored = not git(project, "status", "--porcelain", "--", file).strip()
    before = read_json(clean, {"tests": {}, "failed": 0, "source": "missing"})
    if result["source"] == "file" and before["source"] == "file":
        known = {test for test, outcome in before["tests"].items() if outcome == "failed"}
        new = sorted(t for t, outcome in result["tests"].items() if outcome == "failed" and t not in known)
        delta = len(new)
    else:
        new, delta = [], result["failed"] - before["failed"]
    data = {"file": file, "line": line, "replace": replace, "new_failures": new, "failed_delta": delta,
            "restored": restored, "source": result["source"], "executed": result["executed"]}
    write_json(out, data)
    return data


def cmd_canary(args: argparse.Namespace) -> int:
    data = canary(args.project.resolve(), args.file, args.line, args.replace, args.command, args.format,
                  args.clean.resolve(), args.out.resolve())
    print(f"[fix-debt] canary: {data['failed_delta']} new failures; restored: {data['restored']}")
    return 0


def _new_in_touched(before: Counter, after: Counter) -> list[dict]:
    return [{"file": file, "tool_id": tool_id, "count": n - before[(file, tool_id)]}
            for (file, tool_id), n in sorted(after.items()) if n > before[(file, tool_id)]]


def compare_findings(item: dict, before: list[dict], after: list[dict], touched: list[str]) -> dict:
    """The item's findings left after the fix, and findings the fix added to the files it touched."""
    def mine(finding: dict) -> bool:
        return (finding["rule"] == item["rule"] and in_area(str(finding["file"]), item["area"])
                and (not item.get("tool_ids") or str(finding["tool_id"]) in item["tool_ids"]))
    remaining = [f for f in after if mine(f)]
    counts_before = Counter((f["file"], f["tool_id"]) for f in before if f["file"] in touched)
    counts_after = Counter((f["file"], f["tool_id"]) for f in after if f["file"] in touched)
    return {"remaining": len(remaining), "remaining_examples": remaining[:5],
            "new": _new_in_touched(counts_before, counts_after)}


def compare_baseline(item: dict, before: dict, after: dict, touched: list[str]) -> dict:
    """The same comparison on an adopted project's baseline ({tool_id: {file: count}})."""
    remaining = sum(n for file, n in after.get(item["rule"], {}).items() if in_area(file, item["area"]))
    def counts(baseline: dict) -> Counter:
        return Counter({(file, tool_id): n for tool_id, files in baseline.items()
                        for file, n in files.items() if file in touched})
    return {"remaining": remaining, "remaining_examples": [], "new": _new_in_touched(counts(before), counts(after))}


def _touched(project: Path, start: str) -> list[str]:
    return [line for line in git(project, "diff", "--name-only", f"{start}..HEAD").splitlines() if line]


def cmd_verify(args: argparse.Namespace) -> int:
    project, folder = args.project.resolve(), args.item_dir.resolve()
    item = read_json(folder / "item.json")
    touched = _touched(project, item["start"])
    with tempfile.TemporaryDirectory() as tmp:
        argv = ["tools", str(project), "--stack", args.stack, "--org", args.org, "--render", str(args.render),
                "--out", tmp, *(["--solution", args.solution] if args.solution else [])]
        code = audit.main(argv)
        doc = read_json(Path(tmp) / audit.TOOL_FINDINGS, {"status": f"audit exit {code}", "findings": []})
    data = {"status": doc["status"], "touched": touched, "evidence": "analyzer",
            "remaining": None, "remaining_examples": [], "new": []}
    if code == 0 and str(doc["status"]).startswith("ran"):
        before = read_json(args.before.resolve(), {"findings": []})["findings"]
        data.update(compare_findings(item, before, doc["findings"], touched))
    write_json(folder / "verify.json", data)
    print(f"[fix-debt] verify: {data['status']}; remaining {data['remaining']}; new {len(data['new'])}")
    return 0


def cmd_verify_review(args: argparse.Namespace) -> int:
    folder = args.item_dir.resolve()
    item = read_json(folder / "item.json")
    review = read_json(args.review.resolve(), {"rules": []})
    remaining = sum(int(r.get("count", 0)) for r in review.get("rules", []) if r.get("rule") == item["rule"])
    write_json(folder / "verify.json", {"status": "review", "touched": [], "evidence": "rule auditor",
                                        "remaining": remaining, "remaining_examples": [], "new": []})
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
    item = read_json(folder / "item.json")
    touched = _touched(project, item["start"])
    check = subprocess.run(args.check, shell=True, cwd=project, capture_output=True, text=True,  # noqa: S602
                           encoding="utf-8", errors="replace", check=False)
    data = {"status": "check passed" if check.returncode == 0 else "check failed", "touched": touched,
            "evidence": "baseline",
            **compare_baseline(item, read_json(args.before.resolve(), {}), adopted_baseline(project, args.stack),
                               touched)}
    write_json(folder / "verify.json", data)
    return 0


# Markers that silence a finding instead of fixing it (ADOPT-3), on lines a fix adds.
SUPPRESSION = re.compile(
    r"eslint-disable|#\s*noqa|#\s*type:\s*ignore|#\s*pragma\s+warning\s+disable|\[SuppressMessage"
    r"|<NoWarn>|//\s*ignore(?:_for_file)?:|severity\s*=\s*none", re.IGNORECASE)
BASELINES = ("eslint-suppressions.json",)
CLOCK_SLACK = 2.0  # seconds: file and commit times are compared across processes


def _commits(project: Path, start: str) -> list[tuple[str, str, list[str]]]:
    """(sha, subject, files) for each commit after start, oldest first."""
    shas = git(project, "rev-list", "--reverse", f"{start}..HEAD").split()
    return [(sha, git(project, "log", "-1", "--format=%s", sha).strip(),
             [f for f in git(project, "show", "--name-only", "--format=", sha).splitlines() if f])
            for sha in shas]


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


def compute_verdict(project: Path, folder: Path) -> dict:
    item = read_json(folder / "item.json")
    clean, after = read_json(folder / "clean.json"), read_json(folder / "after.json")
    canary_run, verify = read_json(folder / "canary.json"), read_json(folder / "verify.json")
    pinned, red = read_json(folder / "pinned.json"), read_json(folder / "red.json")
    commits = _commits(project, item["start"])
    checks: dict[str, dict] = {}

    def check(name: str, ok: bool | None, reason: str) -> None:
        checks[name] = {"ok": ok, "reason": reason}

    last_commit = float(git(project, "log", "-1", "--format=%ct").strip() or 0)
    if after is None or after["source"] == "missing":
        check("tests ran", False, f"no readable result from the after run{': ' + after['error'] if after else ''}")
    elif after["executed"] == 0:
        check("tests ran", False, "no test executed in the after run")
    elif after["finished_at"] + CLOCK_SLACK < last_commit:
        check("tests ran", False, "the after run is older than the item's last commit")
    else:
        check("tests ran", True, f"{after['executed']} executed, {after['failed']} failed")

    if clean is None or after is None:
        check("nothing lost", False, "the clean or the after run is missing")
    elif clean["failed"]:
        check("nothing lost", False, f"the clean run already had {clean['failed']} failing tests")
    elif clean["source"] == after["source"] == "file":
        lost = sorted(t for t, o in clean["tests"].items() if o == "passed" and after["tests"].get(t) != "passed")
        check("nothing lost", not lost, f"no longer passing: {', '.join(lost)}" if lost else "every passing test still passes")
    else:
        worse = after["passed"] < clean["passed"] or after["failed"] > 0 or after["skipped"] > clean["skipped"]
        check("nothing lost", not worse, f"counts: {clean['passed']} passed before, {after['passed']} after"
              + (f", {after['failed']} failed" if after["failed"] else ""))

    if item["formatter_only"]:
        check("canary", None, "formatter only: no canary")
    elif canary_run is None:
        check("canary", False, "no canary was run")
    elif not canary_run["restored"]:
        check("canary", False, f"{canary_run['file']} wasn't restored after the canary")
    else:
        saw = canary_run["failed_delta"] > 0
        check("canary", saw, f"{canary_run['failed_delta']} new failures from the break in "
              f"{canary_run.get('file')}:{canary_run.get('line')}" if saw else "the break caused no new failure")

    pin = next(((sha, files) for sha, subject, files in commits if subject.startswith("test: pin")), None)
    if pin is None:
        check("pinned tests", None, "no pin commit")
    else:
        later = {f for sha, _, files in commits[[c[0] for c in commits].index(pin[0]) + 1:] for f in files}
        touched_pins = sorted(set(pin[1]) & later)
        ok = bool(pinned) and pinned["executed"] > 0 and pinned["failed"] == 0 and not touched_pins
        check("pinned tests", ok, "pinned tests passed on the unfixed code and stayed unchanged" if ok else
              (f"pinned tests changed after pinning: {', '.join(touched_pins)}" if touched_pins
               else "the pinned tests didn't pass on the unfixed code"))

    if not item["p1"]:
        check("red first", None, "not a P1 item")
    else:
        ok = bool(red) and red["failed"] > 0
        check("red first", ok, f"{red['failed']} failing before the fix" if ok else "no test was seen failing before the fix")

    if verify is None or verify.get("remaining") is None:
        check("item gone", False, f"not verified: {verify['status'] if verify else 'no verify run'}")
    elif verify["status"] == "check failed":
        check("item gone", False, "the project's check failed")
    else:
        ok = verify["remaining"] == 0 and not verify["new"]
        check("item gone", ok, f"{verify['remaining']} left, {len(verify['new'])} new in touched files ({verify['evidence']})")

    allowed = item["allow"] + (pin[1] if pin else [])
    changed = sorted({f for _, _, files in commits for f in files})
    outside = [f for f in changed if not any(in_area(f, a) or f == a for a in allowed)]
    added = [line[1:] for line in git(project, "diff", "-U0", f"{item['start']}..HEAD").splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    marks = [line.strip() for line in added if SUPPRESSION.search(line)]
    grown = [b for b in BASELINES if _baseline_total(project, "HEAD", b) > _baseline_total(project, item["start"], b)]
    problems = ([f"outside the item: {', '.join(outside)}"] if outside else []) + \
               ([f"suppression added: {marks[0]}"] if marks else []) + ([f"baseline grew: {', '.join(grown)}"] if grown else [])
    check("scope", not problems, "; ".join(problems) or f"{len(changed)} files, all inside the item")

    failing = [f"{name}: {c['reason']}" for name, c in checks.items() if c["ok"] is False]
    does_not_prove = ["the canary shows the tests see one spot, not every changed line"]
    if item.get("kind") == "review":
        does_not_prove.append("the item's absence rests on an AI rule auditor")
    if any(run and run.get("source") == "summary" for run in (clean, after)):
        does_not_prove.append("summary-line evidence has no per-test ids")
    return {"item": item["id"], "verdict": "STOPPED" if failing else "DONE", "checks": checks,
            "reasons": failing, "does_not_prove": does_not_prove}


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
    if verdict["verdict"] != "DONE":
        return 1
    done_file = folder.parent.parent / DONE
    done = read_json(done_file, [])
    write_json(done_file, sorted({*done, verdict["item"]}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    # "action", not "command": the test and canary commands have a --command option of their own.
    commands = parser.add_subparsers(dest="action", required=True)
    items = commands.add_parser("items", help="debt items for the next round")
    items.add_argument("out", type=Path)
    items.add_argument("--org", required=True)
    items.add_argument("--max", type=int, default=10)
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
    can = commands.add_parser("canary", help="break one line, run the tests, restore it")
    can.add_argument("project", type=Path)
    can.add_argument("--file", required=True)
    can.add_argument("--line", required=True, type=int)
    can.add_argument("--replace", required=True)
    can.add_argument("--command", required=True)
    can.add_argument("--format", required=True, choices=sorted(RESULT_SUFFIX))
    can.add_argument("--clean", required=True, type=Path)
    can.add_argument("--out", required=True, type=Path)
    ver = commands.add_parser("verify", help="re-run the analyzers on HEAD: the item must be gone")
    ver.add_argument("project", type=Path)
    ver.add_argument("--item-dir", required=True, type=Path)
    ver.add_argument("--stack", required=True)
    ver.add_argument("--org", required=True)
    ver.add_argument("--render", required=True, type=Path)
    ver.add_argument("--before", required=True, type=Path)
    ver.add_argument("--solution")
    rev = commands.add_parser("verify-review", help="record a rule auditor's recount of a review item")
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
    args = parser.parse_args(argv)
    return {"items": cmd_items, "start": cmd_start, "test": cmd_test, "canary": cmd_canary,
            "verify": cmd_verify, "verify-review": cmd_verify_review, "baseline": cmd_baseline,
            "verify-adopted": cmd_verify_adopted, "verdict": cmd_verdict}[args.action](args)


if __name__ == "__main__":
    sys.exit(main())
