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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
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
    args = parser.parse_args(argv)
    return {"items": cmd_items, "start": cmd_start, "test": cmd_test, "canary": cmd_canary}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
